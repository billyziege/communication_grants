"""Tests for db/sqlite_repository.py — SQLiteGrantRepository.

Tests use an in-memory SQLite connection pre-populated via create_schema(conn)
and direct INSERT statements.  No file I/O; no mocking.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.models import create_schema
from db.repository import Grant, GrantPage, GrantRepository, MAX_PAGE_SIZE
from db.sqlite_repository import SQLiteGrantRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_grant(
    conn: sqlite3.Connection,
    *,
    title: str = "Test Grant",
    abstract: str | None = "An abstract about communication",
    source: str = "nih",
    source_id: str = "TEST001",
    start_date: str | None = None,
    end_date: str | None = None,
    funding_amount: float | None = None,
    funding_currency: str | None = None,
    organization: str | None = None,
    country: str | None = None,
    source_programme: str | None = None,
    source_url: str | None = None,
    metadata: dict | None = None,
) -> int:
    metadata_json = json.dumps(metadata) if metadata is not None else None
    cur = conn.execute(
        """
        INSERT INTO grants (
            title, abstract, start_date, end_date,
            funding_amount, funding_currency, organization, country,
            source, source_id, source_programme, source_url, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title, abstract, start_date, end_date,
            funding_amount, funding_currency, organization, country,
            source, source_id, source_programme, source_url, metadata_json,
        ),
    )
    return cur.lastrowid


@pytest.fixture
def conn():
    """In-memory SQLite connection with schema; no rows."""
    c = sqlite3.connect(":memory:")
    create_schema(c)
    return c


@pytest.fixture
def repo(conn):
    """SQLiteGrantRepository with one NIH and one CORDIS row, FTS rebuilt."""
    _insert_grant(
        conn,
        title="Wireless Communication Research",
        abstract="studying radio frequency signals in wireless networks",
        source="nih",
        source_id="NIH001",
    )
    _insert_grant(
        conn,
        title="European Climate Initiative",
        abstract="renewable energy and climate change studies across Europe",
        source="cordis",
        source_id="CORDIS001",
    )
    conn.execute("INSERT INTO grants_fts(grants_fts) VALUES('rebuild')")
    conn.commit()
    return SQLiteGrantRepository(conn)


# ---------------------------------------------------------------------------
# 1. row_factory set internally
# ---------------------------------------------------------------------------


def test_row_factory_set_internally(conn):
    """Repo sets conn.row_factory; get_by_id returns a Grant, not a tuple."""
    # Do NOT set conn.row_factory before constructing — the repo must do it.
    _insert_grant(conn, title="Row Factory Test", source_id="RF001")
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    result = repo.get_by_id(1)
    assert isinstance(result, Grant)
    assert result.title == "Row Factory Test"


# ---------------------------------------------------------------------------
# 2. metadata parsing
# ---------------------------------------------------------------------------


def test_metadata_json_parsed_to_dict(conn):
    """A row with JSON metadata returns Grant.metadata as a dict."""
    meta = {"activity_code": "R01", "fy": 2024}
    _insert_grant(conn, source_id="META001", metadata=meta)
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    grant = repo.get_by_id(1)
    assert isinstance(grant.metadata, dict)
    assert grant.metadata["activity_code"] == "R01"
    assert grant.metadata["fy"] == 2024


def test_metadata_null_returns_empty_dict(conn):
    """A row with NULL metadata returns Grant.metadata == {}."""
    _insert_grant(conn, source_id="META002", metadata=None)
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    grant = repo.get_by_id(1)
    assert grant.metadata == {}
    assert isinstance(grant.metadata, dict)


# ---------------------------------------------------------------------------
# 3. search — returns results
# ---------------------------------------------------------------------------


def test_search_returns_matching_grant(repo):
    """search('Wireless') returns the grant with that term."""
    page = repo.search("Wireless")
    assert page.total >= 1
    assert any("Wireless" in g.title for g in page.items)


def test_search_returns_grant_page(repo):
    page = repo.search("communication")
    assert isinstance(page, GrantPage)
    assert len(page.items) >= 1


# ---------------------------------------------------------------------------
# 4. search — BM25 ordering
# ---------------------------------------------------------------------------


def test_search_bm25_ordering(conn):
    """Better FTS match (more occurrences of the query term) appears first."""
    # Grant A: "satellite" appears many times in both title and abstract → better match
    _insert_grant(
        conn,
        title="Satellite Communication Satellite Study",
        abstract="satellite satellite communication satellite research satellite",
        source="nih",
        source_id="SAT001",
    )
    # Grant B: "satellite" appears only once in abstract
    _insert_grant(
        conn,
        title="Digital Broadcasting Networks",
        abstract="satellite interference in digital broadcasting",
        source="nih",
        source_id="SAT002",
    )
    conn.execute("INSERT INTO grants_fts(grants_fts) VALUES('rebuild')")
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    page = repo.search("satellite")
    assert len(page.items) >= 2
    # Grant A should rank first — more occurrences → lower (more negative) BM25 score
    assert page.items[0].source_id == "SAT001"


# ---------------------------------------------------------------------------
# 5. search — source filter
# ---------------------------------------------------------------------------


def test_search_source_filter_nih_only(repo):
    """source='nih' returns only NIH grants."""
    page = repo.search("communication OR energy OR climate", source="nih")
    assert page.total >= 1
    assert all(g.source == "nih" for g in page.items)


def test_search_source_filter_cordis_only(repo):
    """source='cordis' returns only CORDIS grants."""
    page = repo.search("energy OR climate OR communication", source="cordis")
    assert page.total >= 1
    assert all(g.source == "cordis" for g in page.items)


def test_search_source_filter_none_returns_both(repo):
    """source=None returns grants from all sources."""
    page = repo.search("research OR studies OR communication OR energy", source=None)
    sources = {g.source for g in page.items}
    assert "nih" in sources
    assert "cordis" in sources


def test_search_source_filter_nih_excludes_cordis(repo):
    """source='nih' excludes CORDIS grants even if they match."""
    page = repo.search("energy OR climate OR studies", source="nih")
    assert all(g.source == "nih" for g in page.items)


# ---------------------------------------------------------------------------
# 6. search — total count
# ---------------------------------------------------------------------------


def test_search_total_reflects_all_matching_rows(conn):
    """total reflects all matches, not just the current page."""
    for i in range(10):
        _insert_grant(
            conn,
            title=f"Neural Communication Study {i}",
            abstract="neuroscience communication research data",
            source="nih",
            source_id=f"NEURO{i:03d}",
        )
    conn.execute("INSERT INTO grants_fts(grants_fts) VALUES('rebuild')")
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    page = repo.search("Neural", limit=3, offset=0)
    assert page.total == 10
    assert len(page.items) == 3
    assert page.limit == 3


# ---------------------------------------------------------------------------
# 7. search — empty result
# ---------------------------------------------------------------------------


def test_search_no_match_returns_empty_page(repo):
    """No match → GrantPage(items=[], total=0, ...)."""
    page = repo.search("xyznonexistent99zqq")
    assert page.items == []
    assert page.total == 0
    assert isinstance(page, GrantPage)


# ---------------------------------------------------------------------------
# 8. search — FTS syntax error propagates
# ---------------------------------------------------------------------------


def test_search_fts_syntax_error_propagates(repo):
    """Malformed MATCH expression raises sqlite3.OperationalError."""
    with pytest.raises(sqlite3.OperationalError):
        repo.search("AND OR {{{ invalid")


# ---------------------------------------------------------------------------
# 9. list_grants — ordering
# ---------------------------------------------------------------------------


def test_list_grants_id_asc_ordering(conn):
    """list_grants returns rows in id ASC order regardless of insert order."""
    for sid in ["C", "A", "B"]:
        _insert_grant(conn, title=f"Grant {sid}", source_id=f"ORD{sid}")
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    page = repo.list_grants()
    ids = [g.id for g in page.items]
    assert ids == sorted(ids)
    assert len(ids) == 3


# ---------------------------------------------------------------------------
# 10. list_grants — source filter
# ---------------------------------------------------------------------------


def test_list_grants_source_filter_nih_only(repo):
    """list_grants(source='nih') returns only NIH grants."""
    page = repo.list_grants(source="nih")
    assert page.total >= 1
    assert all(g.source == "nih" for g in page.items)


def test_list_grants_source_filter_cordis_only(repo):
    """list_grants(source='cordis') returns only CORDIS grants."""
    page = repo.list_grants(source="cordis")
    assert page.total >= 1
    assert all(g.source == "cordis" for g in page.items)


def test_list_grants_source_filter_none_returns_all(repo):
    """list_grants(source=None) returns grants from all sources."""
    page = repo.list_grants(source=None)
    sources = {g.source for g in page.items}
    assert "nih" in sources
    assert "cordis" in sources


# ---------------------------------------------------------------------------
# 11. list_grants — pagination
# ---------------------------------------------------------------------------


def test_list_grants_pagination_correct_page(conn):
    """Pagination returns the correct page; total is the unfiltered row count."""
    for i in range(10):
        _insert_grant(conn, title=f"Paged Grant {i}", source_id=f"PAG{i:03d}")
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    page = repo.list_grants(limit=3, offset=3)
    assert len(page.items) == 3
    assert page.total == 10
    assert page.offset == 3
    assert page.limit == 3


def test_list_grants_pagination_first_page(conn):
    for i in range(5):
        _insert_grant(conn, title=f"First Page {i}", source_id=f"FP{i:03d}")
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    page = repo.list_grants(limit=2, offset=0)
    assert len(page.items) == 2
    assert page.total == 5
    assert page.offset == 0


# ---------------------------------------------------------------------------
# 12. list_grants — offset beyond last row
# ---------------------------------------------------------------------------


def test_list_grants_offset_beyond_last_row(conn):
    """Offset past the last row returns items=[], but total is still N."""
    for i in range(5):
        _insert_grant(conn, title=f"Grant {i}", source_id=f"OFG{i:03d}")
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    page = repo.list_grants(limit=10, offset=1000)
    assert page.items == []
    assert page.total == 5


# ---------------------------------------------------------------------------
# 13. get_by_id — found / not found
# ---------------------------------------------------------------------------


def test_get_by_id_found(conn):
    """get_by_id returns the correct Grant for an existing id."""
    _insert_grant(conn, title="Specific Grant Title", source_id="GBI001")
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    grant = repo.get_by_id(1)
    assert grant is not None
    assert isinstance(grant, Grant)
    assert grant.title == "Specific Grant Title"
    assert grant.id == 1
    assert grant.source_id == "GBI001"


def test_get_by_id_not_found(conn):
    """get_by_id returns None for a missing id."""
    repo = SQLiteGrantRepository(conn)
    assert repo.get_by_id(9999) is None


def test_get_by_id_returns_all_fields(conn):
    """get_by_id populates all Grant fields correctly."""
    _insert_grant(
        conn,
        title="Full Field Test",
        abstract="Testing all fields",
        source="cordis",
        source_id="FULL001",
        start_date="2023-01-01",
        end_date="2024-12-31",
        funding_amount=1000000.0,
        funding_currency="EUR",
        organization="Test Org",
        country="DE",
        source_programme="h2020",
        source_url="https://cordis.europa.eu/project/id/999",
        metadata={"acronym": "TEST"},
    )
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    grant = repo.get_by_id(1)
    assert grant.title == "Full Field Test"
    assert grant.abstract == "Testing all fields"
    assert grant.source == "cordis"
    assert grant.source_id == "FULL001"
    assert grant.start_date == "2023-01-01"
    assert grant.end_date == "2024-12-31"
    assert grant.funding_amount == 1000000.0
    assert grant.funding_currency == "EUR"
    assert grant.organization == "Test Org"
    assert grant.country == "DE"
    assert grant.source_programme == "h2020"
    assert grant.source_url == "https://cordis.europa.eu/project/id/999"
    assert grant.metadata == {"acronym": "TEST"}


# ---------------------------------------------------------------------------
# 14. get_by_source — found / not found
# ---------------------------------------------------------------------------


def test_get_by_source_found(conn):
    """get_by_source returns the correct Grant for an existing (source, source_id) pair."""
    _insert_grant(conn, title="NIH Specific", source="nih", source_id="NIH_SPEC_001")
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    grant = repo.get_by_source("nih", "NIH_SPEC_001")
    assert grant is not None
    assert isinstance(grant, Grant)
    assert grant.source == "nih"
    assert grant.source_id == "NIH_SPEC_001"
    assert grant.title == "NIH Specific"


def test_get_by_source_not_found(conn):
    """get_by_source returns None for a missing (source, source_id) pair."""
    repo = SQLiteGrantRepository(conn)
    assert repo.get_by_source("nih", "DOESNOTEXIST") is None


def test_get_by_source_wrong_source_returns_none(conn):
    """get_by_source returns None when source_id exists but source doesn't match."""
    _insert_grant(conn, source="nih", source_id="CROSSSRC001")
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    # source_id exists under 'nih' but not 'cordis'
    assert repo.get_by_source("cordis", "CROSSSRC001") is None


# ---------------------------------------------------------------------------
# 15. Validation — ValueError with correct messages
# ---------------------------------------------------------------------------


def test_validation_negative_offset_search_raises(repo):
    """Negative offset raises ValueError with correct message."""
    with pytest.raises(ValueError, match="offset must be >= 0"):
        repo.search("test", offset=-1)


def test_validation_negative_offset_list_grants_raises(repo):
    with pytest.raises(ValueError, match="offset must be >= 0"):
        repo.list_grants(offset=-5)


def test_validation_zero_limit_search_raises(repo):
    """Zero limit raises ValueError with correct message."""
    with pytest.raises(ValueError, match="limit must be > 0"):
        repo.search("test", limit=0)


def test_validation_zero_limit_list_grants_raises(repo):
    with pytest.raises(ValueError, match="limit must be > 0"):
        repo.list_grants(limit=0)


def test_validation_negative_limit_search_raises(repo):
    """Negative limit raises ValueError with correct message."""
    with pytest.raises(ValueError, match="limit must be > 0"):
        repo.search("test", limit=-5)


def test_validation_negative_limit_list_grants_raises(repo):
    with pytest.raises(ValueError, match="limit must be > 0"):
        repo.list_grants(limit=-1)


def test_validation_unrecognized_source_search_raises(repo):
    """Unrecognized source string raises ValueError with correct message."""
    with pytest.raises(ValueError, match="source must be"):
        repo.search("test", source="pubmed")


def test_validation_unrecognized_source_list_grants_raises(repo):
    with pytest.raises(ValueError, match="source must be"):
        repo.list_grants(source="unknown_source")


def test_validation_empty_string_source_raises(repo):
    """Empty string source raises ValueError."""
    with pytest.raises(ValueError, match="source must be"):
        repo.search("test", source="")


def test_validation_error_message_contains_bad_source(repo):
    """ValueError message includes the offending source value."""
    with pytest.raises(ValueError, match="'pubmed'"):
        repo.list_grants(source="pubmed")


def test_validation_error_message_contains_bad_offset(repo):
    """ValueError message includes the offending offset value."""
    with pytest.raises(ValueError, match="-3"):
        repo.search("test", offset=-3)


def test_validation_error_message_contains_bad_limit(repo):
    """ValueError message includes the offending limit value."""
    with pytest.raises(ValueError, match="-7"):
        repo.list_grants(limit=-7)


# ---------------------------------------------------------------------------
# 16. Validation — MAX_PAGE_SIZE clamping
# ---------------------------------------------------------------------------


def test_search_limit_clamped_to_max_page_size(repo):
    """limit=501 is silently clamped to 500; GrantPage.limit == MAX_PAGE_SIZE."""
    page = repo.search("communication", limit=MAX_PAGE_SIZE + 1)
    assert page.limit == MAX_PAGE_SIZE


def test_list_grants_limit_clamped_to_max_page_size(conn):
    """list_grants with oversized limit returns GrantPage.limit == MAX_PAGE_SIZE."""
    for i in range(3):
        _insert_grant(conn, title=f"Clamp {i}", source_id=f"CL{i:03d}")
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    page = repo.list_grants(limit=MAX_PAGE_SIZE + 1)
    assert page.limit == MAX_PAGE_SIZE


def test_search_limit_exactly_max_page_size_not_clamped(repo):
    """limit == MAX_PAGE_SIZE is accepted unchanged."""
    page = repo.search("communication", limit=MAX_PAGE_SIZE)
    assert page.limit == MAX_PAGE_SIZE


def test_list_grants_limit_below_max_page_size_unchanged(conn):
    _insert_grant(conn, source_id="LIM001")
    conn.commit()
    repo = SQLiteGrantRepository(conn)
    page = repo.list_grants(limit=10)
    assert page.limit == 10


# ---------------------------------------------------------------------------
# 17. Structural subtyping
# ---------------------------------------------------------------------------


def test_isinstance_grant_repository_without_inheritance(repo):
    """SQLiteGrantRepository satisfies GrantRepository Protocol without inheriting."""
    assert isinstance(repo, GrantRepository), (
        "SQLiteGrantRepository must structurally satisfy GrantRepository "
        "without inheriting from it"
    )


def test_sqlite_repository_does_not_inherit_grant_repository():
    """Confirm SQLiteGrantRepository does not explicitly inherit from GrantRepository."""
    assert GrantRepository not in SQLiteGrantRepository.__mro__
