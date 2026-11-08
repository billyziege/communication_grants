"""api/schema.py — Strawberry GraphQL schema for the communication grants API.

Exposes a Relay-compatible GraphQL API over the grant database.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Iterable

import strawberry
from strawberry import relay
from strawberry.scalars import JSON

from db.repository import Grant


# ---------------------------------------------------------------------------
# Source enum
# ---------------------------------------------------------------------------


@strawberry.enum
class Source(Enum):
    NIH = "nih"
    CORDIS = "cordis"


# ---------------------------------------------------------------------------
# GrantLookupInput
# ---------------------------------------------------------------------------


@strawberry.input
class GrantLookupInput:
    source: Source
    source_id: str


# ---------------------------------------------------------------------------
# GrantNode
# ---------------------------------------------------------------------------


@strawberry.type
class GrantNode(relay.Node):
    db_id: relay.NodeID[int]
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
    def from_db(cls, grant: Grant) -> "GrantNode":
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
            source_url=grant.source_url or "",
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


# ---------------------------------------------------------------------------
# Params sentinels
# ---------------------------------------------------------------------------


@dataclass
class ListParams:
    source_filter: str | None

    def __iter__(self):
        return iter([])


@dataclass
class SearchParams:
    query: str
    source_filter: str | None

    def __iter__(self):
        return iter([])


# ---------------------------------------------------------------------------
# Cursor helper
# ---------------------------------------------------------------------------


def _cursor_to_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    _, val = relay.from_base64(cursor)
    return int(val) + 1


# ---------------------------------------------------------------------------
# GrantConnection
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# SearchGrantConnection
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Query root
# ---------------------------------------------------------------------------


@strawberry.type
class Query:
    node: relay.Node = relay.node()

    @relay.connection(GrantConnection, max_results=500)
    def grants(
        self,
        info: strawberry.types.Info,
        grant_source: Annotated[
            Source | None,
            strawberry.argument(name="source"),
        ] = None,
    ) -> Iterable[GrantNode]:
        return ListParams(source_filter=grant_source.value if grant_source else None)

    @relay.connection(SearchGrantConnection, max_results=500)
    def search(
        self,
        info: strawberry.types.Info,
        query: str,
        grant_source: Annotated[
            Source | None,
            strawberry.argument(name="source"),
        ] = None,
    ) -> Iterable[GrantNode]:
        return SearchParams(
            query=query,
            source_filter=grant_source.value if grant_source else None,
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

    @strawberry.field
    def grants_by_source(
        self,
        info: strawberry.types.Info,
        items: list[GrantLookupInput],
    ) -> list[GrantNode | None]:
        repo = info.context.repo
        return [
            GrantNode.from_db(grant)
            if (grant := repo.get_by_source(item.source.value, item.source_id)) is not None
            else None
            for item in items
        ]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


schema = strawberry.Schema(
    query=Query,
    config=strawberry.schema.config.StrawberryConfig(relay_max_results=500),
)
