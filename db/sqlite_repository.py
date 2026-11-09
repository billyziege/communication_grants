"""db/sqlite_repository.py — SQLiteGrantRepository.

Concrete implementation of the GrantRepository Protocol using raw SQLite
queries.  No ORM.  All connection lifecycle (open/close) is the caller's
responsibility.

Side effect: sets conn.row_factory = sqlite3.Row on the connection it
receives.  All callers in this project use the connection exclusively with
this repository, so there is no risk of interference from this change.
"""
from __future__ import annotations

import json
import sqlite3

from db.repository import Grant, GrantFacets, GrantPage, GrantRepository, MAX_PAGE_SIZE

# FTS5 is told to rank at most this many results before the caller filters them.
# This avoids computing BM25 across the full corpus for common grant words.
# 2 000 is well above any realistic browsing need while keeping queries <300 ms.
FTS_MAX_RESULTS = 2000


class SQLiteGrantRepository:
    """Read-only SQLite implementation of the GrantRepository Protocol.

    Does not inherit from GrantRepository; structural subtyping via the
    @runtime_checkable Protocol is sufficient (see db/repository.py).
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        # Intentional documented side effect: set row_factory so that all
        # queries return sqlite3.Row objects, enabling column access by name.
        conn.row_factory = sqlite3.Row
        self._conn = conn

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate(self, source: str | None, limit: int, offset: int) -> int:
        """Validate and clamp pagination / filter parameters.

        Returns the (possibly clamped) limit value.

        Raises
        ------
        ValueError
            source not in ('nih', 'cordis', None)
            offset < 0
            limit <= 0
        """
        if source not in ("nih", "cordis", None):
            raise ValueError(
                f"source must be 'nih', 'cordis', or None; got {source!r}"
            )
        if offset < 0:
            raise ValueError(f"offset must be >= 0; got {offset}")
        if limit <= 0:
            raise ValueError(f"limit must be > 0; got {limit}")
        if limit > MAX_PAGE_SIZE:
            return MAX_PAGE_SIZE
        return limit

    def _row_to_grant(self, row: sqlite3.Row) -> Grant:
        """Convert a sqlite3.Row to a Grant dataclass.

        ``metadata`` is always a dict — the raw JSON column is parsed here;
        NULL metadata maps to an empty dict.
        """
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

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

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
        """Full-text search via FTS5 MATCH with optional server-side filters.

        Results ordered by BM25 relevance (ascending — more negative = more
        relevant). Filter parameters map directly to SQL WHERE clauses so the
        full database is searched, not just the loaded page.

        sqlite3.OperationalError from malformed MATCH expressions propagates.
        """
        clamped_limit = self._validate(source, limit, offset)

        # Build WHERE clause for the outer (post-FTS5) query.
        # Conditions reference the joined `grants` alias g; no leading "AND".
        where_parts: list[str] = []
        filter_params: list = []

        if source is not None:
            where_parts.append("g.source = ?")
            filter_params.append(source)
        if year_min is not None:
            where_parts.append("CAST(substr(g.start_date, 1, 4) AS INT) >= ?")
            filter_params.append(year_min)
        if year_max is not None:
            where_parts.append("CAST(substr(g.start_date, 1, 4) AS INT) <= ?")
            filter_params.append(year_max)
        if country:
            where_parts.append("g.country = ?")
            filter_params.append(country)
        if programmes:
            placeholders = ",".join(["?"] * len(programmes))
            where_parts.append(f"g.source_programme IN ({placeholders})")
            filter_params.extend(programmes)
        if funding_min is not None:
            where_parts.append("g.funding_amount >= ?")
            filter_params.append(funding_min)
        if funding_max is not None:
            where_parts.append("g.funding_amount <= ?")
            filter_params.append(funding_max)

        where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        # Using FTS5's native `rank` column in the CTE lets the engine return
        # results in BM25 order using its internal heap-sort, stopping at
        # FTS_MAX_RESULTS without scoring the full corpus.  The outer query
        # then filters and paginates the already-ranked set.
        results_sql = f"""
            WITH fts AS (
                SELECT rowid, rank
                FROM   grants_fts
                WHERE  grants_fts MATCH ?
                ORDER  BY rank LIMIT {FTS_MAX_RESULTS}
            )
            SELECT g.*, fts.rank
            FROM   fts
            JOIN   grants g ON fts.rowid = g.id
            {where_clause}
            ORDER  BY fts.rank
            LIMIT  ? OFFSET ?
        """
        rows = self._conn.execute(
            results_sql,
            [query] + filter_params + [clamped_limit, offset],
        ).fetchall()

        count_sql = f"""
            WITH fts AS (
                SELECT rowid
                FROM   grants_fts
                WHERE  grants_fts MATCH ?
                ORDER  BY rank LIMIT {FTS_MAX_RESULTS}
            )
            SELECT COUNT(*)
            FROM   fts
            JOIN   grants g ON fts.rowid = g.id
            {where_clause}
        """
        total: int = self._conn.execute(
            count_sql,
            [query] + filter_params,
        ).fetchone()[0]

        return GrantPage(
            items=[self._row_to_grant(row) for row in rows],
            total=total,
            offset=offset,
            limit=clamped_limit,
        )

    def list_grants(
        self,
        *,
        source: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> GrantPage:
        """Return grants without a full-text filter, ordered by id ASC.

        Stable, deterministic ordering by id enables reliable pagination.
        """
        clamped_limit = self._validate(source, limit, offset)

        if source is not None:
            where_clause = "WHERE source = ?"
            source_params: list = [source]
        else:
            where_clause = ""
            source_params = []

        results_sql = f"""
            SELECT *
            FROM   grants
            {where_clause}
            ORDER  BY id ASC
            LIMIT  ? OFFSET ?
        """
        rows = self._conn.execute(
            results_sql,
            source_params + [clamped_limit, offset],
        ).fetchall()

        count_sql = f"""
            SELECT COUNT(*)
            FROM   grants
            {where_clause}
        """
        total: int = self._conn.execute(count_sql, source_params).fetchone()[0]

        return GrantPage(
            items=[self._row_to_grant(row) for row in rows],
            total=total,
            offset=offset,
            limit=clamped_limit,
        )

    def get_by_id(self, grant_id: int) -> Grant | None:
        """Return the grant with the given internal id, or None."""
        row = self._conn.execute(
            "SELECT * FROM grants WHERE id = ?",
            (grant_id,),
        ).fetchone()
        return self._row_to_grant(row) if row is not None else None

    def get_by_source(self, source: str, source_id: str) -> Grant | None:
        """Return the grant matching (source, source_id), or None."""
        row = self._conn.execute(
            "SELECT * FROM grants WHERE source = ? AND source_id = ?",
            (source, source_id),
        ).fetchone()
        return self._row_to_grant(row) if row is not None else None

    def get_facets(
        self,
        query: str,
        *,
        source: str | None = None,
    ) -> GrantFacets:
        """Return distinct sources, programmes, and countries for query."""
        if source not in ("nih", "cordis", None):
            raise ValueError(
                f"source must be 'nih', 'cordis', or None; got {source!r}"
            )

        source_filter = "AND g.source = ?" if source is not None else ""
        source_params: list = [source] if source is not None else []

        def _distinct(col: str) -> list[str]:
            sql = f"""
                WITH fts AS (
                    SELECT rowid
                    FROM   grants_fts
                    WHERE  grants_fts MATCH ?
                    ORDER  BY rank LIMIT {FTS_MAX_RESULTS}
                )
                SELECT DISTINCT g.{col}
                FROM   fts
                JOIN   grants g ON fts.rowid = g.id
                WHERE  g.{col} IS NOT NULL
                       {source_filter}
                ORDER  BY g.{col}
            """
            rows = self._conn.execute(sql, [query] + source_params).fetchall()
            return [r[0] for r in rows]

        return GrantFacets(
            sources=_distinct("source"),
            programmes=_distinct("source_programme"),
            countries=_distinct("country"),
        )
