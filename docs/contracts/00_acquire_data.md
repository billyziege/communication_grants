# Contract 00 — `db/acquire_data.py`

**Status:** Ready for implementation  
**Depends on:** None  
**Prerequisite for:** Contract 01 (field name verification — see §9)

---

## 1. Purpose and Scope

`db/acquire_data.py` is responsible for **data acquisition only** — downloading source files from NIH ExPORTER and CORDIS, detecting the temporal anchor, triggering the NIH gap fill if needed, and writing a manifest. It performs no parsing, normalization, or database operations.

**In scope:**
- Downloading NIH ExPORTER annual project and abstract ZIP files
- Downloading CORDIS bulk CSV files for FP7, Horizon 2020, and Horizon Europe
- Extracting the CORDIS temporal anchor date
- Detecting whether the NIH ExPORTER coverage falls short of the anchor date
- Filling the NIH gap via the live RePORTER API if needed
- Writing a manifest JSON file recording what was acquired
- Idempotent re-runs (skip files that already exist and are intact)

**Out of scope:**
- Unzipping or parsing CSV contents (the ZIPs are written to disk as-is)
- Normalization or field mapping
- SQLite operations
- Any operation performed by `build_db.py` after acquisition

---

## 2. CLI Interface

```
python db/acquire_data.py \
    --start-year YYYY \
    --data-dir PATH \
    [--force-redownload]
```

| Argument | Required | Description |
|---|---|---|
| `--start-year` | Yes | First fiscal year to include (e.g. `2007`) |
| `--data-dir` | Yes | Directory where downloaded files and manifest are written |
| `--force-redownload` | No | Re-download all files even if they already exist |

**No `--end-year` argument.** The end date is determined automatically by the CORDIS temporal anchor (see §5). The resolved anchor date is reported to the user and recorded in the manifest.

**Exit codes:**
- `0` — all files acquired successfully, manifest written
- `1` — one or more files could not be acquired; manifest written with failure records

---

## 3. File Layout

All files are written under `--data-dir` in the following structure:

```
{data-dir}/
  manifest.json
  nih/
    exporter/
      RePORTER_PRJ_C_FY{YEAR}.zip        # project file, one per fiscal year
      RePORTER_PRJABS_C_FY{YEAR}.zip     # abstract file, one per fiscal year
    gap_fill/
      fy{YEAR}_projects.json             # raw API response pages, one file per fiscal year
  cordis/
    fp7/
      cordis-fp7projects-csv.zip
    h2020/
      cordis-h2020projects-csv.zip
    horizon_europe/
      cordis-HORIZONprojects-csv.zip
```

Sub-directories are created by the script if they do not exist.

---

## 4. Download Behavior

All HTTP requests must:
- Set `User-Agent: communication-grants-research/1.0 (academic research; contact: brandon.s.zerbe@gmail.com)`
- Wait **2 seconds between consecutive requests** to the same host
- Follow redirects
- Raise on HTTP 4xx/5xx responses

---

## 5. CORDIS Acquisition and Temporal Anchor

### 5.1 Files to download

Download one ZIP file per framework programme (each ZIP contains a single CSV):

| Programme | Period | URL |
|---|---|---|
| FP7 | 2007–2013 | `https://cordis.europa.eu/data/cordis-fp7projects-csv.zip` |
| Horizon 2020 | 2014–2020 | `https://cordis.europa.eu/data/cordis-h2020projects-csv.zip` |
| Horizon Europe | 2021–present | `https://cordis.europa.eu/data/cordis-HORIZONprojects-csv.zip` |

FP7 and Horizon 2020 are closed programmes; their files are static. Horizon Europe is updated periodically.

### 5.2 Temporal anchor extraction

The temporal anchor is extracted from the HTTP `Last-Modified` response header of the Horizon Europe ZIP download. This header reflects when CORDIS last refreshed the bulk export and is the canonical measure of data currency.

Steps:
1. Issue a HEAD request (or capture the header during the GET download) to `cordis-HORIZONprojects-csv.zip`
2. Parse the `Last-Modified` header value into a `datetime.date`
3. If the header is absent, abort with a clear error: `"CORDIS Horizon Europe ZIP returned no Last-Modified header — cannot determine temporal anchor"`

The temporal anchor is the end boundary for all NIH data. It is recorded in the manifest and reported to the user:

```
CORDIS temporal anchor: 2026-09-14
Both sources will cover {--start-year} through 2026-09-14.
```

---

## 6. NIH ExPORTER Acquisition

### 6.1 Files to download

For each fiscal year from `--start-year` to the last complete NIH fiscal year whose end date (September 30) falls on or before the CORDIS temporal anchor:

- Project file: `https://reporter.nih.gov/services/exporter/DownloadFromDocService?DocType=EXPPRJ&KeyId={YEAR}`
- Abstract file: `https://reporter.nih.gov/services/exporter/DownloadFromDocService?DocType=EXPABS&KeyId={YEAR}`

Both URLs redirect (302) to `public.era.nih.gov`; `curl -L` follows automatically. The download endpoint enforces a rate limit of 200 req/min; the 2-second inter-request delay in §4 uses at most ~30 req/min, well within the limit.

NIH fiscal year N ends September 30 of year N. Example: FY2025 ends 2025-09-30.

### 6.2 Idempotency

If a ZIP file already exists in `--data-dir` and passes integrity check (non-zero size; ZIP magic bytes present), skip the download unless `--force-redownload` is set. Log: `Skipping {filename} — already present.`

---

## 7. NIH Gap Fill

### 7.1 Gap detection

If the CORDIS temporal anchor date is more recent than September 30 of the last downloaded ExPORTER fiscal year, a gap exists. The gap fiscal years are those whose **start date** (October 1 of the prior calendar year) falls on or before the temporal anchor — i.e., the fiscal year has begun and contains data as of the anchor date, even if it has not yet ended.

Example: last ExPORTER file is FY2025 (ends 2025-09-30), anchor is 2026-09-14 → gap fiscal year is FY2026 (started Oct 1, 2025, which is ≤ anchor; FY2027 starts Oct 1, 2026, which is > anchor and is excluded).

### 7.2 Preflight estimate

For each gap fiscal year, POST to the RePORTER API with `limit: 1` to retrieve `total_count`:

```
POST https://api.reporter.nih.gov/v2/projects/search
Content-Type: application/json

{
  "criteria": { "fiscal_years": [YEAR] },
  "limit": 1,
  "offset": 0
}
```

Sum `total_count` across all gap fiscal years. Estimated requests = `ceil(total / 500)`.

### 7.3 Off-hours warning

If estimated requests > 30 (approximately 30 seconds at 1 req/sec), print:

```
NIH gap fill: ~{total_count} records across {N} fiscal year(s), ~{estimated_requests} API
requests (~{estimated_minutes} min at 1 req/sec).
NIH recommends running large jobs off-hours: 9PM–5AM EST (3AM–11AM CET).
Press Enter to continue or Ctrl+C to abort.
```

If estimated requests ≤ 30, proceed without prompting.

### 7.4 Gap fill execution

For each gap fiscal year, paginate through the RePORTER API at `limit: 500`, starting at `offset: 0`, incrementing by 500 until all records are retrieved or `offset` would exceed 14,999.

If `total_count` for a fiscal year exceeds 15,499 (the API hard cap), log a warning and continue; the manifest records the shortfall.

Each page response is written as a separate JSON file: `nih/gap_fill/fy{YEAR}_page_{N:04d}.json`.

Rate: **1 request per second**. Use a monotonic timer; do not rely on `time.sleep` alone.

---

## 8. Manifest

On completion (success or partial failure), write `{data-dir}/manifest.json`:

```json
{
  "schema_version": 1,
  "generated_at": "2026-11-07T10:00:00Z",
  "start_year": 2007,
  "cordis_anchor_date": "2026-09-14",
  "nih_exporter": {
    "fiscal_years": [2007, 2008, "...", 2025],
    "files": [
      {
        "fiscal_year": 2007,
        "project_file": "nih/exporter/RePORTER_PRJ_C_FY2007.zip",
        "abstract_file": "nih/exporter/RePORTER_PRJABS_C_FY2007.zip",
        "status": "ok"
      }
    ]
  },
  "nih_gap_fill": {
    "fiscal_years": [2026],
    "total_records_retrieved": 51200,
    "total_records_available": 51200,
    "shortfall": false,
    "files": [
      {
        "fiscal_year": 2026,
        "pages": ["nih/gap_fill/fy2026_page_0001.json"],
        "status": "ok"
      }
    ]
  },
  "cordis": {
    "anchor_source": "Last-Modified header",
    "programmes": [
      {
        "programme": "fp7",
        "file": "cordis/fp7/cordis-fp7projects-csv.zip",
        "status": "ok"
      },
      {
        "programme": "h2020",
        "file": "cordis/h2020/cordis-h2020projects-csv.zip",
        "status": "ok"
      },
      {
        "programme": "horizon_europe",
        "file": "cordis/horizon_europe/cordis-HORIZONprojects-csv.zip",
        "status": "ok"
      }
    ]
  },
  "errors": []
}
```

`status` is `"ok"` or `"failed"`. Failed items are also recorded in `"errors"` with the filename and error message. The script exits with code `1` if any errors are present.

---

## 9. Prerequisites for Contract 01

The following field-name verifications are **not needed for this contract** but must be completed before Contract 01 (Common Data Model) can be written. They will be resolved by inspecting the downloaded ZIP headers after this contract is implemented.

- CORDIS CSV field names (title, objective/abstract, start date, end date, funding amount, coordinator, etc.)
- NIH ExPORTER project CSV field names (title, PI, org, amount, activity code, etc.)
- NIH ExPORTER abstract CSV field name for abstract text

---

## 10. Test Surface

The sub-agent implementing this contract must write tests covering at minimum:

- **Temporal anchor extraction:** a mocked HEAD/GET response with a `Last-Modified` header produces the correct anchor date; a response without the header raises with the specified error message
- **Gap detection:** given a last ExPORTER year and an anchor date, correctly identifies gap fiscal years
- **Off-hours warning threshold:** jobs ≤ 30 estimated requests proceed silently; jobs > 30 prompt
- **Preflight estimate calculation:** `ceil(total_count / 500)` is correct
- **Idempotency:** a file that already exists and passes integrity check is not re-downloaded
- **Integrity check:** a zero-byte file or non-ZIP file fails the check and is re-downloaded
- **Manifest structure:** a completed run produces a valid manifest matching the schema above
- **Exit code:** exits `1` when any item in `errors` is non-empty
- **Rate limiting:** consecutive requests to the same host are separated by ≥ 2 seconds (ExPORTER/CORDIS) or ≥ 1 second (RePORTER API)

HTTP calls must be mocked in tests — no live network calls.
