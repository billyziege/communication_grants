# Contract 03 — DB Build Pipeline

**Status:** Ready for implementation  
**Depends on:** Contract 00 (`acquire_data.py`), Contract 01 (`db/models.py` — schema + normalization helpers)  
**Prerequisite for:** Contract 04 (query layer needs a populated DB to test against)

---

## 1. Purpose and Scope

`db/build_db.py` is the full pipeline: it invokes data acquisition, reads the downloaded files, normalizes every field using helpers from `db/models.py`, and loads a single SQLite database. It is the only supported way to produce the database.

**In scope:**
- CLI interface (§2)
- Overwrite detection, confirmation prompt, and optional backup (§3)
- Calling `db.acquire_data.run()` for all downloads (§4)
- Loading CORDIS data from downloaded ZIPs (§5)
- Loading NIH ExPORTER data from downloaded ZIPs (§6)
- Loading NIH gap-fill data from downloaded JSON files (§7)
- FTS5 index rebuild (§8)
- Summary report (§9)
- Country lookup dict augmentation: `NIH_COUNTRY_LOOKUP` lives in `db/models.py` (placed by Contract 01); this pipeline imports and calls `normalize_country()` from there

**Out of scope:**
- Any downloads (delegated to `acquire_data.py`)
- Schema DDL (defined in `db/models.py` — call `create_schema(conn)`)
- Normalization logic (defined in `db/models.py`)
- The running web application

---

## 2. CLI Interface

```
python db/build_db.py \
    --start-year YYYY \
    --data-dir  PATH \
    --db-path   PATH \
    [--force-redownload] \
    [--backup-db [PATH]]
```

| Argument | Required | Description |
|---|---|---|
| `--start-year` | Yes | First fiscal year to include (e.g. `2007`); passed through to `acquire_data` |
| `--data-dir` | Yes | Directory containing downloaded files and `manifest.json` |
| `--db-path` | Yes | Path to write the SQLite database (created if absent) |
| `--force-redownload` | No | Passed through to `acquire_data`; re-downloads all files |
| `--backup-db [PATH]` | No | If the DB already has data, copy it before overwriting; auto-names backup if no path given |

**Exit codes:**
- `0` — pipeline completed; database written
- `1` — one or more records failed to load; database written with what succeeded; errors printed to stderr

---

## 3. Overwrite Detection and Backup

Before any writes, check whether `--db-path` already exists and contains rows in the `grants` table.

### 3.1 When existing data is detected

Print one of two prompts, then call `input()` to wait:

**With `--backup-db`:**
```
{db_path} already exists with {N:,} grants.
Will back up to {backup_path} before writing.
Press Enter to continue or Ctrl+C to abort.
```

**Without `--backup-db`:**
```
{db_path} already exists with {N:,} grants.
You can abort and rerun with --backup-db to preserve current state.
Press Enter to continue or Ctrl+C to abort.
```

### 3.2 Backup execution

If `--backup-db` was given, perform the backup **after** the user confirms (not before) using `shutil.copy2(db_path, backup_path)`. Log: `Backed up {db_path} → {backup_path}`.

If no path was given with `--backup-db`, auto-name the backup:
```
{db_path}.{YYYYMMDDHHMMSS}.bak
```
where the timestamp is UTC at the moment the confirmation is received.

### 3.3 Fresh database

If `--db-path` does not exist, or exists but has no `grants` table, or has a `grants` table with zero rows: proceed without prompting.

---

## 4. Data Acquisition

```python
from db.acquire_data import run as acquire_run

exit_code = acquire_run(
    start_year=args.start_year,
    data_dir=Path(args.data_dir),
    force=args.force_redownload,
)
```

If `acquire_run` returns `1` (one or more files failed), print a warning and continue with whatever was successfully downloaded. Do not abort — partial data is better than no data for a research use case.

After acquisition, read the manifest:
```python
manifest = json.loads((data_dir / "manifest.json").read_text())
```

---

## 5. Loading CORDIS Data

For each programme recorded in `manifest["cordis"]["programmes"]` where `status == "ok"`:

1. Open the ZIP with `zipfile.ZipFile` (CORDIS ZIPs use the standard format)
2. Load `organization.csv` into memory: a dict `{project_id: (org_name, country)}` keeping only `role == 'coordinator'` rows — use `get_coordinator()` from `db/models.py`
3. Stream `project.csv` row by row using Python's `csv.reader` with `delimiter=';'`
4. For each project row, build a `grants` insert:

| `grants` column | Source | Helper |
|---|---|---|
| `title` | `project["title"]` | `.strip()` |
| `abstract` | `project["objective"]` | `.strip()` or NULL if blank |
| `start_date` | `project["startDate"]` | already ISO 8601; NULL if blank |
| `end_date` | `project["endDate"]` | already ISO 8601; NULL if blank |
| `funding_amount` | `project["ecMaxContribution"]` | `normalize_cordis_decimal()` |
| `funding_currency` | `'EUR'` | NULL if amount is NULL |
| `organization` | coordinator `name` | from org dict |
| `country` | coordinator `country` | from org dict (already ISO alpha-2) |
| `source` | `'cordis'` | — |
| `source_id` | `project["id"]` | store as text |
| `source_programme` | filename | `source_programme_from_filename()` |
| `source_url` | `project["id"]` | `cordis_source_url()` |
| `metadata` | multiple | `make_cordis_metadata()` → `json.dumps()` |

Use `INSERT OR REPLACE` to handle re-runs idempotently.

### 5.1 CORDIS organization join approach

Loading all coordinator rows into a dict keyed by `projectID` before streaming `project.csv` is preferred over a per-row lookup. For large files this keeps memory bounded at one coordinator row per project — acceptable given the file sizes (Horizon Europe organization.csv is ~60MB uncompressed; keeping only coordinator rows reduces this to tens of thousands of entries).

---

## 6. Loading NIH ExPORTER Data

For each fiscal year in `manifest["nih_exporter"]["files"]` where `status == "ok"`:

### 6.1 Load abstracts into memory

Open `RePORTER_PRJABS_C_FY{YEAR}.zip` with `zipfile.ZipFile` (standard format). Read the CSV into a dict `{application_id: abstract_text}`.

### 6.2 Stream project rows

Open `RePORTER_PRJ_C_FY{YEAR}.zip` using `iter_csv_lines()` from `db/models.py` (streaming deflate — `zipfile.ZipFile` cannot open these files; see Contract 01 §4.1).

Decode the byte stream as UTF-8 and parse with `csv.reader`.

For each project row, build a `grants` insert:

| `grants` column | Source | Helper |
|---|---|---|
| `title` | `PROJECT_TITLE` | `.strip()` |
| `abstract` | `abstracts.get(APPLICATION_ID)` | NULL if no match |
| `start_date` | `PROJECT_START` | `normalize_nih_date()` |
| `end_date` | `PROJECT_END` | `normalize_nih_date()` |
| `funding_amount` | `TOTAL_COST` | parse as float; NULL if blank |
| `funding_currency` | `'USD'` | NULL if amount is NULL |
| `organization` | `ORG_NAME` | `.strip()` |
| `country` | `ORG_COUNTRY` | `normalize_country()` from `db/models.py` |
| `source` | `'nih'` | — |
| `source_id` | `APPLICATION_ID` | store as text |
| `source_programme` | `NULL` | — |
| `source_url` | `APPLICATION_ID` | `nih_source_url()` |
| `metadata` | multiple | `make_nih_metadata()` → `json.dumps()` |

Use `INSERT OR REPLACE`.

---

## 7. Loading NIH Gap-Fill Data

For each fiscal year in `manifest["nih_gap_fill"]["fiscal_years"]`:

Read all page files (`nih/gap_fill/fy{YEAR}_page_{N:04d}.json`) in page order. Each file contains the raw RePORTER API v2 response:

```json
{
  "meta": {"total": ..., "offset": ..., "limit": ...},
  "results": [ { ... }, ... ]
}
```

### 7.1 API v2 field names

**Implementation note:** RePORTER API v2 field names differ from ExPORTER CSV column names. Verify the exact field names from the API documentation at `https://api.reporter.nih.gov/` or by inspecting an actual gap-fill JSON file produced by `acquire_data.py`. The table below gives the expected names based on the v2 schema; treat them as provisional until verified against a live file.

| `grants` column | Expected API v2 field | Notes |
|---|---|---|
| `title` | `project_title` | `.strip()` |
| `abstract` | `abstract_text` | NULL if absent |
| `start_date` | `project_start_date` | ISO 8601 from API; `normalize_nih_date()` as fallback |
| `end_date` | `project_end_date` | ISO 8601 from API |
| `funding_amount` | `award_amount` | parse as float; NULL if absent |
| `funding_currency` | `'USD'` | — |
| `organization` | `org_name` | `.strip()` |
| `country` | `org_country` | `normalize_country()` |
| `source` | `'nih'` | — |
| `source_id` | `appl_id` | cast to text |
| `source_programme` | `NULL` | — |
| `source_url` | `appl_id` | `nih_source_url()` |
| `metadata` | multiple | see §7.2 |

### 7.2 Gap-fill metadata JSON

```json
{
  "activity_code":    "R01",
  "ic_name":          "...",
  "core_project_num": "...",
  "pi_names":         "SMITH, JOHN",
  "fy":               2026
}
```

Expected API v2 sources: `activity_code`, `agency_ic_admin.abbreviation` (or `ic_name`), `core_project_num`, `pi_names` (list — join to a single string as `"LAST, FIRST; ..."` for consistency with ExPORTER format), `fiscal_year`.

Use `INSERT OR REPLACE`.

---

## 8. FTS5 Index Rebuild

After all inserts are complete:

```python
conn.execute("INSERT INTO grants_fts(grants_fts) VALUES('rebuild')")
conn.commit()
```

This rebuilds the content-rowid FTS5 index from the `grants` table in one pass.

---

## 9. Summary Report

Print to stdout on completion:

```
Build complete.
  NIH grants loaded:    {N:,}  (ExPORTER: {N:,}, gap fill: {N:,})
  CORDIS grants loaded: {N:,}  (fp7: {N:,}, h2020: {N:,}, horizon_europe: {N:,})
  Total:                {N:,}
  Errors:               {N}
  Database:             {db_path}  ({size:.1f} MB)
```

If errors > 0, also print: `See stderr for error details.`

---

## 10. Test Surface

The sub-agent implementing this contract must write tests covering at minimum:

- **Overwrite detection:** a DB with 0 rows does not trigger the prompt; a DB with ≥ 1 row does
- **Prompt text — with `--backup-db`:** prompt includes backup path and does not include the `--backup-db` hint
- **Prompt text — without `--backup-db`:** prompt includes `"You can abort and rerun with --backup-db to preserve current state."`
- **Backup execution:** backup is performed *after* `input()` returns, not before; `shutil.copy2` is called with the correct paths; auto-name follows `{db_path}.{YYYYMMDDHHMMSS}.bak` pattern
- **CORDIS loading:** given a minimal mock ZIP containing `project.csv` and `organization.csv`, inserts the correct row; coordinator join populates `organization` and `country`; `source_programme` matches the filename
- **NIH ExPORTER loading:** given a mock streaming-ZIP project file and a mock abstract ZIP, inserts the correct row with abstract joined; `normalize_country()` is called for `ORG_COUNTRY`
- **NIH gap-fill loading:** given a mock page JSON file, inserts the correct row
- **Idempotency:** running the load twice with the same data produces the same row count (not doubled), due to `INSERT OR REPLACE`
- **Partial acquisition failure:** if `acquire_run` returns `1`, loading proceeds with available files; exit code is `1`
- **FTS5 rebuild:** after load, an FTS `MATCH` query returns the expected row
- **Summary output:** correct counts appear in stdout
- **Exit code 0 / 1:** clean run exits `0`; a row-level load error exits `1`

HTTP calls and file I/O must be mocked; use `tmp_path` and in-memory or temp-file SQLite DBs.

---

## 11. Known Implementation Nuances

- **CORDIS ZIPs are multi-file**: each ZIP contains `project.csv`, `organization.csv`, and several other CSVs (see Contract 01 §5). Open with `zipfile.ZipFile` and address files by name.
- **NIH project ZIPs are streaming**: use `iter_csv_lines()` from `db/models.py`, not `zipfile.ZipFile`.
- **CORDIS decimal separator**: `ecMaxContribution` uses commas (`"2073781,25"`); use `normalize_cordis_decimal()`.
- **NIH date formats**: `PROJECT_START` / `PROJECT_END` may be `MM/DD/YYYY` or `YYYY-MM-DD`; use `normalize_nih_date()`.
- **Gap-fill API field names**: treat the names in §7.1 as provisional; verify against actual JSON output before writing the field-mapping code.
