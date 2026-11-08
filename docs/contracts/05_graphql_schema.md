# Contract 05 — GraphQL Schema

**Status:** Ready for implementation  
**Depends on:** Contract 02 (`db/repository.py` — `Grant`, `GrantPage`, `GrantRepository`), Contract 04 (`db/sqlite_repository.py` — `SQLiteGrantRepository`)  
**Prerequisite for:** Contract 06 (React + Relay frontend)

---

## 1. Purpose and Scope

`api/schema.py` and `api/app.py` expose the grant database as a Relay-compatible GraphQL API using Strawberry and FastAPI.

**In scope:**
- `GrantNode` Strawberry type implementing `relay.Node`
- `GrantConnection` and `SearchGrantConnection` — DB-backed Relay connections
- `Query` root type with `node`, `grants`, `search`, and `grantBySource` fields
- `Source` enum
- `CustomContext` for injecting the repository
- FastAPI app wiring (`api/app.py`)

**Out of scope:**
- Mutations — this API is read-only; all writes go through the CLI build pipeline
- Authentication / authorization
- Subscriptions
- `last`/`before` backward pagination (not implemented in v1; silently ignored)

---

## 2. Package Additions

Add to `pyproject.toml` dependencies:

```
strawberry-graphql[fastapi]>=0.341
fastapi>=0.115
uvicorn[standard]>=0.30
```

---

## 3. File Layout

```
api/
  __init__.py           # empty package marker
  schema.py             # all Strawberry types, connections, Query
  app.py                # FastAPI app, context, router
tests/
  test_graphql.py
```

---

## 4. `Source` Enum

```python
import strawberry
from enum import Enum

@strawberry.enum
class Source(Enum):
    NIH = "nih"
    CORDIS = "cordis"
```

Must subclass Python `Enum`. The `.value` attribute (`"nih"`, `"cordis"`) maps directly to the repository's `source` filter string.

---

## 5. `GrantNode`

```python
from strawberry import relay
from strawberry.scalars import JSON

@strawberry.type
class GrantNode(relay.Node):
    db_id: relay.NodeID[int]        # private; becomes id: ID! (GlobalID)
    title: str
    abstract: str | None
    start_date: str | None
    end_date: str | None
    funding_amount: float | None
    funding_currency: str | None
    organization: str | None
    country: str | None
    source: Source
    source_id: str
    source_programme: str | None
    source_url: str
    metadata: JSON

    @classmethod
    def from_db(cls, grant: "Grant") -> "GrantNode":
        return cls(
            db_id=grant.id,
            title=grant.title,
            abstract=grant.abstract,
            start_date=grant.start_date,
            end_date=grant.end_date,
            funding_amount=grant.funding_amount,
            funding_currency=grant.funding_currency,
            organization=grant.organization,
            country=grant.country,
            source=Source(grant.source),
            source_id=grant.source_id,
            source_programme=grant.source_programme,
            source_url=grant.source_url,
            metadata=grant.metadata,
        )

    @classmethod
    def resolve_nodes(
        cls,
        *,
        info: strawberry.types.Info,
        node_ids: Iterable[str],
        required: bool = False,
    ) -> Iterable["GrantNode | None"]:
        repo = info.context.repo
        results = []
        for node_id in node_ids:
            grant = repo.get_by_id(int(node_id))
            if grant is not None:
                results.append(cls.from_db(grant))
            elif required:
                raise ValueError(f"Grant {node_id!r} not found")
            else:
                results.append(None)
        return results
```

**Notes:**
- `relay.NodeID[int]` marks the field private; Strawberry generates `id: ID!` encoded as `base64("GrantNode:{db_id}")`.
- `resolve_nodes` is called by the auto-generated `node(id: ID!): Node!` root query. Do not call it directly.
- `metadata: JSON` uses `strawberry.scalars.JSON` — no additional scalar registration required.

---

## 6. Params Sentinel Objects

DB-backed connections use a lightweight params sentinel instead of a real iterable. The resolver returns the sentinel; `resolve_connection` reads it to call the repository.

```python
from dataclasses import dataclass

@dataclass
class ListParams:
    source_filter: str | None

@dataclass
class SearchParams:
    query: str
    source_filter: str | None
```

Both classes implement `__iter__` returning an empty iterator to satisfy Strawberry's runtime iterable check without loading any data:

```python
def __iter__(self):
    return iter([])
```

---

## 7. `GrantConnection`

Used by the `grants` query. Calls `repo.list_grants()`.

```python
@strawberry.type
class GrantConnection(relay.Connection[GrantNode]):
    total_count: int = 0

    @classmethod
    def resolve_connection(
        cls,
        nodes: ListParams,
        *,
        info: strawberry.types.Info,
        before: str | None = None,
        after: str | None = None,
        first: int | None = None,
        last: int | None = None,
        max_results: int | None = None,
        **kwargs,
    ) -> "GrantConnection":
        repo = info.context.repo
        offset = _cursor_to_offset(after)
        limit = min(first if first is not None else 20, max_results or 500)

        page = repo.list_grants(
            source=nodes.source_filter,
            limit=limit,
            offset=offset,
        )

        edges = [
            relay.Edge(
                node=GrantNode.from_db(item),
                cursor=relay.to_base64("arrayconnection", str(offset + i)),
            )
            for i, item in enumerate(page.items)
        ]
        return cls(
            edges=edges,
            page_info=relay.PageInfo(
                start_cursor=edges[0].cursor if edges else None,
                end_cursor=edges[-1].cursor if edges else None,
                has_previous_page=offset > 0,
                has_next_page=(offset + len(page.items)) < page.total,
            ),
            total_count=page.total,
        )
```

---

## 8. `SearchGrantConnection`

Used by the `search` query. Calls `repo.search()`. Identical shape to `GrantConnection` with different params handling.

```python
@strawberry.type
class SearchGrantConnection(relay.Connection[GrantNode]):
    total_count: int = 0

    @classmethod
    def resolve_connection(
        cls,
        nodes: SearchParams,
        *,
        info: strawberry.types.Info,
        before: str | None = None,
        after: str | None = None,
        first: int | None = None,
        last: int | None = None,
        max_results: int | None = None,
        **kwargs,
    ) -> "SearchGrantConnection":
        repo = info.context.repo
        offset = _cursor_to_offset(after)
        limit = min(first if first is not None else 20, max_results or 500)

        page = repo.search(
            nodes.query,
            source=nodes.source_filter,
            limit=limit,
            offset=offset,
        )

        edges = [
            relay.Edge(
                node=GrantNode.from_db(item),
                cursor=relay.to_base64("arrayconnection", str(offset + i)),
            )
            for i, item in enumerate(page.items)
        ]
        return cls(
            edges=edges,
            page_info=relay.PageInfo(
                start_cursor=edges[0].cursor if edges else None,
                end_cursor=edges[-1].cursor if edges else None,
                has_previous_page=offset > 0,
                has_next_page=(offset + len(page.items)) < page.total,
            ),
            total_count=page.total,
        )
```

---

## 9. Cursor Helper

```python
def _cursor_to_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    _, val = relay.from_base64(cursor)
    return int(val) + 1
```

Cursor format is `base64("arrayconnection:{offset}")` — the standard Relay `arrayconnection` encoding, natively understood by the Relay JS client.

---

## 10. `Query` Root Type

```python
@strawberry.type
class Query:
    node: relay.Node = relay.node()

    @relay.connection(GrantConnection, max_results=500)
    def grants(
        self,
        info: strawberry.types.Info,
        source: Source | None = None,
    ) -> Iterable[GrantNode]:
        return ListParams(source_filter=source.value if source else None)

    @relay.connection(SearchGrantConnection, max_results=500)
    def search(
        self,
        info: strawberry.types.Info,
        query: str,
        source: Source | None = None,
    ) -> Iterable[GrantNode]:
        return SearchParams(
            query=query,
            source_filter=source.value if source else None,
        )

    @strawberry.field
    def grant_by_source(
        self,
        info: strawberry.types.Info,
        source: Source,
        source_id: str,
    ) -> GrantNode | None:
        grant = info.context.repo.get_by_source(source.value, source_id)
        return GrantNode.from_db(grant) if grant else None
```

**`node(id: ID!)`** is auto-generated by `relay.node()` — no additional code needed. It decodes the global ID, dispatches to `GrantNode.resolve_nodes`, and returns a `Node` interface type.

---

## 11. Schema Object

```python
schema = strawberry.Schema(
    query=Query,
    config=strawberry.schema.config.StrawberryConfig(relay_max_results=500),
)
```

---

## 12. Context — `api/app.py`

```python
import os
import sqlite3
import strawberry
from strawberry.fastapi import GraphQLRouter, BaseContext
from fastapi import FastAPI
from db.sqlite_repository import SQLiteGrantRepository
from api.schema import schema

class CustomContext(BaseContext):
    def __init__(self, repo: SQLiteGrantRepository) -> None:
        super().__init__()
        self.repo = repo

def get_context() -> CustomContext:
    db_path = os.environ["GRANTS_DB_PATH"]
    conn = sqlite3.connect(db_path, check_same_thread=False)
    repo = SQLiteGrantRepository(conn)
    return CustomContext(repo=repo)

graphql_router = GraphQLRouter(
    schema,
    context_getter=get_context,
    graphql_ide="graphiql",
)

app = FastAPI(title="Communication Grants API")
app.include_router(graphql_router, prefix="/graphql")
```

**`GRANTS_DB_PATH`** — required environment variable; path to the SQLite database file. No default; raise `KeyError` if absent (the FastAPI startup will fail with a clear error message).

**Connection per request:** Opening a new `sqlite3.connect()` per request is acceptable for this read-only research tool. No connection pool is needed.

---

## 13. Generated SDL (expected)

```graphql
interface Node {
  id: ID!
}

type GrantNode implements Node {
  id: ID!
  title: String!
  abstract: String
  startDate: String
  endDate: String
  fundingAmount: Float
  fundingCurrency: String
  organization: String
  country: String
  source: Source!
  sourceId: String!
  sourceProgramme: String
  sourceUrl: String!
  metadata: JSON!
}

type GrantNodeEdge {
  cursor: String!
  node: GrantNode!
}

type GrantConnection {
  pageInfo: PageInfo!
  edges: [GrantNodeEdge!]!
  totalCount: Int!
}

type SearchGrantConnection {
  pageInfo: PageInfo!
  edges: [GrantNodeEdge!]!
  totalCount: Int!
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}

enum Source {
  NIH
  CORDIS
}

type Query {
  node(id: ID!): Node!
  grants(source: Source, before: String, after: String, first: Int, last: Int): GrantConnection!
  search(query: String!, source: Source, before: String, after: String, first: Int, last: Int): SearchGrantConnection!
  grantBySource(source: Source!, sourceId: String!): GrantNode
}

scalar JSON
```

---

## 14. Error Handling

- **FTS syntax error:** `sqlite3.OperationalError` from a malformed `search` query propagates through `resolve_connection` and becomes a standard GraphQL `errors` array entry. Do not catch it.
- **Missing `GRANTS_DB_PATH`:** `KeyError` from `os.environ["GRANTS_DB_PATH"]` surfaces immediately on first request with a 500 and a clear message. No special handling.
- **`node()` not found:** `resolve_nodes` returns `None` for unknown IDs (when `required=False`). Strawberry surfaces this as a null in the response or a GraphQL error per the spec.

---

## 15. Test Surface

Tests use `schema.execute_sync()` with an in-memory SQLite database — no HTTP layer, no env-var dependency.

**Suggested fixture:**

```python
import sqlite3, json, pytest
from db.models import create_schema
from db.sqlite_repository import SQLiteGrantRepository
from api.schema import schema, CustomContext

@pytest.fixture
def ctx():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    conn.execute("""
        INSERT INTO grants
          (title, abstract, source, source_id, source_url, metadata)
        VALUES
          ('NIH Grant', 'An NIH abstract', 'nih', 'APP001',
           'https://reporter.nih.gov/project-details/APP001', '{}'),
          ('CORDIS Grant', 'A CORDIS abstract', 'cordis', 'C001',
           'https://cordis.europa.eu/project/id/C001', '{}')
    """)
    conn.execute("INSERT INTO grants_fts(grants_fts) VALUES('rebuild')")
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    return CustomContext(repo=repo)

def gql(query, ctx, variables=None):
    return schema.execute_sync(query, context_value=ctx, variable_values=variables or {})
```

**Required tests:**

- **`grants` query returns all rows:** `grants { edges { node { title } } totalCount }` returns 2 edges, totalCount=2
- **`grants` source filter:** `grants(source: NIH)` returns only the NIH grant; `grants(source: CORDIS)` returns only CORDIS
- **`grants` pagination:** insert 5 rows; `grants(first: 2)` returns 2 edges with `hasNextPage: true`; following with `after: endCursor` returns the next page
- **`grants` hasNextPage / hasPreviousPage:** correct booleans on first page, middle page, last page
- **`grants` totalCount stable across pages:** totalCount is the same on every page, not just the current slice
- **`search` returns relevant result:** `search(query: "NIH")` returns the NIH grant
- **`search` BM25 ordering:** better FTS match appears first
- **`search` source filter:** `search(query: "grant", source: CORDIS)` returns only CORDIS
- **`search` FTS syntax error:** malformed query (`search(query: "AND AND")`) returns a GraphQL error entry (not a 500)
- **`node` lookup:** `node(id: $id)` with a valid encoded GrantNode ID returns `... on GrantNode { title }`
- **`node` missing ID:** `node(id: "invalid")` returns a GraphQL error (not a crash)
- **`grantBySource` found:** `grantBySource(source: NIH, sourceId: "APP001")` returns the NIH grant
- **`grantBySource` not found:** `grantBySource(source: NIH, sourceId: "MISSING")` returns null
- **`GrantNode.id` is a valid GlobalID:** `GrantNode.id` decodes to `("GrantNode", "<int>")` via `relay.from_base64`
- **`metadata` returned as object:** grant with `metadata='{"x":1}'` returns `metadata { x }` or the JSON object (not a string)
- **Source enum serialization:** NIH grant's `source` field serializes as `"NIH"` (enum name, not `"nih"`)
- **All GrantNode fields round-trip:** a fully-populated grant row returns every field correctly via a `grants` query
- **`last`/`before` ignored gracefully:** `grants(last: 2)` returns a result without crashing (empty or first page)
