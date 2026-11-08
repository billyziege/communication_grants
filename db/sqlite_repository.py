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
        limit: int = 20,
        offset: int = 0,
    ) -> GrantPage:
        """Full-text search over title and abstract via FTS5 MATCH.

        Results are ordered by BM25 relevance, best match first.
        SQLite FTS5 bm25() returns negative values; more negative means more
        relevant.  ORDER BY bm25(grants_fts) ascending therefore returns the
        best matches first — do not negate or reverse the sign.

        sqlite3.OperationalError from malformed MATCH expressions propagates
        to the caller (Contract 05 handles user-facing presentation).
        """
        clamped_limit = self._validate(source, limit, offset)

        # Build the source filter clause dynamically to avoid passing the
        # parameter twice with OR IS NULL (§6.1 of contract).
        if source is not None:
            source_clause = "AND g.source = ?"
            source_params: list = [source]
        else:
            source_clause = ""
            source_params = []

        results_sql = f"""
            SELECT g.*,
                   bm25(grants_fts) AS rank
            FROM   grants_fts
            JOIN   grants g ON grants_fts.rowid = g.id
            WHERE  grants_fts MATCH ?
                   {source_clause}
            ORDER  BY bm25(grants_fts)
            LIMIT  ? OFFSET ?
        """
        rows = self._conn.execute(
            results_sql,
            [query] + source_params + [clamped_limit, offset],
        ).fetchall()

        count_sql = f"""
            SELECT COUNT(*)
            FROM   grants_fts
            JOIN   grants g ON grants_fts.rowid = g.id
            WHERE  grants_fts MATCH ?
                   {source_clause}
        """
        total: int = self._conn.execute(
            count_sql,
            [query] + source_params,
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

        if source is not None:
            source_clause = "AND g.source = ?"
            source_params: list = [source]
        else:
            source_clause = ""
            source_params = []

        def _distinct(col: str, extra: str = "") -> list[str]:
            sql = f"""
                SELECT DISTINCT g.{col}
                FROM   grants_fts
                JOIN   grants g ON grants_fts.rowid = g.id
                WHERE  grants_fts MATCH ?
                       {source_clause}
                       {extra}
                ORDER  BY g.{col}
            """
            rows = self._conn.execute(sql, [query] + source_params).fetchall()
            return [r[0] for r in rows if r[0] is not None]

        return GrantFacets(
            sources=_distinct("source"),
            programmes=_distinct("source_programme", "AND g.source_programme IS NOT NULL"),
            countries=_distinct("country", "AND g.country IS NOT NULL"),
        )
