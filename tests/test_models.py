"""Tests for db/models.py — no live network, no live filesystem beyond tmp_path."""
import io
import json
import sqlite3
import struct
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.models import (
    NIH_COUNTRY_LOOKUP,
    cordis_source_url,
    create_schema,
    get_coordinator,
    iter_csv_lines,
    make_cordis_metadata,
    make_nih_metadata,
    nih_source_url,
    normalize_cordis_decimal,
    normalize_country,
    normalize_nih_date,
    source_programme_from_filename,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_streaming_zip(csv_text: str) -> bytes:
    """Create a minimal streaming-ZIP byte string containing *csv_text*.

    Uses raw DEFLATE (wbits=-15) so iter_csv_lines can decompress it.
    The local file header has the data-descriptor flag (0x0008) set, which
    is exactly the format NIH ExPORTER project ZIPs use.
    """
    raw = csv_text.encode()
    # zlib.compress produces a zlib-wrapped stream; strip the 2-byte header
    # and the 4-byte Adler-32 trailer to get a raw deflate stream.
    compressed = zlib.compress(raw, level=6)[2:-4]

    fname = b"test.csv"
    fname_len = len(fname)
    extra_len = 0

    header = b"PK\x03\x04"
    header += struct.pack("<H", 20)       # version needed to extract
    header += struct.pack("<H", 0x0008)   # flags: data descriptor present
    header += struct.pack("<H", 8)        # compression method: DEFLATE
    header += struct.pack("<H", 0)        # last mod time
    header += struct.pack("<H", 0)        # last mod date
    header += struct.pack("<I", 0)        # CRC-32 (deferred to data descriptor)
    header += struct.pack("<I", 0)        # compressed size (deferred)
    header += struct.pack("<I", 0)        # uncompressed size (deferred)
    header += struct.pack("<H", fname_len)
    header += struct.pack("<H", extra_len)
    header += fname
    return header + compressed


def _fresh_conn() -> sqlite3.Connection:
    return sqlite3.connect(":memory:")


# ---------------------------------------------------------------------------
# 1. Schema creation
# ---------------------------------------------------------------------------


def test_create_schema_grants_table():
    conn = _fresh_conn()
    create_schema(conn)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='grants'"
    ).fetchall()
    assert rows, "grants table should exist after create_schema"


def test_create_schema_fts_table():
    conn = _fresh_conn()
    create_schema(conn)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='grants_fts'"
    ).fetchall()
    assert rows, "grants_fts virtual table should exist after create_schema"


def test_create_schema_idempotent():
    """Calling create_schema twice on the same connection must not raise."""
    conn = _fresh_conn()
    create_schema(conn)
    create_schema(conn)


def test_create_schema_grants_columns():
    conn = _fresh_conn()
    create_schema(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(grants)")}
    expected = {
        "id", "title", "abstract", "start_date", "end_date",
        "funding_amount", "funding_currency", "organization", "country",
        "source", "source_id", "source_programme", "source_url", "metadata",
    }
    assert expected.issubset(cols), f"Missing columns: {expected - cols}"


# ---------------------------------------------------------------------------
# 2. UNIQUE constraint — INSERT OR REPLACE
# ---------------------------------------------------------------------------


def _insert_grant(conn, source="nih", source_id="123", title="Test Grant"):
    conn.execute(
        """
        INSERT OR REPLACE INTO grants
            (title, source, source_id)
        VALUES (?, ?, ?)
        """,
        (title, source, source_id),
    )
    conn.commit()


def test_unique_constraint_raises_on_plain_insert():
    conn = _fresh_conn()
    create_schema(conn)
    _insert_grant(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO grants (title, source, source_id) VALUES ('Dupe', 'nih', '123')"
        )


def test_insert_or_replace_overwrites():
    conn = _fresh_conn()
    create_schema(conn)
    _insert_grant(conn, title="Original")
    _insert_grant(conn, title="Replaced")  # INSERT OR REPLACE
    titles = [r[0] for r in conn.execute("SELECT title FROM grants WHERE source_id='123'")]
    assert titles == ["Replaced"]


def test_unique_different_source_allowed():
    conn = _fresh_conn()
    create_schema(conn)
    _insert_grant(conn, source="nih", source_id="42")
    _insert_grant(conn, source="cordis", source_id="42")
    count = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
    assert count == 2


# ---------------------------------------------------------------------------
# 3. NIH date normalization
# ---------------------------------------------------------------------------


def test_nih_date_mm_dd_yyyy():
    assert normalize_nih_date("09/15/2023") == "2023-09-15"


def test_nih_date_mm_dd_yyyy_leading_zeros():
    assert normalize_nih_date("01/01/2010") == "2010-01-01"


def test_nih_date_iso_passthrough():
    assert normalize_nih_date("2023-09-15") == "2023-09-15"


def test_nih_date_blank_is_none():
    assert normalize_nih_date("") is None
    assert normalize_nih_date("   ") is None


def test_nih_date_none_is_none():
    assert normalize_nih_date(None) is None


def test_nih_date_garbage_is_none():
    assert normalize_nih_date("not-a-date") is None
    assert normalize_nih_date("32/13/2023") is None


def test_nih_date_already_iso_various():
    assert normalize_nih_date("2007-01-01") == "2007-01-01"


# ---------------------------------------------------------------------------
# 4. CORDIS decimal normalization
# ---------------------------------------------------------------------------


def test_cordis_decimal_comma_separator():
    assert normalize_cordis_decimal("2073781,25") == pytest.approx(2073781.25)


def test_cordis_decimal_zero():
    assert normalize_cordis_decimal("0,00") == pytest.approx(0.0)


def test_cordis_decimal_blank_is_none():
    assert normalize_cordis_decimal("") is None
    assert normalize_cordis_decimal("   ") is None


def test_cordis_decimal_none_is_none():
    assert normalize_cordis_decimal(None) is None


def test_cordis_decimal_integer_no_comma():
    assert normalize_cordis_decimal("1000000") == pytest.approx(1000000.0)


def test_cordis_decimal_garbage_is_none():
    assert normalize_cordis_decimal("not-a-number") is None


def test_cordis_decimal_quoted_value():
    # CSV may leave surrounding quotes after a naive split
    assert normalize_cordis_decimal('"2073781,25"') == pytest.approx(2073781.25)


# ---------------------------------------------------------------------------
# 5. NIH streaming ZIP reader
# ---------------------------------------------------------------------------


def test_iter_csv_lines_yields_header_and_rows(tmp_path):
    csv_text = "HEADER1,HEADER2\nrow1a,row1b\nrow2a,row2b\n"
    zip_path = tmp_path / "test.zip"
    zip_path.write_bytes(_make_streaming_zip(csv_text))

    lines = list(iter_csv_lines(zip_path))
    # Strip trailing \r if present (Windows line endings)
    decoded = [ln.rstrip(b"\r").decode() for ln in lines if ln.strip()]
    assert decoded[0] == "HEADER1,HEADER2"
    assert decoded[1] == "row1a,row1b"
    assert decoded[2] == "row2a,row2b"


def test_iter_csv_lines_single_line_no_trailing_newline(tmp_path):
    csv_text = "ONLY_LINE"
    zip_path = tmp_path / "test.zip"
    zip_path.write_bytes(_make_streaming_zip(csv_text))

    lines = list(iter_csv_lines(zip_path))
    assert len(lines) == 1
    assert lines[0].strip() == b"ONLY_LINE"


def test_iter_csv_lines_many_rows(tmp_path):
    rows = "\n".join(f"row{i},value{i}" for i in range(1000)) + "\n"
    zip_path = tmp_path / "test.zip"
    zip_path.write_bytes(_make_streaming_zip(rows))

    lines = [ln for ln in iter_csv_lines(zip_path) if ln.strip()]
    assert len(lines) == 1000


# ---------------------------------------------------------------------------
# 6. NIH country normalization
# ---------------------------------------------------------------------------


def test_country_united_states():
    assert normalize_country("UNITED STATES") == "US"


def test_country_united_kingdom():
    assert normalize_country("UNITED KINGDOM") == "GB"


def test_country_canada():
    assert normalize_country("CANADA") == "CA"


def test_country_australia():
    assert normalize_country("AUSTRALIA") == "AU"


def test_country_germany():
    assert normalize_country("GERMANY") == "DE"


def test_country_france():
    assert normalize_country("FRANCE") == "FR"


def test_country_japan():
    assert normalize_country("JAPAN") == "JP"


def test_country_china():
    assert normalize_country("CHINA") == "CN"


def test_country_israel():
    assert normalize_country("ISRAEL") == "IL"


def test_country_south_korea():
    assert normalize_country("SOUTH KOREA") == "KR"


def test_country_netherlands():
    assert normalize_country("NETHERLANDS") == "NL"


def test_country_sweden():
    assert normalize_country("SWEDEN") == "SE"


def test_country_switzerland():
    assert normalize_country("SWITZERLAND") == "CH"


def test_country_italy():
    assert normalize_country("ITALY") == "IT"


def test_country_spain():
    assert normalize_country("SPAIN") == "ES"


def test_country_brazil():
    assert normalize_country("BRAZIL") == "BR"


def test_country_india():
    assert normalize_country("INDIA") == "IN"


def test_country_mexico():
    assert normalize_country("MEXICO") == "MX"


def test_country_south_africa():
    assert normalize_country("SOUTH AFRICA") == "ZA"


def test_country_unknown_returns_none(capsys):
    result = normalize_country("NONEXISTENTLAND")
    assert result is None
    captured = capsys.readouterr()
    assert "NONEXISTENTLAND" in captured.err


def test_country_unknown_warning_on_stderr(capsys):
    normalize_country("FANTASYLAND")
    captured = capsys.readouterr()
    assert "FANTASYLAND" in captured.err


def test_country_lookup_dict_has_all_required():
    required = {
        "UNITED STATES", "CANADA", "UNITED KINGDOM", "AUSTRALIA",
        "GERMANY", "FRANCE", "JAPAN", "CHINA", "ISRAEL", "SOUTH KOREA",
        "NETHERLANDS", "SWEDEN", "SWITZERLAND", "ITALY", "SPAIN",
        "BRAZIL", "INDIA", "MEXICO", "SOUTH AFRICA",
    }
    missing = required - set(NIH_COUNTRY_LOOKUP.keys())
    assert not missing, f"Missing required entries: {missing}"


# ---------------------------------------------------------------------------
# 7. CORDIS coordinator join
# ---------------------------------------------------------------------------


def test_coordinator_found():
    orgs = [
        {"name": "Participant Corp", "country": "DE", "role": "participant"},
        {"name": "Lead University", "country": "FR", "role": "coordinator"},
    ]
    name, country = get_coordinator(orgs, project_id="99")
    assert name == "Lead University"
    assert country == "FR"


def test_coordinator_missing_returns_none_with_warning(capsys):
    orgs = [
        {"name": "Only Participant", "country": "IT", "role": "participant"},
    ]
    name, country = get_coordinator(orgs, project_id="77")
    assert name is None
    assert country is None
    captured = capsys.readouterr()
    assert "77" in captured.err  # warning includes the project_id


def test_coordinator_empty_orgs_returns_none(capsys):
    name, country = get_coordinator([], project_id="55")
    assert name is None
    assert country is None


def test_coordinator_case_insensitive_role(capsys):
    """role field should match 'coordinator' case-insensitively."""
    orgs = [{"name": "UniLab", "country": "SE", "role": "Coordinator"}]
    name, country = get_coordinator(orgs, project_id="11")
    assert name == "UniLab"
    assert country == "SE"


# ---------------------------------------------------------------------------
# 8. source_programme derivation
# ---------------------------------------------------------------------------


def test_programme_fp7():
    assert source_programme_from_filename("cordis-fp7projects-csv.zip") == "fp7"


def test_programme_h2020():
    assert source_programme_from_filename("cordis-h2020projects-csv.zip") == "h2020"


def test_programme_horizon_europe():
    assert source_programme_from_filename("cordis-HORIZONprojects-csv.zip") == "horizon_europe"


def test_programme_full_path():
    """Should work when given a full path, not just the basename."""
    assert source_programme_from_filename(
        "/data/cordis/horizon_europe/cordis-HORIZONprojects-csv.zip"
    ) == "horizon_europe"


# ---------------------------------------------------------------------------
# 9. FTS5 rebuild
# ---------------------------------------------------------------------------


def test_fts5_match_after_rebuild():
    conn = _fresh_conn()
    create_schema(conn)
    conn.execute(
        """
        INSERT INTO grants (title, abstract, source, source_id)
        VALUES ('Climate Change Adaptation', 'A study on adaptation strategies', 'cordis', 'C1')
        """
    )
    conn.execute(
        """
        INSERT INTO grants (title, abstract, source, source_id)
        VALUES ('Machine Learning Genomics', 'Deep learning for gene expression', 'nih', 'N1')
        """
    )
    conn.commit()
    conn.execute("INSERT INTO grants_fts(grants_fts) VALUES('rebuild')")
    conn.commit()

    rows = conn.execute(
        "SELECT grants.title FROM grants_fts JOIN grants ON grants_fts.rowid = grants.id WHERE grants_fts MATCH 'adaptation'"
    ).fetchall()
    titles = [r[0] for r in rows]
    assert "Climate Change Adaptation" in titles


def test_fts5_match_on_abstract():
    conn = _fresh_conn()
    create_schema(conn)
    conn.execute(
        """
        INSERT INTO grants (title, abstract, source, source_id)
        VALUES ('Some Grant', 'Neural networks for protein folding', 'nih', 'N2')
        """
    )
    conn.commit()
    conn.execute("INSERT INTO grants_fts(grants_fts) VALUES('rebuild')")
    conn.commit()

    rows = conn.execute(
        "SELECT grants.title FROM grants_fts JOIN grants ON grants_fts.rowid = grants.id WHERE grants_fts MATCH 'protein'"
    ).fetchall()
    assert rows, "FTS search on abstract should return a result"


def test_fts5_no_match_returns_empty():
    conn = _fresh_conn()
    create_schema(conn)
    conn.execute(
        "INSERT INTO grants (title, abstract, source, source_id) VALUES ('Quantum Computing', NULL, 'nih', 'N3')"
    )
    conn.commit()
    conn.execute("INSERT INTO grants_fts(grants_fts) VALUES('rebuild')")

    rows = conn.execute(
        "SELECT grants.title FROM grants_fts JOIN grants ON grants_fts.rowid = grants.id WHERE grants_fts MATCH 'biology'"
    ).fetchall()
    assert rows == []


# ---------------------------------------------------------------------------
# 10. metadata JSON structure
# ---------------------------------------------------------------------------


def test_nih_metadata_all_keys_present():
    row = {
        "ACTIVITY": "R01",
        "IC_NAME": "NATIONAL CANCER INSTITUTE",
        "CORE_PROJECT_NUM": "R01CA123456",
        "PI_NAMEs": "SMITH, JOHN",
        "FY": "2025",
    }
    meta = make_nih_metadata(row)
    assert set(meta.keys()) == {"activity_code", "ic_name", "core_project_num", "pi_names", "fy"}


def test_nih_metadata_values_mapped_correctly():
    row = {
        "ACTIVITY": "R01",
        "IC_NAME": "NATIONAL CANCER INSTITUTE",
        "CORE_PROJECT_NUM": "R01CA123456",
        "PI_NAMEs": "SMITH, JOHN; DOE, JANE",
        "FY": "2025",
    }
    meta = make_nih_metadata(row)
    assert meta["activity_code"] == "R01"
    assert meta["ic_name"] == "NATIONAL CANCER INSTITUTE"
    assert meta["core_project_num"] == "R01CA123456"
    assert meta["pi_names"] == "SMITH, JOHN; DOE, JANE"
    assert meta["fy"] == 2025


def test_nih_metadata_missing_fields_produce_none():
    meta = make_nih_metadata({})
    assert meta["activity_code"] is None
    assert meta["ic_name"] is None
    assert meta["core_project_num"] is None
    assert meta["pi_names"] is None
    assert meta["fy"] is None


def test_nih_metadata_fy_is_int_when_present():
    row = {"FY": "2024"}
    meta = make_nih_metadata(row)
    assert isinstance(meta["fy"], int)
    assert meta["fy"] == 2024


def test_nih_metadata_fy_none_when_non_numeric():
    row = {"FY": "abc"}
    meta = make_nih_metadata(row)
    assert meta["fy"] is None


def test_cordis_metadata_all_keys_present():
    row = {
        "acronym": "SolDAC",
        "topics": "HORIZON-CL5-2021-D2-01-11",
        "status": "SIGNED",
        "ecSignatureDate": "2022-05-12",
        "keywords": "solar energy",
    }
    meta = make_cordis_metadata(row)
    assert set(meta.keys()) == {"acronym", "topics", "status", "ec_signature_date", "keywords"}


def test_cordis_metadata_values_mapped_correctly():
    row = {
        "acronym": "SolDAC",
        "topics": "HORIZON-CL5-2021-D2-01-11",
        "status": "SIGNED",
        "ecSignatureDate": "2022-05-12",
        "keywords": "solar energy",
    }
    meta = make_cordis_metadata(row)
    assert meta["acronym"] == "SolDAC"
    assert meta["topics"] == "HORIZON-CL5-2021-D2-01-11"
    assert meta["status"] == "SIGNED"
    assert meta["ec_signature_date"] == "2022-05-12"
    assert meta["keywords"] == "solar energy"


def test_cordis_metadata_missing_fields_produce_none():
    meta = make_cordis_metadata({})
    assert meta["acronym"] is None
    assert meta["topics"] is None
    assert meta["status"] is None
    assert meta["ec_signature_date"] is None
    assert meta["keywords"] is None


# ---------------------------------------------------------------------------
# 11. source_url construction
# ---------------------------------------------------------------------------


def test_nih_source_url():
    assert nih_source_url("12345678") == "https://reporter.nih.gov/project-details/12345678"


def test_nih_source_url_numeric_id():
    assert nih_source_url(99999) == "https://reporter.nih.gov/project-details/99999"


def test_cordis_source_url():
    assert cordis_source_url("101084642") == "https://cordis.europa.eu/project/id/101084642"


def test_cordis_source_url_numeric_id():
    assert cordis_source_url(888888) == "https://cordis.europa.eu/project/id/888888"
