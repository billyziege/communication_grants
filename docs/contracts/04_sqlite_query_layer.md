# Contract 04 — SQLite Query Layer

**Status:** Ready for implementation  
**Depends on:** Contract 01 (`db/models.py` — `create_schema`), Contract 02 (`db/repository.py` — `Grant`, `GrantPage`, `GrantRepository`, `MAX_PAGE_SIZE`)  
**Prerequisite for:** Contract 05 (GraphQL resolvers receive a `SQLiteGrantRepository`)

---

## 1. Purpose and Scope

`db/sqlite_repository.py` contains `SQLiteGrantRepository`, the single concrete implementation of the `GrantRepository` Protocol. All queries are raw SQL — no ORM. The class owns input validation, BM25-ordered FTS search, offset-based pagination, and row-to-dataclass mapping.

**In scope:**
- `SQLiteGrantRepository` class and its four public methods
- Input validation (`source`, `limit`, `offset`) — this is where the enforcement documented in Contract 02 is actually implemented
- FTS5 `MATCH` queries for `search()`
- Raw `SELECT` queries for `list_grants()`, `get_by_id()`, `get_by_source()`
- `_row_to_grant()` private mapping helper
- `conn.row_factory` management

**Out of scope:**
- Opening or closing the SQLite connection (caller's responsibility)
- Schema creation — call `create_schema(conn)` from `db/models.py` if needed in tests
- FastAPI dependency injection (Contract 05)

---

## 2. Class Signature

```python
import json
import sqlite3
from db.repository import Grant, GrantPage, GrantRepository, MAX_PAGE_SIZE

class SQLiteGrantRepository:
    def __init__(self, conn: sqlite3.Connection) -> None: ...
    def search(self, query: str, *, source: str | None = None,
               limit: int = 20, offset: int = 0) -> GrantPage: ...
    def list_grants(self, *, source: str | None = None,
                    limit: int = 20, offset: int = 0) -> GrantPage: ...
    def get_by_id(self, grant_id: int) -> Grant | None: ...
    def get_by_source(self, source: str, source_id: str) -> Grant | None: ...
    def _row_to_grant(self, row: sqlite3.Row) -> Grant: ...       # private
    def _validate(self, source: str | None,
                  limit: int, offset: int) -> int: ...            # private; returns clamped limit
```

`SQLiteGrantRepository` need not declare `GrantRepository` as a base class — structural subtyping via `Protocol` is sufficient.

---

## 3. `__init__`

```python
def __init__(self, conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row   # set internally; documented side effect
    self._conn = conn
```

Setting `row_factory` on the received connection is an intentional side effect. All callers in this project use the connection exclusively with this repository, so there is no risk of interference. Document this in a comment.

---

## 4. Input Validation — `_validate()`

Called at the top of `search()` and `list_grants()` before any SQL. Returns the clamped limit.

| Check | Raises |
|---|---|
| `source not in ('nih', 'cordis', None)` | `ValueError` with message: `"source must be 'nih', 'cordis', or None; got {source!r}"` |
| `offset < 0` | `ValueError` with message: `"offset must be >= 0; got {offset}"` |
| `limit <= 0` | `ValueError` with message: `"limit must be > 0; got {limit}"` |
| `limit > MAX_PAGE_SIZE` | clamp silently: `return MAX_PAGE_SIZE` |

`get_by_id()` and `get_by_source()` take no pagination parameters and perform no validation beyond what Python's type system enforces.

---

## 5. `_row_to_grant()`

Converts a `sqlite3.Row` to a `Grant` dataclass. Called by all four public methods.

```python
def _row_to_grant(self, row: sqlite3.Row) -> Grant:
    return Grant(
        id=row["id"],
        title=row["title"],
        abstract=row["abstract"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        funding_amount=row["funding_amount"],
        funding_currency=row["funding_currency"],
        organization=row["organization"],
        country=row["country"],
        source=row["source"],
        source_id=row["source_id"],
        source_programme=row["source_programme"],
        source_url=row["source_url"],
        metadata=json.loads(row["metadata"] or "{}"),
    )
```

`metadata` is always a `dict` — never the raw JSON string.

---

## 6. `search()`

Full-text search over `title` and `abstract` via FTS5 `MATCH`. Results ordered by BM25 relevance (best match first). Runs two queries: one for the page of results, one for the total count.

### 6.1 Source filter pattern

Build the `source` clause dynamically to avoid passing the parameter twice:

```python
if source is not None:
    source_clause = "AND g.source = ?"
    source_params = [source]
else:
    source_clause = ""
    source_params = []
```

### 6.2 Results query

```sql
SELECT g.*,
       bm25(grants_fts) AS rank
FROM   grants_fts
JOIN   grants g ON grants_fts.rowid = g.id
WHERE  grants_fts MATCH ?
       {source_clause}
ORDER  BY bm25(grants_fts)
LIMIT  ? OFFSET ?
```

Parameters: `[query] + source_params + [clamped_limit, offset]`

### 6.3 Count query

```sql
SELECT COUNT(*)
FROM   grants_fts
JOIN   grants g ON grants_fts.rowid = g.id
WHERE  grants_fts MATCH ?
       {source_clause}
```

Parameters: `[query] + source_params`

### 6.4 BM25 ordering note

SQLite FTS5 `bm25()` returns negative values; more negative = more relevant. `ORDER BY bm25(grants_fts)` ascending therefore returns the best matches first. Do not negate or reverse the sign.

### 6.5 FTS5 syntax errors

Let `sqlite3.OperationalError` propagate — do not catch it. The GraphQL layer (Contract 05) will handle user-facing error presentation.

---

## 7. `list_grants()`

Returns grants without a full-text filter, ordered by `id ASC` for stable pagination.

### 7.1 Results query

```sql
SELECT *
FROM   grants
{where_clause}
ORDER  BY id ASC
LIMIT  ? OFFSET ?
```

Where `{where_clause}` is `WHERE source = ?` when source is given, empty otherwise.

Parameters: `source_params + [clamped_limit, offset]`

### 7.2 Count query

```sql
SELECT COUNT(*)
FROM   grants
{where_clause}
```

Parameters: `source_params`

---

## 8. `get_by_id()`

```sql
SELECT * FROM grants WHERE id = ?
```

Returns `_row_to_grant(row)` if a row is found, `None` otherwise.

---

## 9. `get_by_source()`

```sql
SELECT * FROM grants WHERE source = ? AND source_id = ?
```

Returns `_row_to_grant(row)` if a row is found, `None` otherwise.

---

## 10. File Layout

```
db/
  sqlite_repository.py    # SQLiteGrantRepository
tests/
  test_sqlite_repository.py
```

---

## 11. Test Surface

Tests use an in-memory SQLite connection pre-populated via `create_schema(conn)` and direct `INSERT` statements (or the fixture helper below). No file I/O; no mocking.

**Suggested fixture:**

```python
@pytest.fixture
def repo():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    # insert a couple of NIH and CORDIS rows directly, then rebuild FTS
    conn.execute("INSERT INTO grants (title, abstract, source, source_id, ...) VALUES (...)")
    conn.execute("INSERT INTO grants_fts(grants_fts) VALUES('rebuild')")
    conn.commit()
    return SQLiteGrantRepository(conn)
```

**Required tests:**

- **`row_factory` set internally:** construct repo without caller setting `row_factory`; `get_by_id` returns a `Grant` (not a tuple)
- **`metadata` parsing:** a row with JSON metadata returns `Grant.metadata` as a dict; a row with NULL metadata returns `{}`
- **`search` returns results:** inserting a grant with known title + FTS rebuild → `search("known term")` returns it
- **`search` BM25 ordering:** two grants where one is a better FTS match → better match appears first in `items`
- **`search` source filter:** `source='nih'` returns only NIH grants; `source='cordis'` returns only CORDIS grants; `source=None` returns both
- **`search` total count:** `total` reflects all matching rows, not just the current page
- **`search` empty result:** no match → `GrantPage(items=[], total=0, ...)`
- **`search` FTS syntax error:** malformed MATCH expression raises `sqlite3.OperationalError`
- **`list_grants` ordering:** rows returned in `id ASC` order
- **`list_grants` source filter:** behaves identically to `search` source filter
- **`list_grants` pagination:** correct page returned; `total` is the unfiltered count
- **`list_grants` offset beyond last row:** `items=[]`, `total=N` (not an error)
- **`get_by_id` found / not found:** correct `Grant` returned; `None` for missing id
- **`get_by_source` found / not found:** correct `Grant` returned; `None` for missing pair
- **Validation — `ValueError`:** negative offset, zero limit, negative limit, unrecognized source string — all four raise `ValueError` with the specified message
- **Validation — `MAX_PAGE_SIZE` clamping:** `limit=501` is silently clamped to 500; result has `limit=500` in returned `GrantPage`
- **Structural subtyping:** `isinstance(repo, GrantRepository)` is `True` without inheritance
