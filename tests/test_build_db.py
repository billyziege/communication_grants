"""Tests for db/build_db.py — no live network, all I/O uses tmp_path.

Field-name decisions for NIH gap-fill (§7.1 provisional):
  - Top-level fields used: project_title, abstract_text, project_start_date,
    project_end_date, award_amount, appl_id, activity_code, core_project_num,
    fiscal_year.
  - org_name / org_country: tried first under a nested ``organization`` dict
    (org_name, org_country keys), then as flat fields.
  - ic_name: tried from ``agency_ic_admin.abbreviation``, then flat ``ic_name``.
  - pi_names: list of dicts with ``last_name`` / ``first_name`` keys, joined as
    "LAST, FIRST; LAST, FIRST".
"""

from __future__ import annotations

import csv
import io
import json
import re
import shutil
import sqlite3
import struct
import sys
import zipfile
import zlib
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.build_db import (
    _count_existing_grants,
    _handle_overwrite,
    _load_abstract_dict,
    _load_cordis_org_dict,
    _load_cordis_programme,
    _load_gap_fill_year,
    _load_nih_exporter_year,
    _make_gap_fill_metadata,
    build,
)
from db.models import create_schema


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_streaming_zip(csv_text: str) -> bytes:
    """NIH-style streaming DEFLATE ZIP (data-descriptor flag 0x0008 set)."""
    raw = csv_text.encode()
    compressed = zlib.compress(raw, level=6)[2:-4]  # strip zlib header + Adler32
    fname = b"test.csv"
    header = b"PK\x03\x04"
    header += struct.pack("<H", 20)      # version needed
    header += struct.pack("<H", 0x0008)  # data-descriptor flag
    header += struct.pack("<H", 8)       # DEFLATE
    header += struct.pack("<H", 0)       # mod time
    header += struct.pack("<H", 0)       # mod date
    header += struct.pack("<I", 0)       # CRC-32 (deferred)
    header += struct.pack("<I", 0)       # compressed size (deferred)
    header += struct.pack("<I", 0)       # uncompressed size (deferred)
    header += struct.pack("<H", len(fname))
    header += struct.pack("<H", 0)       # extra len
    header += fname
    return header + compressed


def _make_cordis_zip(project_rows: list[dict], org_rows: list[dict]) -> bytes:
    """Standard CORDIS ZIP with project.csv and organization.csv (delimiter=';')."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # organization.csv
        org_buf = StringIO()
        if org_rows:
            writer = csv.DictWriter(org_buf, fieldnames=list(org_rows[0].keys()), delimiter=";")
            writer.writeheader()
            writer.writerows(org_rows)
        zf.writestr("organization.csv", org_buf.getvalue())

        # project.csv
        prj_buf = StringIO()
        if project_rows:
            writer = csv.DictWriter(prj_buf, fieldnames=list(project_rows[0].keys()), delimiter=";")
            writer.writeheader()
            writer.writerows(project_rows)
        zf.writestr("project.csv", prj_buf.getvalue())

    return buf.getvalue()


def _make_abs_zip(rows: list[dict]) -> bytes:
    """Standard NIH abstract ZIP with one CSV inside."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        csv_buf = StringIO()
        if rows:
            writer = csv.DictWriter(csv_buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        zf.writestr("RePORTER_PRJABS_C_FY2023.csv", csv_buf.getvalue())
    return buf.getvalue()


def _fresh_db(path: Path) -> sqlite3.Connection:
    """Return an open connection to a newly-schema'd SQLite DB at path."""
    conn = sqlite3.connect(str(path))
    create_schema(conn)
    return conn


def _db_with_grants(path: Path, n: int = 1) -> None:
    """Write n rows to the grants table in path."""
    conn = _fresh_db(path)
    for i in range(n):
        conn.execute(
            "INSERT INTO grants (title, source, source_id) VALUES (?, 'nih', ?)",
            (f"Grant {i}", str(i)),
        )
    conn.commit()
    conn.close()


def _make_manifest(
    data_dir: Path,
    cordis_programmes: list[dict] | None = None,
    nih_files: list[dict] | None = None,
    gap_fill_files: list[dict] | None = None,
) -> dict:
    manifest = {
        "schema_version": 1,
        "cordis": {"programmes": cordis_programmes or []},
        "nih_exporter": {"files": nih_files or []},
        "nih_gap_fill": {"fiscal_years": [], "files": gap_fill_files or []},
    }
    (data_dir / "manifest.json").write_text(json.dumps(manifest))
    return manifest


# ---------------------------------------------------------------------------
# 1. _count_existing_grants
# ---------------------------------------------------------------------------


def test_count_no_db(tmp_path):
    assert _count_existing_grants(tmp_path / "nope.db") == 0


def test_count_empty_db(tmp_path):
    db = tmp_path / "empty.db"
    conn = _fresh_db(db)
    conn.close()
    assert _count_existing_grants(db) == 0


def test_count_no_table(tmp_path):
    db = tmp_path / "notbl.db"
    sqlite3.connect(str(db)).close()
    assert _count_existing_grants(db) == 0


def test_count_with_rows(tmp_path):
    db = tmp_path / "rows.db"
    _db_with_grants(db, 3)
    assert _count_existing_grants(db) == 3


# ---------------------------------------------------------------------------
# 2. _handle_overwrite — prompt triggering
# ---------------------------------------------------------------------------


def test_no_prompt_when_no_db(tmp_path):
    """Missing DB → no prompt."""
    with patch("builtins.input") as mock_input:
        _handle_overwrite(tmp_path / "nope.db", want_backup=False)
    mock_input.assert_not_called()


def test_no_prompt_when_zero_rows(tmp_path):
    """DB with 0 rows → no prompt."""
    db = tmp_path / "empty.db"
    conn = _fresh_db(db)
    conn.close()
    with patch("builtins.input") as mock_input:
        _handle_overwrite(db, want_backup=False)
    mock_input.assert_not_called()


def test_prompt_when_has_rows(tmp_path):
    """DB with ≥1 rows → prompt is shown."""
    db = tmp_path / "data.db"
    _db_with_grants(db, 5)
    with patch("builtins.input"):
        with patch("builtins.print") as mock_print:
            _handle_overwrite(db, want_backup=False)
    mock_print.assert_called()


# ---------------------------------------------------------------------------
# 3. _handle_overwrite — prompt text
# ---------------------------------------------------------------------------


def test_prompt_text_with_explicit_backup_path(tmp_path, capsys):
    """With explicit --backup-db PATH: prompt mentions backup path; no --backup-db hint."""
    db = tmp_path / "data.db"
    backup = tmp_path / "data.db.bak"
    _db_with_grants(db, 2)
    with patch("builtins.input"):
        with patch("shutil.copy2"):
            _handle_overwrite(db, want_backup=True, explicit_backup_path=backup)
    out = capsys.readouterr().out
    assert str(backup) in out
    assert "--backup-db" not in out


def test_prompt_text_without_backup(tmp_path, capsys):
    """Without --backup-db: prompt includes abort hint."""
    db = tmp_path / "data.db"
    _db_with_grants(db, 1)
    with patch("builtins.input"):
        _handle_overwrite(db, want_backup=False)
    out = capsys.readouterr().out
    assert "You can abort and rerun with --backup-db to preserve current state." in out


def test_prompt_text_includes_grant_count(tmp_path, capsys):
    db = tmp_path / "data.db"
    _db_with_grants(db, 42)
    with patch("builtins.input"):
        _handle_overwrite(db, want_backup=False)
    out = capsys.readouterr().out
    assert "42" in out


# ---------------------------------------------------------------------------
# 4. _handle_overwrite — backup execution
# ---------------------------------------------------------------------------


def test_backup_performed_after_input(tmp_path):
    """shutil.copy2 is called AFTER input() returns, not before."""
    db = tmp_path / "data.db"
    backup = tmp_path / "data.db.bak"
    _db_with_grants(db, 1)

    call_order: list[str] = []

    with patch("builtins.input", side_effect=lambda: call_order.append("input")):
        with patch("shutil.copy2", side_effect=lambda *a: call_order.append("copy2")):
            _handle_overwrite(db, want_backup=True, explicit_backup_path=backup)

    assert call_order == ["input", "copy2"], f"Expected [input, copy2] but got {call_order}"


def test_backup_explicit_path_passed_to_copy2(tmp_path):
    """shutil.copy2 is called with the explicit backup path."""
    db = tmp_path / "data.db"
    backup = tmp_path / "my_backup.db"
    _db_with_grants(db, 1)

    with patch("builtins.input"):
        with patch("shutil.copy2") as mock_copy:
            _handle_overwrite(db, want_backup=True, explicit_backup_path=backup)

    mock_copy.assert_called_once()
    args = mock_copy.call_args[0]
    assert Path(args[1]) == backup


def test_backup_autoname_follows_pattern(tmp_path):
    """Auto-name backup path matches {db_path}.{YYYYMMDDHHMMSS}.bak."""
    db = tmp_path / "data.db"
    _db_with_grants(db, 1)

    captured: list[tuple] = []

    with patch("builtins.input"):
        with patch("shutil.copy2", side_effect=lambda src, dst: captured.append((src, dst))):
            _handle_overwrite(db, want_backup=True, explicit_backup_path=None)

    assert captured, "shutil.copy2 was never called"
    actual_backup = str(captured[0][1])
    # Pattern: {db_path}.{14 digits}.bak
    assert re.match(r".*\.\d{14}\.bak$", actual_backup), (
        f"Auto-name does not match pattern: {actual_backup}"
    )
    assert actual_backup.startswith(str(db) + ".")


def test_no_backup_without_flag(tmp_path):
    """When want_backup=False, shutil.copy2 is never called."""
    db = tmp_path / "data.db"
    _db_with_grants(db, 1)
    with patch("builtins.input"):
        with patch("shutil.copy2") as mock_copy:
            _handle_overwrite(db, want_backup=False)
    mock_copy.assert_not_called()


# ---------------------------------------------------------------------------
# 5. _load_cordis_org_dict
# ---------------------------------------------------------------------------


def test_cordis_org_dict_finds_coordinator(tmp_path):
    org_rows = [
        {"projectID": "101", "name": "Lead Uni", "country": "FR", "role": "coordinator"},
        {"projectID": "101", "name": "Partner Corp", "country": "DE", "role": "participant"},
    ]
    zip_bytes = _make_cordis_zip([], org_rows)
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        result = _load_cordis_org_dict(zf)
    assert "101" in result
    name, country = result["101"]
    assert name == "Lead Uni"
    assert country == "FR"


def test_cordis_org_dict_ignores_participants(tmp_path):
    org_rows = [
        {"projectID": "200", "name": "Only Participant", "country": "IT", "role": "participant"},
    ]
    zip_bytes = _make_cordis_zip([], org_rows)
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        result = _load_cordis_org_dict(zf)
    # No coordinator found → entry may or may not be in dict, but name/country are None
    name, country = result.get("200", (None, None))
    assert name is None


# ---------------------------------------------------------------------------
# 6. _load_cordis_programme
# ---------------------------------------------------------------------------


CORDIS_PROJECT_ROW = {
    "id": "101084642",
    "acronym": "TESTPROJECT",
    "status": "SIGNED",
    "title": "Test CORDIS Project",
    "startDate": "2022-01-01",
    "endDate": "2025-12-31",
    "totalCost": "3000000",
    "ecMaxContribution": "2500000,00",
    "objective": "Research into communication.",
    "topics": "HORIZON-CL5",
    "ecSignatureDate": "2022-01-15",
    "keywords": "communication; grants",
}

CORDIS_ORG_ROW = {
    "projectID": "101084642",
    "name": "Example University",
    "shortName": "ExUni",
    "country": "NL",
    "role": "coordinator",
    "type": "HES",
}


def test_cordis_programme_inserts_row(tmp_path):
    zip_path = tmp_path / "cordis-h2020projects-csv.zip"
    zip_path.write_bytes(_make_cordis_zip([CORDIS_PROJECT_ROW], [CORDIS_ORG_ROW]))

    db = tmp_path / "test.db"
    conn = _fresh_db(db)
    errors: list = []
    n = _load_cordis_programme(conn, zip_path, errors)
    assert n == 1
    assert errors == []


def test_cordis_programme_coordinator_join(tmp_path):
    zip_path = tmp_path / "cordis-h2020projects-csv.zip"
    zip_path.write_bytes(_make_cordis_zip([CORDIS_PROJECT_ROW], [CORDIS_ORG_ROW]))

    db = tmp_path / "test.db"
    conn = _fresh_db(db)
    _load_cordis_programme(conn, zip_path, [])

    row = conn.execute(
        "SELECT organization, country FROM grants WHERE source_id=?",
        ("101084642",),
    ).fetchone()
    assert row is not None
    assert row[0] == "Example University"
    assert row[1] == "NL"


def test_cordis_programme_source_programme_from_filename(tmp_path):
    zip_path = tmp_path / "cordis-fp7projects-csv.zip"
    zip_path.write_bytes(_make_cordis_zip([CORDIS_PROJECT_ROW], [CORDIS_ORG_ROW]))

    db = tmp_path / "test.db"
    conn = _fresh_db(db)
    _load_cordis_programme(conn, zip_path, [])

    row = conn.execute(
        "SELECT source_programme FROM grants WHERE source_id=?",
        ("101084642",),
    ).fetchone()
    assert row is not None
    assert row[0] == "fp7"


def test_cordis_programme_funding_amount(tmp_path):
    zip_path = tmp_path / "cordis-h2020projects-csv.zip"
    zip_path.write_bytes(_make_cordis_zip([CORDIS_PROJECT_ROW], [CORDIS_ORG_ROW]))

    db = tmp_path / "test.db"
    conn = _fresh_db(db)
    _load_cordis_programme(conn, zip_path, [])

    row = conn.execute(
        "SELECT funding_amount, funding_currency FROM grants WHERE source_id=?",
        ("101084642",),
    ).fetchone()
    assert row is not None
    assert abs(row[0] - 2500000.0) < 0.01
    assert row[1] == "EUR"


def test_cordis_programme_blank_amount_gives_null(tmp_path):
    project_row = {**CORDIS_PROJECT_ROW, "id": "999", "ecMaxContribution": ""}
    zip_path = tmp_path / "cordis-h2020projects-csv.zip"
    zip_path.write_bytes(_make_cordis_zip([project_row], [
        {**CORDIS_ORG_ROW, "projectID": "999"}
    ]))

    db = tmp_path / "test.db"
    conn = _fresh_db(db)
    _load_cordis_programme(conn, zip_path, [])

    row = conn.execute(
        "SELECT funding_amount, funding_currency FROM grants WHERE source_id=?",
        ("999",),
    ).fetchone()
    assert row is not None
    assert row[0] is None
    assert row[1] is None


def test_cordis_programme_uses_insert_or_replace(tmp_path):
    zip_path = tmp_path / "cordis-h2020projects-csv.zip"
    zip_path.write_bytes(_make_cordis_zip([CORDIS_PROJECT_ROW], [CORDIS_ORG_ROW]))

    db = tmp_path / "test.db"
    conn = _fresh_db(db)
    _load_cordis_programme(conn, zip_path, [])
    _load_cordis_programme(conn, zip_path, [])  # second run

    count = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
    assert count == 1, f"INSERT OR REPLACE failed; got {count} rows instead of 1"


# ---------------------------------------------------------------------------
# 7. _load_abstract_dict
# ---------------------------------------------------------------------------


def test_load_abstract_dict_basic(tmp_path):
    rows = [
        {"APPLICATION_ID": "11111111", "ABSTRACT_TEXT": "Abstract text here."},
        {"APPLICATION_ID": "22222222", "ABSTRACT_TEXT": "Another abstract."},
    ]
    abs_zip = tmp_path / "abs.zip"
    abs_zip.write_bytes(_make_abs_zip(rows))

    result = _load_abstract_dict(abs_zip)
    assert result["11111111"] == "Abstract text here."
    assert result["22222222"] == "Another abstract."


def test_load_abstract_dict_empty(tmp_path):
    abs_zip = tmp_path / "abs.zip"
    abs_zip.write_bytes(_make_abs_zip([]))
    assert _load_abstract_dict(abs_zip) == {}


# ---------------------------------------------------------------------------
# 8. _load_nih_exporter_year
# ---------------------------------------------------------------------------


NIH_PROJECT_CSV = (
    "APPLICATION_ID,PROJECT_TITLE,PROJECT_START,PROJECT_END,"
    "TOTAL_COST,ORG_NAME,ORG_COUNTRY,ACTIVITY,IC_NAME,CORE_PROJECT_NUM,PI_NAMEs,FY\n"
    "12345678,NIH Test Grant,09/01/2022,08/31/2023,"
    "500000,Test University,UNITED STATES,R01,NATIONAL CANCER INSTITUTE,R01CA123456,"
    "SMITH JOHN,2022\n"
)

NIH_ABS_ROWS = [
    {"APPLICATION_ID": "12345678", "ABSTRACT_TEXT": "This is the abstract."}
]


def _make_nih_fixture(tmp_path: Path) -> tuple[Path, dict]:
    """Write NIH project/abstract ZIPs and return (data_dir, file_entry)."""
    data_dir = tmp_path / "data"
    exporter_dir = data_dir / "nih" / "exporter"
    exporter_dir.mkdir(parents=True)

    prj_path = exporter_dir / "RePORTER_PRJ_C_FY2022.zip"
    abs_path = exporter_dir / "RePORTER_PRJABS_C_FY2022.zip"

    prj_path.write_bytes(_make_streaming_zip(NIH_PROJECT_CSV))
    abs_path.write_bytes(_make_abs_zip(NIH_ABS_ROWS))

    file_entry = {
        "fiscal_year": 2022,
        "project_file": "nih/exporter/RePORTER_PRJ_C_FY2022.zip",
        "abstract_file": "nih/exporter/RePORTER_PRJABS_C_FY2022.zip",
        "status": "ok",
    }
    return data_dir, file_entry


def test_nih_exporter_inserts_row(tmp_path):
    data_dir, file_entry = _make_nih_fixture(tmp_path)
    db = tmp_path / "test.db"
    conn = _fresh_db(db)
    errors: list = []
    n = _load_nih_exporter_year(conn, data_dir, file_entry, errors)
    assert n == 1
    assert errors == []


def test_nih_exporter_abstract_joined(tmp_path):
    data_dir, file_entry = _make_nih_fixture(tmp_path)
    db = tmp_path / "test.db"
    conn = _fresh_db(db)
    _load_nih_exporter_year(conn, data_dir, file_entry, [])

    row = conn.execute(
        "SELECT abstract FROM grants WHERE source_id=?", ("12345678",)
    ).fetchone()
    assert row is not None
    assert row[0] == "This is the abstract."


def test_nih_exporter_normalize_country_called(tmp_path):
    """normalize_country is called for ORG_COUNTRY and produces ISO alpha-2."""
    data_dir, file_entry = _make_nih_fixture(tmp_path)
    db = tmp_path / "test.db"
    conn = _fresh_db(db)
    _load_nih_exporter_year(conn, data_dir, file_entry, [])

    row = conn.execute(
        "SELECT country FROM grants WHERE source_id=?", ("12345678",)
    ).fetchone()
    assert row is not None
    assert row[0] == "US"  # normalize_country("UNITED STATES") == "US"


def test_nih_exporter_start_date_normalized(tmp_path):
    data_dir, file_entry = _make_nih_fixture(tmp_path)
    db = tmp_path / "test.db"
    conn = _fresh_db(db)
    _load_nih_exporter_year(conn, data_dir, file_entry, [])

    row = conn.execute(
        "SELECT start_date FROM grants WHERE source_id=?", ("12345678",)
    ).fetchone()
    assert row is not None
    assert row[0] == "2022-09-01"


def test_nih_exporter_source_values(tmp_path):
    data_dir, file_entry = _make_nih_fixture(tmp_path)
    db = tmp_path / "test.db"
    conn = _fresh_db(db)
    _load_nih_exporter_year(conn, data_dir, file_entry, [])

    row = conn.execute(
        "SELECT source, source_id, source_programme, funding_currency FROM grants WHERE source_id=?",
        ("12345678",),
    ).fetchone()
    assert row is not None
    assert row[0] == "nih"
    assert row[1] == "12345678"
    assert row[2] is None   # NIH ExPORTER has no source_programme
    assert row[3] == "USD"


def test_nih_exporter_idempotent(tmp_path):
    data_dir, file_entry = _make_nih_fixture(tmp_path)
    db = tmp_path / "test.db"
    conn = _fresh_db(db)
    _load_nih_exporter_year(conn, data_dir, file_entry, [])
    _load_nih_exporter_year(conn, data_dir, file_entry, [])  # second run

    count = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
    assert count == 1, "INSERT OR REPLACE should not double the rows"


# ---------------------------------------------------------------------------
# 9. _make_gap_fill_metadata
# ---------------------------------------------------------------------------


def test_gap_fill_metadata_flat_fields():
    result = {
        "activity_code": "R01",
        "ic_name": "NCI",
        "core_project_num": "R01CA123456",
        "pi_names": "SMITH, JOHN",
        "fiscal_year": 2026,
    }
    meta = _make_gap_fill_metadata(result)
    assert meta["activity_code"] == "R01"
    assert meta["fy"] == 2026


def test_gap_fill_metadata_pi_names_list():
    result = {
        "pi_names": [
            {"last_name": "SMITH", "first_name": "JOHN"},
            {"last_name": "DOE", "first_name": "JANE"},
        ],
        "fiscal_year": 2026,
    }
    meta = _make_gap_fill_metadata(result)
    assert meta["pi_names"] == "SMITH, JOHN; DOE, JANE"


def test_gap_fill_metadata_agency_ic_admin_abbreviation():
    result = {
        "agency_ic_admin": {"abbreviation": "NCI"},
        "fiscal_year": 2025,
    }
    meta = _make_gap_fill_metadata(result)
    assert meta["ic_name"] == "NCI"


def test_gap_fill_metadata_missing_fields_produce_none():
    meta = _make_gap_fill_metadata({})
    assert meta["activity_code"] is None
    assert meta["ic_name"] is None
    assert meta["core_project_num"] is None
    assert meta["pi_names"] is None
    assert meta["fy"] is None


# ---------------------------------------------------------------------------
# 10. _load_gap_fill_year
# ---------------------------------------------------------------------------


def _make_gap_fill_page(results: list[dict]) -> dict:
    return {
        "meta": {"total": len(results), "offset": 0, "limit": 500},
        "results": results,
    }


GAP_FILL_RESULT = {
    "appl_id": 99887766,
    "project_title": "Gap Fill Test Project",
    "abstract_text": "Gap fill abstract.",
    "project_start_date": "2026-01-01",
    "project_end_date": "2026-12-31",
    "award_amount": 300000,
    "org_name": "Gap University",
    "org_country": "UNITED STATES",
    "activity_code": "R01",
    "ic_name": "NINDS",
    "core_project_num": "R01NS123456",
    "pi_names": "JONES, ALICE",
    "fiscal_year": 2026,
}


def _write_gap_fill_page(data_dir: Path, year: int, page: int, page_data: dict) -> str:
    gap_dir = data_dir / "nih" / "gap_fill"
    gap_dir.mkdir(parents=True, exist_ok=True)
    page_file = gap_dir / f"fy{year}_page_{page:04d}.json"
    page_file.write_text(json.dumps(page_data))
    return f"nih/gap_fill/fy{year}_page_{page:04d}.json"


def test_gap_fill_inserts_row(tmp_path):
    data_dir = tmp_path / "data"
    page_rel = _write_gap_fill_page(
        data_dir, 2026, 1, _make_gap_fill_page([GAP_FILL_RESULT])
    )
    year_entry = {
        "fiscal_year": 2026,
        "pages": [page_rel],
        "status": "ok",
    }
    db = tmp_path / "test.db"
    conn = _fresh_db(db)
    errors: list = []
    n = _load_gap_fill_year(conn, data_dir, year_entry, errors)
    assert n == 1
    assert errors == []


def test_gap_fill_correct_values(tmp_path):
    data_dir = tmp_path / "data"
    page_rel = _write_gap_fill_page(
        data_dir, 2026, 1, _make_gap_fill_page([GAP_FILL_RESULT])
    )
    year_entry = {"fiscal_year": 2026, "pages": [page_rel], "status": "ok"}
    db = tmp_path / "test.db"
    conn = _fresh_db(db)
    _load_gap_fill_year(conn, data_dir, year_entry, [])

    row = conn.execute(
        "SELECT title, abstract, start_date, end_date, funding_amount, "
        "funding_currency, organization, country, source, source_id FROM grants "
        "WHERE source_id=?",
        ("99887766",),
    ).fetchone()
    assert row is not None
    title, abstract, start_date, end_date, amount, currency, org, country, source, sid = row
    assert title == "Gap Fill Test Project"
    assert abstract == "Gap fill abstract."
    assert start_date == "2026-01-01"
    assert end_date == "2026-12-31"
    assert abs(amount - 300000) < 0.01
    assert currency == "USD"
    assert source == "nih"
    assert sid == "99887766"


def test_gap_fill_normalize_country(tmp_path):
    data_dir = tmp_path / "data"
    page_rel = _write_gap_fill_page(
        data_dir, 2026, 1, _make_gap_fill_page([GAP_FILL_RESULT])
    )
    year_entry = {"fiscal_year": 2026, "pages": [page_rel], "status": "ok"}
    db = tmp_path / "test.db"
    conn = _fresh_db(db)
    _load_gap_fill_year(conn, data_dir, year_entry, [])

    row = conn.execute(
        "SELECT country FROM grants WHERE source_id=?", ("99887766",)
    ).fetchone()
    assert row is not None
    assert row[0] == "US"


def test_gap_fill_missing_page_records_error(tmp_path):
    data_dir = tmp_path / "data"
    (data_dir / "nih" / "gap_fill").mkdir(parents=True)  # dir exists but file absent
    year_entry = {
        "fiscal_year": 2026,
        "pages": ["nih/gap_fill/fy2026_page_0001.json"],
        "status": "ok",
    }
    db = tmp_path / "test.db"
    conn = _fresh_db(db)
    errors: list = []
    _load_gap_fill_year(conn, data_dir, year_entry, errors)
    assert len(errors) == 1


def test_gap_fill_idempotent(tmp_path):
    data_dir = tmp_path / "data"
    page_rel = _write_gap_fill_page(
        data_dir, 2026, 1, _make_gap_fill_page([GAP_FILL_RESULT])
    )
    year_entry = {"fiscal_year": 2026, "pages": [page_rel], "status": "ok"}
    db = tmp_path / "test.db"
    conn = _fresh_db(db)
    _load_gap_fill_year(conn, data_dir, year_entry, [])
    _load_gap_fill_year(conn, data_dir, year_entry, [])  # second run

    count = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
    assert count == 1, "INSERT OR REPLACE should not double the rows"


# ---------------------------------------------------------------------------
# 11. build() — integration
# ---------------------------------------------------------------------------


def _setup_full_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Return (data_dir, db_path, zip_path) with CORDIS zip + NIH files ready."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = tmp_path / "grants.db"

    # CORDIS h2020 ZIP
    cordis_dir = data_dir / "cordis" / "h2020"
    cordis_dir.mkdir(parents=True)
    cordis_zip = cordis_dir / "cordis-h2020projects-csv.zip"
    cordis_zip.write_bytes(_make_cordis_zip([CORDIS_PROJECT_ROW], [CORDIS_ORG_ROW]))

    # NIH ExPORTER
    exporter_dir = data_dir / "nih" / "exporter"
    exporter_dir.mkdir(parents=True)
    prj_path = exporter_dir / "RePORTER_PRJ_C_FY2022.zip"
    abs_path = exporter_dir / "RePORTER_PRJABS_C_FY2022.zip"
    prj_path.write_bytes(_make_streaming_zip(NIH_PROJECT_CSV))
    abs_path.write_bytes(_make_abs_zip(NIH_ABS_ROWS))

    # Gap fill page
    gap_dir = data_dir / "nih" / "gap_fill"
    gap_dir.mkdir(parents=True)
    page_path = gap_dir / "fy2026_page_0001.json"
    page_path.write_text(json.dumps(_make_gap_fill_page([GAP_FILL_RESULT])))

    # Manifest
    manifest = {
        "schema_version": 1,
        "cordis": {
            "programmes": [
                {
                    "programme": "h2020",
                    "file": "cordis/h2020/cordis-h2020projects-csv.zip",
                    "status": "ok",
                }
            ]
        },
        "nih_exporter": {
            "files": [
                {
                    "fiscal_year": 2022,
                    "project_file": "nih/exporter/RePORTER_PRJ_C_FY2022.zip",
                    "abstract_file": "nih/exporter/RePORTER_PRJABS_C_FY2022.zip",
                    "status": "ok",
                }
            ]
        },
        "nih_gap_fill": {
            "fiscal_years": [2026],
            "files": [
                {
                    "fiscal_year": 2026,
                    "pages": ["nih/gap_fill/fy2026_page_0001.json"],
                    "status": "ok",
                }
            ],
        },
    }
    (data_dir / "manifest.json").write_text(json.dumps(manifest))

    return data_dir, db_path, cordis_zip


def _run_build(data_dir, db_path, **kwargs):
    """Run build() with acquire_run mocked to return 0 (manifest already written)."""
    with patch("db.build_db.acquire_run", return_value=0):
        return build(
            start_year=2022,
            data_dir=data_dir,
            db_path=db_path,
            **kwargs,
        )


def test_build_exit_code_0_clean(tmp_path):
    data_dir, db_path, _ = _setup_full_fixture(tmp_path)
    code = _run_build(data_dir, db_path)
    assert code == 0


def test_build_creates_database(tmp_path):
    data_dir, db_path, _ = _setup_full_fixture(tmp_path)
    _run_build(data_dir, db_path)
    assert db_path.exists()


def test_build_total_grant_count(tmp_path):
    data_dir, db_path, _ = _setup_full_fixture(tmp_path)
    _run_build(data_dir, db_path)

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
    conn.close()
    # 1 CORDIS + 1 NIH ExPORTER + 1 gap fill = 3
    assert count == 3


def test_build_fts5_match_after_build(tmp_path):
    """After build(), FTS MATCH query returns expected rows."""
    data_dir, db_path, _ = _setup_full_fixture(tmp_path)
    _run_build(data_dir, db_path)

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT grants.title FROM grants_fts "
        "JOIN grants ON grants_fts.rowid = grants.id "
        "WHERE grants_fts MATCH 'communication'"
    ).fetchall()
    conn.close()
    titles = [r[0] for r in rows]
    # CORDIS project has "Research into communication." in objective
    assert any("CORDIS" in t or "Test" in t or "communication" in t.lower()
               for t in titles)


def test_build_fts5_match_nih_title(tmp_path):
    """NIH ExPORTER title indexed in FTS5."""
    data_dir, db_path, _ = _setup_full_fixture(tmp_path)
    _run_build(data_dir, db_path)

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT grants.title FROM grants_fts "
        "JOIN grants ON grants_fts.rowid = grants.id "
        "WHERE grants_fts MATCH 'NIH'"
    ).fetchall()
    conn.close()
    assert rows, "FTS5 should index NIH grant title"


def test_build_summary_output(tmp_path, capsys):
    data_dir, db_path, _ = _setup_full_fixture(tmp_path)
    _run_build(data_dir, db_path)

    out = capsys.readouterr().out
    assert "Build complete." in out
    assert "NIH grants loaded:" in out
    assert "CORDIS grants loaded:" in out
    assert "Total:" in out
    assert "Errors:" in out
    assert "Database:" in out


def test_build_summary_counts(tmp_path, capsys):
    data_dir, db_path, _ = _setup_full_fixture(tmp_path)
    _run_build(data_dir, db_path)

    out = capsys.readouterr().out
    # 1 NIH ExPORTER + 1 gap fill = 2 NIH total
    # 1 CORDIS h2020
    assert "ExPORTER: 1" in out
    assert "gap fill: 1" in out
    assert "h2020: 1" in out


def test_build_exit_code_1_on_acquire_failure(tmp_path):
    """If acquire_run returns 1, build() returns 1 (partial failure)."""
    data_dir, db_path, _ = _setup_full_fixture(tmp_path)
    with patch("db.build_db.acquire_run", return_value=1):
        code = build(
            start_year=2022,
            data_dir=data_dir,
            db_path=db_path,
        )
    assert code == 1


def test_build_continues_after_acquire_failure(tmp_path):
    """After acquire_run returns 1, available files are still loaded."""
    data_dir, db_path, _ = _setup_full_fixture(tmp_path)
    with patch("db.build_db.acquire_run", return_value=1):
        build(start_year=2022, data_dir=data_dir, db_path=db_path)

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
    conn.close()
    assert count >= 1, "Some grants should be loaded even after partial acquisition"


def test_build_exit_code_1_on_row_error(tmp_path):
    """A missing gap-fill page file causes an error → exit code 1."""
    data_dir, db_path, _ = _setup_full_fixture(tmp_path)

    # Remove the gap-fill page so it cannot be loaded
    page_file = data_dir / "nih" / "gap_fill" / "fy2026_page_0001.json"
    page_file.unlink()

    code = _run_build(data_dir, db_path)
    assert code == 1


def test_build_idempotency(tmp_path):
    """Running build() twice with the same data produces the same row count."""
    data_dir, db_path, _ = _setup_full_fixture(tmp_path)
    _run_build(data_dir, db_path)

    conn = sqlite3.connect(str(db_path))
    count_after_first = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
    conn.close()

    # Second run — overwrite prompt mocked away (db has rows now)
    with patch("db.build_db.acquire_run", return_value=0):
        with patch("builtins.input"):  # suppress prompt
            build(
                start_year=2022,
                data_dir=data_dir,
                db_path=db_path,
            )

    conn = sqlite3.connect(str(db_path))
    count_after_second = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
    conn.close()

    assert count_after_first == count_after_second, (
        f"Row count changed from {count_after_first} to {count_after_second} on second run"
    )


def test_build_skips_failed_cordis_programmes(tmp_path):
    """CORDIS entries with status != 'ok' are skipped."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = tmp_path / "test.db"

    manifest = {
        "schema_version": 1,
        "cordis": {
            "programmes": [
                {
                    "programme": "fp7",
                    "file": "cordis/fp7/nonexistent.zip",
                    "status": "failed",
                }
            ]
        },
        "nih_exporter": {"files": []},
        "nih_gap_fill": {"fiscal_years": [], "files": []},
    }
    (data_dir / "manifest.json").write_text(json.dumps(manifest))

    code = _run_build(data_dir, db_path)
    # No files loaded but no error either (skipped, not failed)
    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
    conn.close()
    assert count == 0
