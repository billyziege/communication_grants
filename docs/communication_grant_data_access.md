# Communication Grant Data Access — Project Roadmap

**Authors:** Brandon Zerbe and the collaborating Claude session  
**Date:** 2026-10-29  
**Status:** Draft — pre-implementation

---

## 1. Purpose

This project builds a local, text-searchable database and query interface for grant funding data from two sources:

- **NIH RePORTER** — U.S. National Institutes of Health funded research portfolio
- **CORDIS** — EU Community Research and Development Information Service (Horizon Europe, Horizon 2020, FP7)

The immediate goal is to support a research paper analyzing funding patterns related to **communication and policy** over approximately the past 10 years. The tool is designed for shared localhost use by a small research team, not public deployment.

---

## 2. Data Sources

### 2.1 NIH — ExPORTER Bulk Download

- **Access method:** NIH ExPORTER annual bulk files (ZIP-compressed CSV), one project file and one abstract file per fiscal year. Available at `reporter.nih.gov/exporter`. No authentication required.
- **Historical range:** Files available from FY1985 onward. Download from the chosen `--start-year` to `--end-year` (script arguments).
- **Full-text search:** Via local SQLite FTS5 after bulk load — abstracts are a separate annual file
- **Local storage needed:** Yes — one-time bulk download, loaded into SQLite
- **File sizes:** Annual project files ~40–68MB (CSV, recent years); abstract files comparable. Total for 2007–2025 estimated at ~1–2GB CSV, producing a SQLite DB of ~1–3GB with FTS5 indexes
- **Download constraints:** No published rate limit for static file downloads (the 1 req/sec and off-hours guidance applies to the RePORTER API, not ExPORTER). Polite practice for `build_db.py`: set an identifying `User-Agent` header and a 2-second delay between file fetches. For a ~20-file build this adds negligible time.
- **Reproducibility:** The build script accepts `--start-year` / `--end-year` arguments. The date window used for any published analysis is noted in the paper; since the script is public, the dataset is fully reproducible.
- **Streaming ZIP format:** NIH ExPORTER project ZIPs (confirmed for FY2025) use ZIP general-purpose bit flag `0x0008` (data descriptor), where compressed and uncompressed sizes are stored in a trailing record rather than the local file header. Python's `zipfile.ZipFile` raises `BadZipFile` on these files. The DB build pipeline reads them via raw deflate streaming (`zlib.decompressobj(-15)`). Abstract ZIPs use the standard format and open normally.
- **Gap fill:** ExPORTER releases annually and lags the fiscal year end by an unknown interval. The effective NIH end date is set by the CORDIS bulk download's last updated date (see §2.2), ensuring both sources are temporally aligned. If the CORDIS end date is more recent than the last ExPORTER file, `build_db.py` fills the gap using the live RePORTER API (v2, `fiscal_years` filter). See §3.3 for gap-fill behavior and rate-limit surfacing.

### 2.2 EU CORDIS

- **Access method:** Bulk dataset downloads from the EU Open Data Portal (`data.europa.eu`)
- **Framework programmes covering ~18 years:**
  - FP7: 2007–2013
  - Horizon 2020: 2014–2020
  - Horizon Europe: 2021–present
- **Full-text search:** Via local SQLite FTS5 after bulk load — project objectives (EU equivalent of abstracts) are included in the bulk files, but field names require verification against a sample file before the data model contract is written
- **Local storage needed:** Yes — one-time bulk download, loaded into SQLite
- **robots.txt note:** CORDIS disallows `/search?` paths; programmatic use of the web search interface is not permitted. The bulk download route is the correct and explicitly supported path
- **Download constraints:** The KTH R library notes that CORDIS direct file downloads are rate limited; no published numeric limit found. Polite practice for `build_db.py`: identifying `User-Agent` header and 2-second delay between fetches. Three framework programme files total — minimal concern in practice.
- **Temporal anchor:** The CORDIS bulk download's last updated date (extracted from file metadata or the most recent grant date in the data) is used as the canonical end boundary for the entire dataset — including the NIH pull. This ensures both sources cover the same time window. `build_db.py` reports this date to the user: *"Dataset covers [--start-year] through [CORDIS last updated: YYYY-MM-DD], both sources aligned."*
- **Gap fill for Horizon Europe:** FP7 and Horizon 2020 are closed programmes — their bulk downloads are complete and static. Horizon Europe (ongoing) is refreshed periodically (lag measured in weeks). No API gap fill is attempted for CORDIS; the bulk snapshot is accepted as the end boundary.
- **SPARQL alternative:** EURIO Knowledge Graph is available but was ruled out in favor of symmetric bulk-download architecture with NIH (see §3.3)

---

## 3. Architecture

### 3.1 Design Goals

1. **Symmetric query access** — both NIH and CORDIS answer the same interface so the research workflow is identical regardless of source
2. **Unified data model** — a normalized `Grant` type shared across both backends enables direct comparison in the paper
3. **Colleague-accessible** — a GraphQL endpoint allows team members to write their own queries without touching the application code
4. **Deployable with minimal friction** — Docker Compose, single command to start

### 3.2 Stack

| Layer | Technology | Notes |
|---|---|---|
| API server | FastAPI + Strawberry | Relay-compatible GraphQL schema |
| Abstraction layer | Python `GrantRepository` interface | `NIHBackend` and `CORDISBackend` implementations |
| NIH backend | SQLite + FTS5 | Loaded from ExPORTER bulk files |
| CORDIS backend | SQLite + FTS5 | Loaded from CORDIS bulk files |
| DB build pipeline | `build_db.py` | Isolated from app; accepts `--start-year` / `--end-year`; downloads, validates, normalizes, loads both sources into a single SQLite DB |
| Frontend | React + Relay | Localhost only |
| Deployment | Docker Compose | `api` service, `web` service, named volume for SQLite DB file |

### 3.3 Key Decisions and Rationale

**Why ExPORTER bulk download over live NIH RePORTER API?**  
The NIH RePORTER API is well-designed but introduces infrastructure disproportionate to the task: 1 req/sec rate limiting, off-hours scheduling for large jobs, preflight count queries, an async job queue, and off-hours detection logic. Switching to ExPORTER annual bulk files eliminates all of this from the running application. More importantly, it makes both data sources symmetric — both are bulk download → SQLite — so the query layer, the data model, and the DB build pipeline are identical for NIH and CORDIS. The tradeoff is freshness: ExPORTER releases annually and lags the fiscal year end by an unknown interval.

**ExPORTER gap-fill via live API:**  
`build_db.py` handles the currency gap automatically, anchored to the CORDIS bulk snapshot date:

1. Download CORDIS bulk files first; extract the last updated date (`cordis_end_date`)
2. Download ExPORTER files through the last complete fiscal year
3. If `cordis_end_date` is more recent than the last ExPORTER file: fill the gap using the live RePORTER API for fiscal years between the last ExPORTER file and `cordis_end_date`
4. Preflight: POST `limit: 1` per gap fiscal year to estimate total records
5. If estimated API requests are large enough to warrant off-hours: print a warning — *"Gap fill requires ~X requests (~Y min at 1 req/sec). NIH recommends off-hours runs (9PM–5AM EST / 3AM–11AM CET). Press Enter to continue or Ctrl+C to abort."* — then wait for input
6. Proceed at 1 req/sec; results loaded into the same SQLite DB as ExPORTER data
7. Report to user: *"Dataset covers [--start-year] through [cordis_end_date], both sources aligned."*

Rate-limit complexity is entirely contained in `build_db.py` and never touches the running web application. In practice the gap is usually one partial fiscal year, so the warning will rarely trigger.

**Why not SPARQL/EURIO Knowledge Graph?**  
SPARQL would require two mental models, two query languages, and two result shapes — one for NIH (bulk/SQLite) and one for EU (SPARQL). Symmetric bulk-download architecture was prioritized. If funding network analysis (co-funding, institutional partnerships) becomes central to the paper, SPARQL is worth revisiting.

**Why SQLite + FTS5 over OpenSearch?**  
OpenSearch requires a running cluster and only pays off at multi-million-record scale or with semantic/vector search requirements. SQLite FTS5 ships with Python's stdlib, produces a single portable file, and provides relevance-ranked full-text search sufficient for this corpus size.

**Why GraphQL (Strawberry) over REST?**  
A GraphQL schema is self-documenting — colleagues can introspect it and write queries without reading application code. Strawberry's native Relay support also removes impedance mismatch with the frontend.

**Why Relay over Apollo Client?**  
Familiarity: Relay has been used on prior projects and Strawberry supports it natively. Apollo Client is lighter but introduces an unfamiliar toolchain for no net benefit.

**Normalization ownership and provenance:**  
All field mapping and normalization from source schemas (NIH ExPORTER CSV columns, CORDIS CSV columns) to the unified `Grant` schema happens entirely in `build_db.py`. By the time data enters SQLite, it is fully normalized — the query layer and GraphQL resolvers have no source-awareness and perform no transformation. Provenance is preserved explicitly as first-class fields on every row: `source` (`nih` | `cordis`), `source_id` (original identifier from the source system), `source_programme` (CORDIS only: `fp7` | `h2020` | `horizon_europe`), and `source_url` (link back to the original record). These fields are exposed through the GraphQL `Grant` type so that research outputs can always be traced back to their origin. FTS5 queries are written as raw SQL — not routed through an ORM — because FTS5's `MATCH` syntax does not map cleanly to ORM query builders.

**Why not true GraphQL federation?**  
Overkill at this scale. Both backends are resolved through a single Strawberry schema — this is standard multi-source resolution, not a federated gateway architecture.

**Overwrite protection and backup in `build_db.py`:**  
When `build_db.py` detects an existing non-empty database, it pauses before writing. The prompt differs based on whether `--backup-db` was passed:

- **With `--backup-db [PATH]`:** `"grants.db already exists with N grants. Will back up to {path} before writing.\nPress Enter to continue or Ctrl+C to abort."` — backup (`shutil.copy2`) runs after the user confirms, before any writes.
- **Without `--backup-db`:** `"grants.db already exists with N grants. You can abort and rerun with --backup-db to preserve current state.\nPress Enter to continue or Ctrl+C to abort."`

If no path is given with `--backup-db`, the backup is auto-named `{db_path}.{YYYYMMDDHHMMSS}.bak`. This protects manual corrections or annotations made directly to the database between runs.

**Why Docker Compose?**  
Deployment simplicity for sharing with colleagues. The SQLite file lives on a named volume to survive image rebuilds.

---

## 4. Implementation Roadmap

### Phase 1 — Documentation (current)
- [x] `docs/communication_grant_data_access.md` — this document
- [x] `README.md` — installation and quick-start orientation
- [ ] `docs/contracts/` — one contract file per topic (see §4.2)

### Phase 2 — Contracts and Implementation (iterative)

Each contract topic is discussed, researched, and written before the corresponding implementation. A sub-agent uses the contract to build tests, implement code, and resolve failures.

#### 4.2 Contract Topics (in dependency order)

**Prerequisites before Contract 1:**
- Verify CORDIS bulk CSV field names against a sample file to confirm objective/summary field name
- Verify NIH ExPORTER abstract CSV field names against a sample file

| # | Contract | Scope |
|---|---|---|
| 1 | Common data model | Unified `Grant` schema — shared fields, explicit provenance fields (`source`, `source_id`, `source_programme`, `source_url`); field mapping from NIH ExPORTER and CORDIS to shared schema; provenance is first-class, not an afterthought |
| 2 | Repository interface | `GrantRepository` interface; query method signatures; `source` filter; result pagination shape |
| 3 | DB build pipeline | `build_db.py`; `--start-year` / `--end-year` CLI args; NIH ExPORTER download + parse + normalize (streaming ZIP for project files); NIH country name → ISO alpha-2 lookup; ExPORTER gap detection; live RePORTER API gap fill (preflight estimate, warn-and-proceed, 1 req/sec); CORDIS bulk download + parse + normalize; full normalization to unified `Grant` schema with explicit provenance fields; SQLite schema + FTS5 setup; idempotent load; polite download behavior (User-Agent, 2s delay); overwrite detection + confirmation prompt; `--backup-db [PATH]` to copy existing DB before overwriting |
| 4 | SQLite query layer | Single `GrantRepository` implementation over unified SQLite schema; FTS5 `MATCH` queries written as raw SQL (not ORM); `source` column filter for per-source queries; provenance fields exposed; result pagination |
| 5 | GraphQL schema | Strawberry types; Relay connections and pagination; resolver wiring to repository; provenance fields in `Grant` type |
| 6 | Frontend | Relay queries; component contracts; search input and results display |
| 7 | Docker Compose | Service definitions; named volume for SQLite DB file; startup order; `build_db.py` invocation documented |

### Phase 3 — DB Build and Distribution

The SQLite database is a **derived artifact** — the ExPORTER and CORDIS CSV files are the source of truth. The DB is not stored in git.

- `build_db.py` is the only supported way to produce the database
- It accepts `--start-year` / `--end-year` arguments; the date window used for any published analysis is noted in the paper
- Pre-built DB distributions:
  - **GitHub Release attachment** (up to 2GB per file) — for sharing with colleagues who don't want to run the build
  - **Zenodo deposit** — if the dataset is cited in the paper (free, DOI-citable, up to 50GB)
- Colleagues who want to reproduce or extend the dataset run `build_db.py` with the published date window

### Phase 4 — Deployment and Sharing
- Final Docker Compose configuration
- Instructions for colleagues: run `build_db.py` once, then `docker compose up`
- Notes on sharing the pre-built DB via GitHub Release or Zenodo

---

## 5. Open Questions

- **CORDIS objective field name:** Must be verified against a sample bulk file before Contract 1 (prerequisite)
- **NIH ExPORTER abstract field name:** Must be verified against a sample abstract CSV before Contract 1 (prerequisite)
- **Search vocabulary:** Controlled vocabulary alignment (NIH activity codes, CORDIS topic codes) for "communication and policy" is handled by the research team's domain expert; this is a prerequisite for meaningful queries but not for the technical build
- **FP7 inclusion:** The 10-year window (2016–2026) technically excludes most of FP7 (ended 2013); confirm with the research team whether FP7 data should be included for longer-range pattern analysis
- **Czech-specific filtering:** CORDIS data supports country filtering; confirm whether Czech partner/coordinator filtering is in scope for the paper

---

## 6. Out of Scope

- Public web deployment
- True GraphQL federation (Apollo Federation gateway architecture)
- Semantic/vector search
- Live NIH API queries (using ExPORTER bulk download instead)
- Real-time data from either source (both are point-in-time snapshots; annual refresh is sufficient for pattern analysis)
