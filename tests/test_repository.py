"""Tests for db/repository.py — interface contract only; no SQLite I/O.

Covers:
- Grant and GrantPage dataclass construction and field access
- Mutable-default guard: metadata default is not shared across instances
- GrantRepository Protocol structural subtyping (runtime_checkable)
- Validation rules exercised via a minimal stub implementation
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.repository import (
    MAX_PAGE_SIZE,
    Grant,
    GrantPage,
    GrantRepository,
)


# ---------------------------------------------------------------------------
# Helpers — minimal stub (no inheritance) for Protocol structural checks
# ---------------------------------------------------------------------------


def _make_grant(**kwargs) -> Grant:
    """Return a Grant with sensible defaults for fields not under test."""
    defaults = dict(
        id=1,
        title="Test Grant",
        abstract=None,
        start_date=None,
        end_date=None,
        funding_amount=None,
        funding_currency=None,
        organization=None,
        country=None,
        source="nih",
        source_id="ABC123",
        source_programme=None,
        source_url=None,
    )
    defaults.update(kwargs)
    return Grant(**defaults)


VALID_SOURCES = {"nih", "cordis", None}


class _StubRepository:
    """Minimal stub that structurally satisfies GrantRepository.

    Implements the validation rules from the contract so the validation
    tests can be exercised at the protocol level without a live DB.

    Does NOT inherit from GrantRepository — structural subtyping only.
    """

    def _validate(
        self, source: str | None, limit: int, offset: int
    ) -> None:
        if source not in VALID_SOURCES:
            raise ValueError(f"Unrecognized source: {source!r}")
        if limit <= 0:
            raise ValueError(f"limit must be positive, got {limit}")
        if offset < 0:
            raise ValueError(f"offset must be >= 0, got {offset}")

    def search(
        self,
        query: str,
        *,
        source: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> GrantPage:
        self._validate(source, limit, offset)
        effective_limit = min(limit, MAX_PAGE_SIZE)
        return GrantPage(items=[], total=0, offset=offset, limit=effective_limit)

    def list_grants(
        self,
        *,
        source: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> GrantPage:
        self._validate(source, limit, offset)
        effective_limit = min(limit, MAX_PAGE_SIZE)
        return GrantPage(items=[], total=0, offset=offset, limit=effective_limit)

    def get_by_id(self, grant_id: int) -> Grant | None:
        return None

    def get_by_source(self, source: str, source_id: str) -> Grant | None:
        return None


# ---------------------------------------------------------------------------
# 1. Grant dataclass construction
# ---------------------------------------------------------------------------


def test_grant_basic_construction():
    g = _make_grant()
    assert g.id == 1
    assert g.title == "Test Grant"
    assert g.source == "nih"
    assert g.source_id == "ABC123"


def test_grant_metadata_default_is_empty_dict():
    g = _make_grant()
    assert g.metadata == {}
    assert isinstance(g.metadata, dict)


def test_grant_metadata_default_not_shared_across_instances():
    """The metadata default must use field(default_factory=dict), not a literal {}."""
    g1 = _make_grant()
    g2 = _make_grant()
    g1.metadata["key"] = "value"
    assert "key" not in g2.metadata, (
        "metadata default is a shared mutable object — use field(default_factory=dict)"
    )


def test_grant_explicit_metadata():
    g = _make_grant(metadata={"activity_code": "R01", "fy": 2024})
    assert g.metadata["activity_code"] == "R01"
    assert g.metadata["fy"] == 2024


def test_grant_all_optional_fields_accept_none():
    g = _make_grant(
        abstract=None,
        start_date=None,
        end_date=None,
        funding_amount=None,
        funding_currency=None,
        organization=None,
        country=None,
        source_programme=None,
        source_url=None,
    )
    assert g.abstract is None
    assert g.start_date is None
    assert g.end_date is None
    assert g.funding_amount is None
    assert g.funding_currency is None
    assert g.organization is None
    assert g.country is None
    assert g.source_programme is None
    assert g.source_url is None


def test_grant_cordis_source():
    g = _make_grant(source="cordis", source_programme="h2020")
    assert g.source == "cordis"
    assert g.source_programme == "h2020"


# ---------------------------------------------------------------------------
# 2. GrantPage dataclass construction
# ---------------------------------------------------------------------------


def test_grant_page_fields_accessible_by_name():
    page = GrantPage(items=[], total=42, offset=0, limit=20)
    assert page.items == []
    assert page.total == 42
    assert page.offset == 0
    assert page.limit == 20


def test_grant_page_total_independent_of_items_length():
    """total reflects all matching rows, not just len(items)."""
    items = [_make_grant(id=i, source_id=f"S{i}") for i in range(1, 4)]
    page = GrantPage(items=items, total=1000, offset=0, limit=3)
    assert len(page.items) == 3
    assert page.total == 1000


def test_grant_page_empty_items_nonzero_total():
    """An offset beyond the last row returns empty items but total > 0."""
    page = GrantPage(items=[], total=50, offset=200, limit=20)
    assert page.items == []
    assert page.total == 50
    assert page.offset == 200


def test_grant_page_zero_total():
    page = GrantPage(items=[], total=0, offset=0, limit=20)
    assert page.total == 0


# ---------------------------------------------------------------------------
# 3. Protocol structural subtyping check
# ---------------------------------------------------------------------------


def test_stub_satisfies_protocol_isinstance():
    """A class with all four methods satisfies isinstance check without inheriting."""
    stub = _StubRepository()
    assert isinstance(stub, GrantRepository), (
        "GrantRepository must be @runtime_checkable and _StubRepository "
        "must structurally satisfy it without inheriting from it"
    )


def test_non_implementing_class_fails_isinstance():
    """A class missing the four methods does NOT satisfy isinstance."""

    class _Empty:
        pass

    assert not isinstance(_Empty(), GrantRepository)


def test_stub_search_returns_grant_page():
    stub = _StubRepository()
    result = stub.search("climate")
    assert isinstance(result, GrantPage)


def test_stub_list_grants_returns_grant_page():
    stub = _StubRepository()
    result = stub.list_grants()
    assert isinstance(result, GrantPage)


def test_stub_get_by_id_returns_none_for_missing():
    stub = _StubRepository()
    assert stub.get_by_id(999) is None


def test_stub_get_by_source_returns_none_for_missing():
    stub = _StubRepository()
    assert stub.get_by_source("nih", "NOTEXIST") is None


# ---------------------------------------------------------------------------
# 4. Source filter validation
# ---------------------------------------------------------------------------


def test_search_valid_source_nih():
    stub = _StubRepository()
    result = stub.search("cancer", source="nih")
    assert isinstance(result, GrantPage)


def test_search_valid_source_cordis():
    stub = _StubRepository()
    result = stub.search("energy", source="cordis")
    assert isinstance(result, GrantPage)


def test_search_valid_source_none_means_all():
    stub = _StubRepository()
    result = stub.search("health", source=None)
    assert isinstance(result, GrantPage)


def test_search_invalid_source_raises_value_error():
    stub = _StubRepository()
    with pytest.raises(ValueError):
        stub.search("cancer", source="pubmed")


def test_list_grants_invalid_source_raises_value_error():
    stub = _StubRepository()
    with pytest.raises(ValueError):
        stub.list_grants(source="unknown_source")


def test_search_empty_string_source_raises_value_error():
    stub = _StubRepository()
    with pytest.raises(ValueError):
        stub.search("test", source="")


# ---------------------------------------------------------------------------
# 5. Offset validation
# ---------------------------------------------------------------------------


def test_search_negative_offset_raises_value_error():
    stub = _StubRepository()
    with pytest.raises(ValueError):
        stub.search("cancer", offset=-1)


def test_list_grants_negative_offset_raises_value_error():
    stub = _StubRepository()
    with pytest.raises(ValueError):
        stub.list_grants(offset=-100)


def test_search_zero_offset_is_valid():
    stub = _StubRepository()
    result = stub.search("cancer", offset=0)
    assert result.offset == 0


def test_list_grants_positive_offset_is_valid():
    stub = _StubRepository()
    result = stub.list_grants(offset=50)
    assert result.offset == 50


# ---------------------------------------------------------------------------
# 6. Limit validation and MAX_PAGE_SIZE clamping
# ---------------------------------------------------------------------------


def test_max_page_size_is_500():
    assert MAX_PAGE_SIZE == 500


def test_search_limit_zero_raises_value_error():
    stub = _StubRepository()
    with pytest.raises(ValueError):
        stub.search("cancer", limit=0)


def test_search_limit_negative_raises_value_error():
    stub = _StubRepository()
    with pytest.raises(ValueError):
        stub.search("cancer", limit=-5)


def test_list_grants_limit_zero_raises_value_error():
    stub = _StubRepository()
    with pytest.raises(ValueError):
        stub.list_grants(limit=0)


def test_search_limit_clamped_to_max_page_size():
    """A limit larger than MAX_PAGE_SIZE is clamped, not rejected."""
    stub = _StubRepository()
    result = stub.search("cancer", limit=MAX_PAGE_SIZE + 100)
    assert result.limit == MAX_PAGE_SIZE


def test_list_grants_limit_clamped_to_max_page_size():
    stub = _StubRepository()
    result = stub.list_grants(limit=MAX_PAGE_SIZE + 1)
    assert result.limit == MAX_PAGE_SIZE


def test_search_limit_exactly_max_page_size_not_clamped():
    stub = _StubRepository()
    result = stub.search("cancer", limit=MAX_PAGE_SIZE)
    assert result.limit == MAX_PAGE_SIZE


def test_search_limit_below_max_page_size_unchanged():
    stub = _StubRepository()
    result = stub.search("cancer", limit=10)
    assert result.limit == 10
