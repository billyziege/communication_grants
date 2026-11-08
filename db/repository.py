"""db/repository.py — Grant, GrantPage, GrantRepository, MAX_PAGE_SIZE.

This module defines the data types and the repository Protocol for the
communication grants database.  No I/O or SQL belongs here — only shapes
and signatures (Contract 02).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# Maximum rows any implementation may return in a single page.
MAX_PAGE_SIZE: int = 500


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class Grant:
    """Python representation of a unified grant row.

    ``metadata`` is always a dict (the repository parses the JSON column
    before returning; callers never see a raw JSON string).
    """

    id:               int
    title:            str
    abstract:         str | None
    start_date:       str | None          # ISO 8601 YYYY-MM-DD or None
    end_date:         str | None          # ISO 8601 YYYY-MM-DD or None
    funding_amount:   float | None
    funding_currency: str | None          # 'USD' | 'EUR' | None
    organization:     str | None
    country:          str | None          # ISO alpha-2 or None
    source:           str                 # 'nih' | 'cordis'
    source_id:        str
    source_programme: str | None          # None | 'fp7' | 'h2020' | 'horizon_europe'
    source_url:       str | None
    metadata:         dict = field(default_factory=dict)  # parsed from JSON; never None


@dataclass
class GrantFacets:
    """Distinct facet values across all grants matching a search query."""

    sources:    list[str]   # e.g. ['nih', 'cordis']
    programmes: list[str]   # e.g. ['fp7', 'h2020', 'horizon_europe']
    countries:  list[str]   # ISO alpha-2 codes, e.g. ['CZ', 'DE', 'US']


@dataclass
class GrantPage:
    """Paginated result envelope.

    ``total`` is the count of *all* rows matching the query/filter, not the
    count of items on this page.  It enables the caller to compute page count
    and detect end-of-results.
    """

    items:  list[Grant]
    total:  int    # total matching rows (ignoring limit/offset), for pagination UI
    offset: int    # the offset used to produce this page
    limit:  int    # the limit used to produce this page


# ---------------------------------------------------------------------------
# Repository Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class GrantRepository(Protocol):
    """Read-only repository interface for grant data.

    Implementations supply the SQL queries; this module supplies only the
    signatures that callers (GraphQL resolvers, CLI tools, tests) depend on.

    Validation rules every implementation must enforce
    --------------------------------------------------
    - ``limit`` must be a positive integer; clamp to ``MAX_PAGE_SIZE``.
    - ``offset`` must be >= 0; raise ``ValueError`` for negative values.
    - ``source`` must be ``'nih'``, ``'cordis'``, or ``None``; raise
      ``ValueError`` for any other string.
    - FTS5 syntax errors and missing-table errors propagate as
      ``sqlite3.OperationalError`` — do not swallow them.
    """

    def search(
        self,
        query: str,
        *,
        source: str | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        country: str | None = None,
        programmes: list[str] | None = None,
        funding_min: float | None = None,
        funding_max: float | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> GrantPage:
        """Full-text search over title and abstract.

        query       — FTS5 MATCH expression
        source      — 'nih', 'cordis', or None (all sources)
        year_min    — inclusive lower bound on start_date year
        year_max    — inclusive upper bound on start_date year
        country     — exact ISO alpha-2 country code
        programmes  — list of source_programme slugs (OR logic within list)
        funding_min — inclusive lower bound on funding_amount
        funding_max — inclusive upper bound on funding_amount
        limit       — max rows; capped at MAX_PAGE_SIZE
        offset      — zero-based row offset for pagination
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

    def get_facets(
        self,
        query: str,
        *,
        source: str | None = None,
    ) -> GrantFacets:
        """Return distinct sources, programmes, and countries matching query.

        Runs three lightweight GROUP BY aggregations via FTS5 MATCH.
        Same filter semantics as search() — source is optional.
        """
        ...
