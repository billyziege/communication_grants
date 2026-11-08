# Contract 01 — Common Data Model

**Status:** Ready for implementation  
**Depends on:** Contract 00 (`acquire_data.py` — downloaded files must exist)  
**Prerequisite for:** Contract 03 (DB build pipeline), Contract 04 (SQLite query layer)

---

## 1. Purpose and Scope

This contract defines the unified `Grant` SQLite schema, the FTS5 full-text index, and the authoritative field mappings from both source formats to that schema. All normalization from source CSV columns to unified fields happens in `build_db.py` (Contract 03); by the time a row enters SQLite it is fully normalized. The query layer and resolvers have no source-awareness and perform no transformation.

**In scope:**
- `grants` table DDL
- `grants_fts` FTS5 virtual table DDL
- Field mapping: NIH ExPORTER project + abstract CSVs → `grants`
- Field mapping: CORDIS `project.csv` + `organization.csv` → `grants`
- Normalization rules for dates, amounts, currencies, and source-specific identifiers
- Provenance fields on every row

**Out of scope:**
- The `GrantRepository` interface (Contract 02)
- The build pipeline that populates the schema (Contract 03)
- GraphQL types derived from this schema (Contract 05)

---

## 2. `grants` Table

```sql
CREATE TABLE IF NOT EXISTS grants (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Core shared fields
    title             TEXT    NOT NULL,
    abstract          TEXT,
    start_date        TEXT,           -- ISO 8601: YYYY-MM-DD; NULL if not present
    end_date          TEXT,           -- ISO 8601: YYYY-MM-DD; NULL if not present
    funding_amount    REAL,           -- raw value in source currency; NULL if not present
    funding_currency  TEXT,           -- 'USD' (NIH) or 'EUR' (CORDIS); NULL if amount NULL
    organization      TEXT,           -- ORG_NAME (NIH) or CORDIS coordinator name
    country           TEXT,           -- ISO alpha-2 code; both NIH and CORDIS normalized (see §6.4)

    -- Provenance (first-class, non-null)
    source            TEXT    NOT NULL CHECK(source IN ('nih', 'cordis')),
    source_id         TEXT    NOT NULL,   -- APPLICATION_ID (NIH) or project id (CORDIS)
    source_programme  TEXT,               -- NULL for NIH; 'fp7'/'h2020'/'horizon_europe' for CORDIS
    source_url        TEXT,               -- deep link back to source record

    -- Source-specific metadata (JSON)
    metadata          TEXT,           -- see §5 for per-source keys

    UNIQUE(source, source_id)
);
```

---

## 3. FTS5 Virtual Table

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS grants_fts USING fts5(
    title,
    abstract,
    content=grants,
    content_rowid=id,
    tokenize='unicode61'
);
```

Using `content=grants` mode: the FTS index stores no data of its own and references the main table. After bulk-inserting all rows, the build pipeline rebuilds the index in one operation:

```sql
INSERT INTO grants_fts(grants_fts) VALUES('rebuild');
```

FTS queries use the `MATCH` syntax against `grants_fts` and join back to `grants` on `rowid = grants.id`.

---

## 4. Field Mapping — NIH ExPORTER

NIH data comes from two CSVs per fiscal year, joined on `APPLICATION_ID`:
- `RePORTER_PRJ_C_FY{YEAR}.csv` — project metadata (comma-delimited; **streaming ZIP format** — see §4.1)
- `RePORTER_PRJABS_C_FY{YEAR}.csv` — abstract text (comma-delimited; standard ZIP)

| `grants` column | Source field | Notes |
|---|---|---|
| `title` | `PROJECT_TITLE` | Strip surrounding whitespace |
| `abstract` | `ABSTRACT_TEXT` | From abstract CSV; NULL if no matching row |
| `start_date` | `PROJECT_START` | Normalize to `YYYY-MM-DD` (see §6.1) |
| `end_date` | `PROJECT_END` | Normalize to `YYYY-MM-DD`; NULL if blank |
| `funding_amount` | `TOTAL_COST` | Parse as REAL; NULL if blank or non-numeric |
| `funding_currency` | *(constant)* | `'USD'`; NULL if `funding_amount` is NULL |
| `organization` | `ORG_NAME` | Strip whitespace |
| `country` | `ORG_COUNTRY` | Normalize to ISO alpha-2 via lookup (see §6.4); NULL if unrecognized |
| `source` | *(constant)* | `'nih'` |
| `source_id` | `APPLICATION_ID` | Store as text |
| `source_programme` | *(constant)* | `NULL` |
| `source_url` | `APPLICATION_ID` | `https://reporter.nih.gov/project-details/{APPLICATION_ID}` |
| `metadata` | multiple fields | See §5.1 |

### 4.1 Streaming ZIP format

NIH ExPORTER **project** ZIPs (confirmed FY2025) use ZIP general-purpose bit flag `0x0008` (data descriptor), which causes Python's `zipfile.ZipFile` to raise `BadZipFile`. Use raw deflate streaming:

```python
import zlib, struct

def iter_csv_lines(zip_path: Path) -> Iterator[bytes]:
    with open(zip_path, 'rb') as f:
        # skip local file header
        f.read(4)                                      # signature
        f.read(2 + 2 + 2 + 2 + 2 + 4 + 4 + 4)        # fixed fields
        fname_len = struct.unpack('<H', f.read(2))[0]
        extra_len = struct.unpack('<H', f.read(2))[0]
        f.read(fname_len + extra_len)
        # stream-decompress
        d = zlib.decompressobj(-15)
        buf = b''
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            buf += d.decompress(chunk)
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1)
                yield line
        if buf:
            yield buf
```

Abstract ZIPs open normally with `zipfile.ZipFile`.

---

## 5. Field Mapping — CORDIS

CORDIS data comes from two CSVs inside each programme ZIP, semicolon-delimited:
- `project.csv` — project metadata and objectives
- `organization.csv` — participant and coordinator organizations (join on `projectID`)

The coordinator row is the one where `organization.csv.role = 'coordinator'`. If a project has no coordinator row, leave `organization` and `country` NULL and log a warning to stderr.

| `grants` column | Source field | Notes |
|---|---|---|
| `title` | `project.title` | Strip whitespace |
| `abstract` | `project.objective` | Strip whitespace; NULL if blank |
| `start_date` | `project.startDate` | Already ISO 8601 (`YYYY-MM-DD`); NULL if blank |
| `end_date` | `project.endDate` | Already ISO 8601; NULL if blank |
| `funding_amount` | `project.ecMaxContribution` | Normalize decimal (see §6.2); NULL if blank |
| `funding_currency` | *(constant)* | `'EUR'`; NULL if `funding_amount` is NULL |
| `organization` | `organization.name` (coordinator) | NULL if no coordinator row |
| `country` | `organization.country` (coordinator) | ISO alpha-2 (e.g. `'CZ'`); NULL if no coordinator row |
| `source` | *(constant)* | `'cordis'` |
| `source_id` | `project.id` | Store as text |
| `source_programme` | *(derived from filename)* | `'fp7'` / `'h2020'` / `'horizon_europe'` — see §5.1 |
| `source_url` | `project.id` | `https://cordis.europa.eu/project/id/{id}` |
| `metadata` | multiple fields | See §5.2 |

### 5.1 `source_programme` derivation

Determined by which file the row came from, not from the `frameworkProgramme` field value:

| File | `source_programme` |
|---|---|
| `cordis-fp7projects-csv.zip` | `'fp7'` |
| `cordis-h2020projects-csv.zip` | `'h2020'` |
| `cordis-HORIZONprojects-csv.zip` | `'horizon_europe'` |

---

## 6. Normalization Rules

### 6.1 NIH date format

NIH `PROJECT_START` and `PROJECT_END` arrive in one of two formats: `MM/DD/YYYY` or `YYYY-MM-DD`. Normalize to ISO 8601 `YYYY-MM-DD`. Blank or unparseable values → NULL.

### 6.2 CORDIS decimal format

CORDIS amount fields use a comma as the decimal separator (e.g. `"2073781,25"`). Replace `,` with `.` before casting to REAL. Values surrounded by double-quotes in the semicolon-delimited CSV must be unquoted first. Blank or unparseable values → NULL.

### 6.4 NIH country name → ISO alpha-2

NIH `ORG_COUNTRY` values are uppercase country names (e.g. `'UNITED STATES'`, `'CANADA'`, `'UNITED KINGDOM'`). Normalize to ISO alpha-2 using a hardcoded lookup dict defined in the build pipeline (Contract 03) — not a SQLite table. Unrecognized names produce NULL with a stderr warning that includes the unrecognized value.

This contract specifies only the target format (ISO alpha-2 or NULL) and the NULL-on-unknown behavior. The lookup dict itself belongs to Contract 03.

### 6.5 Deduplication

The `UNIQUE(source, source_id)` constraint is the deduplication key. The build pipeline uses `INSERT OR REPLACE` so that re-runs with the same files are idempotent.

---

## 7. `metadata` JSON — Per-Source Keys

### 7.1 NIH

```json
{
  "activity_code":    "R01",
  "ic_name":          "NATIONAL CANCER INSTITUTE",
  "core_project_num": "R01CA123456",
  "pi_names":         "SMITH, JOHN; DOE, JANE",
  "fy":               2025
}
```

Source fields: `ACTIVITY`, `IC_NAME`, `CORE_PROJECT_NUM`, `PI_NAMEs`, `FY`.

### 7.2 CORDIS

```json
{
  "acronym":           "SolDAC",
  "topics":            "HORIZON-CL5-2021-D2-01-11",
  "status":            "SIGNED",
  "ec_signature_date": "2022-05-12",
  "keywords":          "..."
}
```

Source fields: `acronym`, `topics`, `status`, `ecSignatureDate`, `keywords`.

---

## 8. Test Surface

The sub-agent implementing this contract must write tests covering at minimum:

- **Schema creation:** `grants` table and `grants_fts` FTS5 table are created without error on a fresh in-memory SQLite DB
- **UNIQUE constraint:** inserting two rows with the same `(source, source_id)` raises or replaces (verify `INSERT OR REPLACE` behavior)
- **NIH date normalization:** `MM/DD/YYYY` → `YYYY-MM-DD`; `YYYY-MM-DD` passthrough; blank → NULL; garbage → NULL
- **CORDIS decimal normalization:** `"2073781,25"` → `2073781.25`; blank → NULL; `"0,00"` → `0.0`
- **NIH streaming ZIP reader:** given a file with known content in streaming-ZIP format, `iter_csv_lines` yields the correct lines
- **NIH country normalization:** `'UNITED STATES'` → `'US'`; `'UNITED KINGDOM'` → `'GB'`; unrecognized name → NULL with stderr warning containing the unrecognized value
- **CORDIS coordinator join:** a mock `organization.csv` with coordinator and participant rows — returns coordinator `name` and `country`; no coordinator row → returns NULL with warning
- **`source_programme` derivation:** each of the three filenames maps to the correct programme slug
- **FTS5 rebuild:** after insert + rebuild, an FTS `MATCH` query returns the expected row
- **`metadata` JSON structure:** NIH and CORDIS metadata dicts contain exactly the keys defined in §7; missing source fields produce NULL values for those keys, not KeyErrors
- **`source_url` construction:** correct URL template for each source

HTTP calls must be mocked; file I/O uses `tmp_path` (pytest fixture) or `sqlite3` in-memory.
