#!/usr/bin/env python3
"""db/build_db.py — Full pipeline: acquire data, load, and build the SQLite DB.

Usage::

    python db/build_db.py \\
        --start-year YYYY \\
        --data-dir  PATH \\
        --db-path   PATH \\
        [--force-redownload] \\
        [--backup-db [PATH]]

Exit codes:
    0 — pipeline completed; database written.
    1 — one or more records (or acquisition steps) failed; database written
        with what succeeded; errors printed to stderr.

NIH gap-fill field-name decisions (§7.1 — provisional):
  - Project title:   ``project_title``
  - Abstract:        ``abstract_text``
  - Start date:      ``project_start_date`` (passed through normalize_nih_date)
  - End date:        ``project_end_date``
  - Award amount:    ``award_amount``
  - Application ID:  ``appl_id``
  - Activity code:   ``activity_code``
  - Core project #:  ``core_project_num``
  - Fiscal year:     ``fiscal_year``
  - IC name:         ``agency_ic_admin.abbreviation`` (falls back to ``ic_name``)
  - PI names:        ``pi_names`` — list of {last_name, first_name} dicts joined
                     as "LAST, FIRST; LAST, FIRST"; also accepted as a plain string
  - Org name:        tried first from nested ``organization.org_name``,
                     then flat ``org_name``
  - Org country:     tried first from nested ``organization.org_country``,
                     then flat ``org_country``
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from db.acquire_data import run as acquire_run  # noqa: F401 (imported for mocking in tests)
from db.models import (
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

# Re-export acquire_run so tests can patch "db.build_db.acquire_run"
from db.acquire_data import run as acquire_run  # noqa: F811


# ---------------------------------------------------------------------------
# Overwrite detection / backup
# ---------------------------------------------------------------------------


def _count_existing_grants(db_path: Path) -> int:
    """Return number of rows in the grants table, or 0 if the DB / table is absent."""
    if not db_path.exists():
        return 0
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            return conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()
    except Exception:
        return 0


def _handle_overwrite(
    db_path: Path,
    want_backup: bool,
    explicit_backup_path: Path | None = None,
) -> Path | None:
    """Check for existing data, prompt user, and optionally perform backup.

    Returns the actual backup path used, or None.

    Parameters
    ----------
    db_path:
        Path to the target database.
    want_backup:
        True when ``--backup-db`` was given (with or without an explicit path).
    explicit_backup_path:
        The path given after ``--backup-db``; None for auto-naming.
    """
    count = _count_existing_grants(db_path)
    if count == 0:
        return None

    if want_backup:
        if explicit_backup_path is not None:
            print(
                f"{db_path} already exists with {count:,} grants.\n"
                f"Will back up to {explicit_backup_path} before writing.\n"
                f"Press Enter to continue or Ctrl+C to abort."
            )
        else:
            print(
                f"{db_path} already exists with {count:,} grants.\n"
                f"Will back up to auto-named backup before writing.\n"
                f"Press Enter to continue or Ctrl+C to abort."
            )
    else:
        print(
            f"{db_path} already exists with {count:,} grants.\n"
            f"You can abort and rerun with --backup-db to preserve current state.\n"
            f"Press Enter to continue or Ctrl+C to abort."
        )

    input()

    if want_backup:
        if explicit_backup_path is None:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            backup_path: Path = Path(f"{db_path}.{ts}.bak")
        else:
            backup_path = explicit_backup_path
        shutil.copy2(db_path, backup_path)
        print(f"Backed up {db_path} → {backup_path}")
        return backup_path

    return None


# ---------------------------------------------------------------------------
# CORDIS loading
# ---------------------------------------------------------------------------


def _load_cordis_org_dict(
    zf: zipfile.ZipFile,
) -> dict[str, tuple[str | None, str | None]]:
    """Return ``{projectID: (org_name, country)}`` for coordinators only.

    Groups all organization rows by ``projectID``, then calls
    ``get_coordinator()`` for each group.  Only coordinator rows are retained
    in the returned dict (memory bound: one entry per project).
    """
    orgs_by_project: dict[str, list[dict]] = {}
    with zf.open("organization.csv") as f:
        reader = csv.DictReader(
            io.TextIOWrapper(f, encoding="utf-8-sig"),
            delimiter=";",
        )
        for row in reader:
            pid = (row.get("projectID") or "").strip()
            if pid:
                orgs_by_project.setdefault(pid, []).append(dict(row))

    result: dict[str, tuple[str | None, str | None]] = {}
    for pid, orgs in orgs_by_project.items():
        name, country = get_coordinator(orgs, pid)
        result[pid] = (name, country)
    return result


def _load_cordis_programme(
    conn: sqlite3.Connection,
    zip_path: Path,
    errors: list,
) -> int:
    """Load one CORDIS ZIP; return number of rows inserted."""
    programme = source_programme_from_filename(zip_path)
    inserted = 0

    with zipfile.ZipFile(zip_path) as zf:
        org_dict = _load_cordis_org_dict(zf)

        with zf.open("project.csv") as f:
            reader = csv.DictReader(
                io.TextIOWrapper(f, encoding="utf-8-sig"),
                delimiter=";",
            )
            for row in reader:
                try:
                    project_id = (row.get("id") or "").strip()
                    if not project_id:
                        continue

                    title = (row.get("title") or "").strip()
                    if not title:
                        continue

                    abstract_raw = (row.get("objective") or "").strip()
                    abstract: str | None = abstract_raw if abstract_raw else None

                    start_date: str | None = (row.get("startDate") or "").strip() or None
                    end_date: str | None = (row.get("endDate") or "").strip() or None

                    amount = normalize_cordis_decimal(row.get("ecMaxContribution"))
                    currency: str | None = "EUR" if amount is not None else None

                    org_name, org_country = org_dict.get(project_id, (None, None))

                    metadata = json.dumps(make_cordis_metadata(row))

                    conn.execute(
                        """
                        INSERT OR REPLACE INTO grants (
                            title, abstract, start_date, end_date,
                            funding_amount, funding_currency,
                            organization, country,
                            source, source_id, source_programme, source_url,
                            metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            title, abstract, start_date, end_date,
                            amount, currency,
                            org_name, org_country,
                            "cordis", project_id, programme,
                            cordis_source_url(project_id),
                            metadata,
                        ),
                    )
                    inserted += 1
                except Exception as exc:
                    errors.append({
                        "file": str(zip_path),
                        "source_id": row.get("id"),
                        "error": str(exc),
                    })
                    print(
                        f"ERROR loading CORDIS row {row.get('id')}: {exc}",
                        file=sys.stderr,
                    )

    conn.commit()
    return inserted


# ---------------------------------------------------------------------------
# NIH ExPORTER loading
# ---------------------------------------------------------------------------


def _load_abstract_dict(abs_zip_path: Path) -> dict[str, str]:
    """Return ``{APPLICATION_ID: abstract_text}`` from a NIH abstract ZIP."""
    result: dict[str, str] = {}
    with zipfile.ZipFile(abs_zip_path) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            return result
        with zf.open(csv_names[0]) as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace"))
            for row in reader:
                app_id = (row.get("APPLICATION_ID") or "").strip()
                abstract = (row.get("ABSTRACT_TEXT") or "").strip()
                if app_id:
                    result[app_id] = abstract
    return result


def _load_nih_exporter_year(
    conn: sqlite3.Connection,
    data_dir: Path,
    file_entry: dict,
    errors: list,
) -> int:
    """Load one NIH ExPORTER fiscal year; return number of rows inserted."""
    prj_path = data_dir / file_entry["project_file"]
    abs_path = data_dir / file_entry["abstract_file"]
    inserted = 0

    # Load abstracts into memory
    abstracts: dict[str, str] = {}
    if abs_path.exists():
        try:
            abstracts = _load_abstract_dict(abs_path)
        except Exception as exc:
            errors.append({"file": str(abs_path), "error": f"abstract load: {exc}"})
            print(
                f"WARNING: failed to load abstracts from {abs_path}: {exc}",
                file=sys.stderr,
            )

    # Stream project rows using iter_csv_lines (streaming deflate format)
    line_iter = iter_csv_lines(prj_path)
    header_line = next(line_iter, None)
    if header_line is None:
        return 0

    header = list(csv.reader([header_line.rstrip(b"\r").decode("utf-8", errors="replace")]))[0]

    for raw_line in line_iter:
        line = raw_line.rstrip(b"\r").decode("utf-8", errors="replace")
        if not line.strip():
            continue

        try:
            values = list(csv.reader([line]))[0]
            # Pad short rows to avoid KeyError on missing trailing columns
            if len(values) < len(header):
                values.extend([""] * (len(header) - len(values)))
            row = dict(zip(header, values))

            app_id = (row.get("APPLICATION_ID") or "").strip()
            if not app_id:
                continue

            title = (row.get("PROJECT_TITLE") or "").strip()
            if not title:
                continue

            abstract: str | None = abstracts.get(app_id) or None

            start_date = normalize_nih_date(row.get("PROJECT_START"))
            end_date = normalize_nih_date(row.get("PROJECT_END"))

            total_cost_raw = (row.get("TOTAL_COST") or "").strip()
            try:
                amount: float | None = float(total_cost_raw) if total_cost_raw else None
            except ValueError:
                amount = None
            currency: str | None = "USD" if amount is not None else None

            org_name: str | None = (row.get("ORG_NAME") or "").strip() or None
            org_country = normalize_country(row.get("ORG_COUNTRY"))

            metadata = json.dumps(make_nih_metadata(row))

            conn.execute(
                """
                INSERT OR REPLACE INTO grants (
                    title, abstract, start_date, end_date,
                    funding_amount, funding_currency,
                    organization, country,
                    source, source_id, source_programme, source_url,
                    metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title, abstract, start_date, end_date,
                    amount, currency,
                    org_name, org_country,
                    "nih", app_id, None,
                    nih_source_url(app_id),
                    metadata,
                ),
            )
            inserted += 1
        except Exception as exc:
            errors.append({
                "source_id": row.get("APPLICATION_ID") if "row" in dir() else None,
                "error": str(exc),
            })
            print(
                f"ERROR loading NIH ExPORTER row: {exc}",
                file=sys.stderr,
            )

    conn.commit()
    return inserted


# ---------------------------------------------------------------------------
# NIH gap-fill loading
# ---------------------------------------------------------------------------


def _make_gap_fill_metadata(result: dict) -> dict:
    """Build the metadata dict from a NIH RePORTER API v2 result record.

    Field-name decisions documented in module docstring.
    """
    # pi_names: list of dicts or a plain string
    pi_names_raw = result.get("pi_names")
    if isinstance(pi_names_raw, list):
        parts: list[str] = []
        for pi in pi_names_raw:
            if isinstance(pi, dict):
                last = (pi.get("last_name") or "").strip()
                first = (pi.get("first_name") or "").strip()
                if last and first:
                    parts.append(f"{last}, {first}")
                elif last:
                    parts.append(last)
            elif isinstance(pi, str) and pi.strip():
                parts.append(pi.strip())
        pi_names: str | None = "; ".join(parts) if parts else None
    elif isinstance(pi_names_raw, str) and pi_names_raw.strip():
        pi_names = pi_names_raw.strip()
    else:
        pi_names = None

    # ic_name: prefer agency_ic_admin.abbreviation, fall back to ic_name
    agency_ic = result.get("agency_ic_admin")
    if isinstance(agency_ic, dict):
        ic_name: str | None = agency_ic.get("abbreviation") or agency_ic.get("name")
    else:
        ic_name = result.get("ic_name")

    # fiscal_year → fy as int
    fy_raw = result.get("fiscal_year")
    try:
        fy: int | None = int(fy_raw) if fy_raw is not None else None
    except (ValueError, TypeError):
        fy = None

    return {
        "activity_code": result.get("activity_code"),
        "ic_name": ic_name,
        "core_project_num": result.get("core_project_num"),
        "pi_names": pi_names,
        "fy": fy,
    }


def _load_gap_fill_year(
    conn: sqlite3.Connection,
    data_dir: Path,
    year_entry: dict,
    errors: list,
) -> int:
    """Load all pages for one gap-fill fiscal year; return rows inserted."""
    inserted = 0
    for page_relpath in year_entry.get("pages", []):
        page_path = data_dir / page_relpath
        if not page_path.exists():
            errors.append({"file": str(page_path), "error": "file not found"})
            print(f"ERROR: gap-fill page not found: {page_path}", file=sys.stderr)
            continue

        try:
            data = json.loads(page_path.read_text())
        except Exception as exc:
            errors.append({"file": str(page_path), "error": str(exc)})
            print(f"ERROR reading gap-fill page {page_path}: {exc}", file=sys.stderr)
            continue

        for result in data.get("results", []):
            try:
                appl_id = result.get("appl_id")
                if appl_id is None:
                    continue
                appl_id_str = str(appl_id)

                title = (result.get("project_title") or "").strip()
                if not title:
                    continue

                abstract_raw = result.get("abstract_text")
                abstract: str | None = (
                    abstract_raw.strip() if isinstance(abstract_raw, str) and abstract_raw.strip()
                    else None
                )

                start_date = normalize_nih_date(result.get("project_start_date"))
                end_date = normalize_nih_date(result.get("project_end_date"))

                amount_raw = result.get("award_amount")
                try:
                    amount: float | None = (
                        float(amount_raw) if amount_raw is not None else None
                    )
                except (ValueError, TypeError):
                    amount = None

                # org_name / org_country: check nested org dict first, then flat
                org_info = result.get("organization")
                if isinstance(org_info, dict):
                    org_name: str | None = (
                        (org_info.get("org_name") or "").strip() or None
                    )
                    org_country_raw: str | None = org_info.get("org_country")
                else:
                    org_name = (result.get("org_name") or "").strip() or None
                    org_country_raw = result.get("org_country")

                org_country = normalize_country(org_country_raw)

                metadata = json.dumps(_make_gap_fill_metadata(result))

                conn.execute(
                    """
                    INSERT OR REPLACE INTO grants (
                        title, abstract, start_date, end_date,
                        funding_amount, funding_currency,
                        organization, country,
                        source, source_id, source_programme, source_url,
                        metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        title, abstract, start_date, end_date,
                        amount, "USD",
                        org_name, org_country,
                        "nih", appl_id_str, None,
                        nih_source_url(appl_id_str),
                        metadata,
                    ),
                )
                inserted += 1
            except Exception as exc:
                errors.append({
                    "source_id": result.get("appl_id"),
                    "error": str(exc),
                })
                print(
                    f"ERROR loading gap-fill row {result.get('appl_id')}: {exc}",
                    file=sys.stderr,
                )

    conn.commit()
    return inserted


# ---------------------------------------------------------------------------
# Main build function
# ---------------------------------------------------------------------------


def build(
    start_year: int,
    data_dir: Path,
    db_path: Path,
    force_redownload: bool = False,
    want_backup: bool = False,
    explicit_backup_path: Path | None = None,
) -> int:
    """Run the full build pipeline.  Returns 0 on clean success, 1 on any error.

    Parameters
    ----------
    start_year:
        First fiscal year to include.
    data_dir:
        Directory where downloaded files and ``manifest.json`` live.
    db_path:
        Path for the output SQLite database.
    force_redownload:
        Re-download all files even if they already exist on disk.
    want_backup:
        True when ``--backup-db`` was given.
    explicit_backup_path:
        Explicit backup path; None means auto-name.
    """
    errors: list = []

    # --- overwrite check and optional backup ---
    _handle_overwrite(db_path, want_backup, explicit_backup_path)

    # --- acquire data ---
    acquire_exit = acquire_run(
        start_year=start_year,
        data_dir=data_dir,
        force=force_redownload,
    )
    if acquire_exit != 0:
        print(
            "WARNING: data acquisition reported failures; "
            "loading whatever was successfully downloaded.",
            file=sys.stderr,
        )

    # --- read manifest ---
    manifest = json.loads((data_dir / "manifest.json").read_text())

    # --- open (or create) database and apply schema ---
    conn = sqlite3.connect(str(db_path))
    create_schema(conn)

    # Counters
    cordis_total = 0
    cordis_by_prog: dict[str, int] = {"fp7": 0, "h2020": 0, "horizon_europe": 0}
    nih_exporter_total = 0
    nih_gap_total = 0

    # --- load CORDIS ---
    for entry in manifest.get("cordis", {}).get("programmes", []):
        if entry.get("status") != "ok":
            continue
        zip_path = data_dir / entry["file"]
        try:
            n = _load_cordis_programme(conn, zip_path, errors)
            prog = entry.get("programme", "")
            cordis_total += n
            if prog in cordis_by_prog:
                cordis_by_prog[prog] += n
        except Exception as exc:
            errors.append({"file": entry["file"], "error": str(exc)})
            print(
                f"ERROR loading CORDIS programme {entry['file']}: {exc}",
                file=sys.stderr,
            )

    # --- load NIH ExPORTER ---
    for file_entry in manifest.get("nih_exporter", {}).get("files", []):
        if file_entry.get("status") != "ok":
            continue
        try:
            n = _load_nih_exporter_year(conn, data_dir, file_entry, errors)
            nih_exporter_total += n
        except Exception as exc:
            errors.append({
                "file": file_entry.get("project_file", ""),
                "error": str(exc),
            })
            print(
                f"ERROR loading NIH ExPORTER FY{file_entry.get('fiscal_year')}: {exc}",
                file=sys.stderr,
            )

    # --- load NIH gap fill ---
    for year_entry in manifest.get("nih_gap_fill", {}).get("files", []):
        if year_entry.get("status") != "ok":
            continue
        try:
            n = _load_gap_fill_year(conn, data_dir, year_entry, errors)
            nih_gap_total += n
        except Exception as exc:
            errors.append({
                "file": f"nih/gap_fill/fy{year_entry.get('fiscal_year')}",
                "error": str(exc),
            })
            print(
                f"ERROR loading gap-fill FY{year_entry.get('fiscal_year')}: {exc}",
                file=sys.stderr,
            )

    # --- FTS5 rebuild ---
    conn.execute("INSERT INTO grants_fts(grants_fts) VALUES('rebuild')")
    conn.commit()

    conn.close()

    # --- summary report ---
    nih_total = nih_exporter_total + nih_gap_total
    total = cordis_total + nih_total
    db_size_mb = db_path.stat().st_size / (1024 * 1024)

    print("Build complete.")
    print(
        f"  NIH grants loaded:    {nih_total:,}"
        f"  (ExPORTER: {nih_exporter_total:,}, gap fill: {nih_gap_total:,})"
    )
    print(
        f"  CORDIS grants loaded: {cordis_total:,}"
        f"  (fp7: {cordis_by_prog['fp7']:,},"
        f" h2020: {cordis_by_prog['h2020']:,},"
        f" horizon_europe: {cordis_by_prog['horizon_europe']:,})"
    )
    print(f"  Total:                {total:,}")
    print(f"  Errors:               {len(errors)}")
    print(f"  Database:             {db_path}  ({db_size_mb:.1f} MB)")

    if errors:
        print("See stderr for error details.")

    return 1 if (errors or acquire_exit != 0) else 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the communication grants SQLite database."
    )
    parser.add_argument(
        "--start-year", type=int, required=True,
        help="First fiscal year to include (e.g. 2007).",
    )
    parser.add_argument(
        "--data-dir", type=Path, required=True,
        help="Directory containing downloaded files and manifest.json.",
    )
    parser.add_argument(
        "--db-path", type=Path, required=True,
        help="Path to write the SQLite database (created if absent).",
    )
    parser.add_argument(
        "--force-redownload", action="store_true",
        help="Re-download all files even if they already exist.",
    )
    parser.add_argument(
        "--backup-db",
        nargs="?",
        const="__auto__",
        default=None,
        metavar="PATH",
        help=(
            "Copy the existing database before overwriting. "
            "If PATH is omitted, an auto-named backup is created."
        ),
    )
    args = parser.parse_args()

    want_backup = args.backup_db is not None
    explicit_backup: Path | None = None
    if want_backup and args.backup_db != "__auto__":
        explicit_backup = Path(args.backup_db)

    sys.exit(
        build(
            start_year=args.start_year,
            data_dir=args.data_dir,
            db_path=args.db_path,
            force_redownload=args.force_redownload,
            want_backup=want_backup,
            explicit_backup_path=explicit_backup,
        )
    )


if __name__ == "__main__":
    main()
