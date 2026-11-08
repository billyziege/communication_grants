# Contract 02 — Repository Interface

**Status:** Ready for implementation  
**Depends on:** Contract 01 (data types reference the `grants` schema)  
**Prerequisite for:** Contract 04 (SQLite query layer implements this), Contract 05 (GraphQL resolvers call this)

---

## 1. Purpose and Scope

This contract defines the `Grant` and `GrantPage` data types and the `GrantRepository` Protocol that the SQLite query layer implements and the GraphQL resolvers call. No I/O or SQL belongs here — only shapes and signatures.

**In scope:**
- `Grant` dataclass (Python representation of a unified grant row)
- `GrantPage` dataclass (paginated result envelope)
- `GrantRepository` Protocol with four method signatures
- Pagination contract (offset-based at the repository level)
- Valid `source` filter values
- Error contract

**Out of scope:**
- SQLite queries (Contract 04)
- GraphQL types and Relay cursor encoding (Contract 05)
- Any I/O, file reading, or network calls

---

## 2. `Grant` Dataclass

```python
from dataclasses import dataclass, field

@dataclass
class Grant:
    id:                int
    title:             str
    abstract:          str | None
    start_date:        str | None          # ISO 8601 YYYY-MM-DD or None
    end_date:          str | None          # ISO 8601 YYYY-MM-DD or None
    funding_amount:    float | None
    funding_currency:  str | None          # 'USD' | 'EUR' | None
    organization:      str | None
    country:           str | None          # ISO alpha-2 or None
    source:            str                 # 'nih' | 'cordis'
    source_id:         str
    source_programme:  str | None          # None | 'fp7' | 'h2020' | 'horizon_europe'
    source_url:        str | None
    metadata:          dict = field(default_factory=dict)  # parsed from JSON; never None
```

`metadata` is always a `dict` — the repository parses the JSON column before returning; callers never see a raw JSON string.

---

## 3. `GrantPage` Dataclass

```python
@dataclass
class GrantPage:
    items:   list[Grant]
    total:   int    # total matching rows (ignoring limit/offset), for pagination UI
    offset:  int    # the offset used to produce this page
    limit:   int    # the limit used to produce this page
```

`total` is the count of all rows matching the query/filter, not the count of items on this page. It enables the caller to compute page count and detect end-of-results.

---

## 4. `GrantRepository` Protocol

```python
from typing import Protocol

class GrantRepository(Protocol):

    def search(
        self,
        query: str,
        *,
        source: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> GrantPage:
        """Full-text search over title and abstract.

        query    — FTS5 MATCH expression (the caller supplies the search terms;
                   the implementation wraps it in a MATCH query)
        source   — 'nih', 'cordis', or None (all sources)
        limit    — max rows to return; capped at MAX_PAGE_SIZE by the implementation
        offset   — zero-based row offset for pagination
        """
        ...

    def list_grants(
        self,
        *,
        source: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> GrantPage:
        """Return grants without a full-text filter.

        Ordered by id ASC (stable, deterministic order for pagination).
        source, limit, offset behave identically to search().
        """
        ...

    def get_by_id(self, grant_id: int) -> Grant | None:
        """Return the grant with the given internal id, or None."""
        ...

    def get_by_source(self, source: str, source_id: str) -> Grant | None:
        """Return the grant matching (source, source_id), or None."""
        ...
```

---

## 5. Pagination Contract

- `limit` must be a positive integer. Implementations clamp it to `MAX_PAGE_SIZE = 500`.
- `offset` must be ≥ 0. A negative offset raises `ValueError`.
- An `offset` beyond the last row returns `GrantPage(items=[], total=N, offset=offset, limit=limit)` — not an error.
- `total` reflects the count of all matching rows for the query/filter, computed in the same query as the items (e.g. via `COUNT(*) OVER()` or a separate `SELECT COUNT(*)`).

---

## 6. `source` Filter

| Value | Meaning |
|---|---|
| `'nih'` | NIH ExPORTER and gap-fill records only |
| `'cordis'` | All CORDIS records (all three programmes) |
| `None` | All records from both sources |

An unrecognized `source` value (anything other than `'nih'`, `'cordis'`, or `None`) raises `ValueError`.

---

## 7. Error Contract

| Situation | Behavior |
|---|---|
| Negative `offset` | `ValueError` |
| `limit` ≤ 0 | `ValueError` |
| Unrecognized `source` string | `ValueError` |
| FTS5 syntax error in `query` | Let the underlying `sqlite3.OperationalError` propagate — do not swallow it |
| DB not yet built / table missing | Let `sqlite3.OperationalError` propagate |

Implementations must not catch and swallow unexpected exceptions.

---

## 8. File Layout

```
db/
  repository.py    # Grant, GrantPage, GrantRepository, MAX_PAGE_SIZE
```

---

## 9. Test Surface

Tests go in `tests/test_repository.py` and test the **interface contract** only — not any SQLite implementation. Use direct instantiation of `Grant` and `GrantPage` to verify the dataclasses, and a minimal stub implementation of `GrantRepository` to verify the Protocol is correctly defined.

- **`Grant` dataclass:** default `metadata={}` is not shared across instances (mutable default guard)
- **`GrantPage` dataclass:** fields accessible by name; `total` is independent of `len(items)`
- **Protocol structural check:** a class implementing all four methods satisfies `isinstance(obj, GrantRepository)` — requires `runtime_checkable` or use `typing.get_protocol_members`
- **`source` filter validation:** `ValueError` for unrecognized values (test at the protocol level by verifying the stub raises correctly)
- **`offset` validation:** negative offset raises `ValueError`
- **`limit` clamping:** a stub that enforces `MAX_PAGE_SIZE` returns at most 500 items
- **`metadata` is always dict:** a `Grant` constructed with `metadata=None` should be caught at construction time or by the type checker — verify the dataclass default
