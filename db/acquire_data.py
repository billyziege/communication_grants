#!/usr/bin/env python3
"""db/acquire_data.py — Data acquisition for communication grants research.

Downloads NIH ExPORTER and CORDIS bulk files, extracts the CORDIS temporal
anchor, fills the NIH gap via the RePORTER API when needed, and writes a
manifest.  Performs no parsing, normalisation, or database operations.

Usage:
    python db/acquire_data.py \\
        --start-year YYYY \\
        --data-dir PATH \\
        [--force-redownload]
"""
import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_AGENT = (
    "communication-grants-research/1.0 "
    "(academic research; contact: brandon.s.zerbe@gmail.com)"
)

CORDIS_URLS: dict[str, str] = {
    "fp7": "https://cordis.europa.eu/data/cordis-fp7projects-csv.zip",
    "h2020": "https://cordis.europa.eu/data/cordis-h2020projects-csv.zip",
    "horizon_europe": "https://cordis.europa.eu/data/cordis-HORIZONprojects-csv.zip",
}

CORDIS_DEST: dict[str, str] = {
    "fp7": "cordis/fp7/cordis-fp7projects-csv.zip",
    "h2020": "cordis/h2020/cordis-h2020projects-csv.zip",
    "horizon_europe": "cordis/horizon_europe/cordis-HORIZONprojects-csv.zip",
}

NIH_PROJECT_URL = (
    "https://reporter.nih.gov/services/exporter/DownloadFromDocService"
    "?DocType=EXPPRJ&KeyId={year}"
)
NIH_ABSTRACT_URL = (
    "https://reporter.nih.gov/services/exporter/DownloadFromDocService"
    "?DocType=EXPABS&KeyId={year}"
)
NIH_API_SEARCH_URL = "https://api.reporter.nih.gov/v2/projects/search"

INTER_HOST_DELAY: float = 2.0   # seconds between successive requests to same host
API_RATE_DELAY: float = 1.0     # seconds between successive RePORTER API calls

ZIP_MAGIC = b"PK\x03\x04"      # local-file-header signature

API_PAGE_LIMIT = 500            # records per API page
API_OFFSET_MAX = 14999          # API hard-cap: max starting offset
API_CAP_RECORDS = 15499         # API hard-cap: max retrievable records per FY

WARN_THRESHOLD = 30             # estimated API requests above which we warn


# ---------------------------------------------------------------------------
# Integrity helpers
# ---------------------------------------------------------------------------

def check_integrity(path: Path) -> bool:
    """Return True iff *path* exists, is non-empty, and starts with ZIP magic."""
    if not path.exists():
        return False
    if path.stat().st_size == 0:
        return False
    with open(path, "rb") as fh:
        magic = fh.read(4)
    return magic == ZIP_MAGIC


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Enforce a minimum delay between successive requests to the same host."""

    def __init__(self) -> None:
        self._last: dict[str, float] = {}

    def wait(self, host: str, min_interval: float) -> None:
        now = time.monotonic()
        last = self._last.get(host, 0.0)
        gap = now - last
        if gap < min_interval:
            time.sleep(min_interval - gap)
        self._last[host] = time.monotonic()


# ---------------------------------------------------------------------------
# Low-level HTTP helpers
# ---------------------------------------------------------------------------

def _host(url: str) -> str:
    return urlparse(url).hostname or url


def _urlopen(req: urllib.request.Request) -> object:
    """Thin wrapper so tests can patch a single symbol."""
    return urllib.request.urlopen(req)  # type: ignore[return-value]


def _get(url: str, rate_limiter: RateLimiter,
         host_delay: float = INTER_HOST_DELAY) -> bytes:
    """GET *url*, return body bytes.  Enforces rate limit per host."""
    rate_limiter.wait(_host(url), host_delay)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _urlopen(req) as resp:
        return resp.read()


def _api_post(payload: dict, rate_limiter: RateLimiter) -> dict:
    """POST to the NIH RePORTER API; return parsed JSON.  Enforces 1 req/s."""
    rate_limiter.wait(_host(NIH_API_SEARCH_URL), API_RATE_DELAY)
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        NIH_API_SEARCH_URL,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with _urlopen(req) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Temporal anchor
# ---------------------------------------------------------------------------

def get_anchor_date(rate_limiter: RateLimiter) -> date:
    """HEAD the Horizon Europe ZIP; parse its Last-Modified header."""
    url = CORDIS_URLS["horizon_europe"]
    rate_limiter.wait(_host(url), INTER_HOST_DELAY)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT},
        method="HEAD",
    )
    with _urlopen(req) as resp:
        lm = resp.headers.get("Last-Modified")
    if not lm:
        raise RuntimeError(
            "CORDIS Horizon Europe ZIP returned no Last-Modified header — "
            "cannot determine temporal anchor"
        )
    return parsedate_to_datetime(lm).date()


# ---------------------------------------------------------------------------
# File download with idempotency
# ---------------------------------------------------------------------------

def download_file(
    url: str,
    dest: Path,
    rate_limiter: RateLimiter,
    force: bool = False,
    host_delay: float = INTER_HOST_DELAY,
) -> None:
    """Download *url* to *dest*.  Skip if the file already passes integrity check."""
    if not force and check_integrity(dest):
        print(f"Skipping {dest.name} — already present.")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = _get(url, rate_limiter, host_delay)
    dest.write_bytes(data)


# ---------------------------------------------------------------------------
# NIH fiscal-year helpers
# ---------------------------------------------------------------------------

def last_complete_exporter_year(anchor: date) -> int:
    """Return the last NIH FY whose September-30 end date is ≤ *anchor*."""
    # FY N ends on September 30 of calendar year N.
    if anchor >= date(anchor.year, 9, 30):
        return anchor.year
    return anchor.year - 1


def detect_gap_years(last_exporter_year: int, anchor: date) -> list[int]:
    """Return FYs that have started but are absent from ExPORTER.

    A fiscal year is a gap year when:
      - its year number is greater than *last_exporter_year*, AND
      - its start date (October 1 of the prior calendar year) is on or before
        *anchor* (the fiscal year has begun and contains data as of anchor).
    """
    gap: list[int] = []
    candidate = last_exporter_year + 1
    while True:
        fy_start = date(candidate - 1, 10, 1)
        if fy_start > anchor:
            break
        gap.append(candidate)
        candidate += 1
    return gap


def estimate_requests(total_count: int) -> int:
    """Return the number of API pages needed to fetch *total_count* records."""
    return math.ceil(total_count / API_PAGE_LIMIT)


# ---------------------------------------------------------------------------
# NIH gap fill
# ---------------------------------------------------------------------------

def api_preflight(
    gap_years: list[int], rate_limiter: RateLimiter
) -> dict[int, int]:
    """Return {year: total_count} from single-record probes for each gap year."""
    counts: dict[int, int] = {}
    for year in gap_years:
        result = _api_post(
            {"criteria": {"fiscal_years": [year]}, "limit": 1, "offset": 0},
            rate_limiter,
        )
        counts[year] = result["meta"]["total"]
    return counts


def gap_fill(
    gap_years: list[int],
    out_dir: Path,
    rate_limiter: RateLimiter,
) -> dict:
    """Paginate through the RePORTER API for each gap year; write JSON files.

    Returns the ``nih_gap_fill`` portion of the manifest.
    """
    gap_dir = out_dir / "nih" / "gap_fill"
    gap_dir.mkdir(parents=True, exist_ok=True)

    # --- preflight estimate ---
    year_counts = api_preflight(gap_years, rate_limiter)
    total_available = sum(year_counts.values())
    estimated = estimate_requests(total_available)

    if estimated > WARN_THRESHOLD:
        estimated_minutes = round(estimated / 60, 1)
        n = len(gap_years)
        print(
            f"NIH gap fill: ~{total_available} records across {n} fiscal "
            f"year(s), ~{estimated} API requests (~{estimated_minutes} min "
            f"at 1 req/sec).\n"
            f"NIH recommends running large jobs off-hours: "
            f"9PM–5AM EST (3AM–11AM CET).\n"
            f"Press Enter to continue or Ctrl+C to abort."
        )
        input()

    # --- paginate ---
    files_by_year: dict[int, list[str]] = {}
    total_retrieved = 0
    shortfall = False

    for year in gap_years:
        total_count = year_counts[year]
        if total_count > API_CAP_RECORDS:
            shortfall = True
            print(
                f"WARNING: FY{year} has {total_count} records which exceeds "
                f"the API cap ({API_CAP_RECORDS}). Data will be incomplete."
            )

        pages: list[str] = []
        offset = 0
        retrieved = 0

        while offset <= API_OFFSET_MAX:
            result = _api_post(
                {
                    "criteria": {"fiscal_years": [year]},
                    "limit": API_PAGE_LIMIT,
                    "offset": offset,
                },
                rate_limiter,
            )
            page_num = (offset // API_PAGE_LIMIT) + 1
            page_file = gap_dir / f"fy{year}_page_{page_num:04d}.json"
            page_file.write_text(json.dumps(result))
            pages.append(str(page_file.relative_to(out_dir)))

            batch = result.get("results", [])
            retrieved += len(batch)
            offset += API_PAGE_LIMIT

            if retrieved >= total_count or not batch:
                break

        total_retrieved += retrieved
        files_by_year[year] = pages

    return {
        "fiscal_years": gap_years,
        "total_records_retrieved": total_retrieved,
        "total_records_available": total_available,
        "shortfall": shortfall,
        "files": [
            {
                "fiscal_year": y,
                "pages": files_by_year[y],
                "status": "ok",
            }
            for y in gap_years
        ],
    }


# ---------------------------------------------------------------------------
# Main acquisition logic
# ---------------------------------------------------------------------------

def run(start_year: int, data_dir: Path, force: bool) -> int:
    """Acquire all data; return 0 on success, 1 if any item failed."""
    rate_limiter = RateLimiter()
    errors: list[dict] = []

    # --- temporal anchor ---
    print("Fetching CORDIS temporal anchor…")
    anchor = get_anchor_date(rate_limiter)
    print(f"CORDIS temporal anchor: {anchor}")
    print(f"Both sources will cover {start_year} through {anchor}.")

    # --- CORDIS downloads ---
    cordis_programmes: list[dict] = []
    for prog, url in CORDIS_URLS.items():
        dest = data_dir / CORDIS_DEST[prog]
        try:
            download_file(url, dest, rate_limiter, force=force)
            cordis_programmes.append({
                "programme": prog,
                "file": str(dest.relative_to(data_dir)),
                "status": "ok",
            })
        except Exception as exc:
            rel = str(dest.relative_to(data_dir))
            errors.append({"file": rel, "error": str(exc)})
            cordis_programmes.append({
                "programme": prog,
                "file": rel,
                "status": "failed",
            })

    # --- NIH ExPORTER downloads ---
    last_fy = last_complete_exporter_year(anchor)
    nih_exporter_dir = data_dir / "nih" / "exporter"
    nih_exporter_dir.mkdir(parents=True, exist_ok=True)

    nih_files: list[dict] = []
    for year in range(start_year, last_fy + 1):
        prj_dest = nih_exporter_dir / f"RePORTER_PRJ_C_FY{year}.zip"
        abs_dest = nih_exporter_dir / f"RePORTER_PRJABS_C_FY{year}.zip"
        prj_url = NIH_PROJECT_URL.format(year=year)
        abs_url = NIH_ABSTRACT_URL.format(year=year)
        status = "ok"

        try:
            download_file(prj_url, prj_dest, rate_limiter, force=force)
        except Exception as exc:
            rel = str(prj_dest.relative_to(data_dir))
            errors.append({"file": rel, "error": str(exc)})
            status = "failed"

        try:
            download_file(abs_url, abs_dest, rate_limiter, force=force)
        except Exception as exc:
            rel = str(abs_dest.relative_to(data_dir))
            errors.append({"file": rel, "error": str(exc)})
            status = "failed"

        nih_files.append({
            "fiscal_year": year,
            "project_file": str(prj_dest.relative_to(data_dir)),
            "abstract_file": str(abs_dest.relative_to(data_dir)),
            "status": status,
        })

    # --- NIH gap fill ---
    gap_years = detect_gap_years(last_fy, anchor)
    if gap_years:
        try:
            gap_manifest = gap_fill(gap_years, data_dir, rate_limiter)
        except Exception as exc:
            errors.append({"file": "nih/gap_fill", "error": str(exc)})
            gap_manifest = {
                "fiscal_years": gap_years,
                "total_records_retrieved": 0,
                "total_records_available": 0,
                "shortfall": False,
                "files": [
                    {"fiscal_year": y, "pages": [], "status": "failed"}
                    for y in gap_years
                ],
            }
    else:
        gap_manifest = {
            "fiscal_years": [],
            "total_records_retrieved": 0,
            "total_records_available": 0,
            "shortfall": False,
            "files": [],
        }

    # --- manifest ---
    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "start_year": start_year,
        "cordis_anchor_date": anchor.isoformat(),
        "nih_exporter": {
            "fiscal_years": list(range(start_year, last_fy + 1)),
            "files": nih_files,
        },
        "nih_gap_fill": gap_manifest,
        "cordis": {
            "anchor_source": "Last-Modified header",
            "programmes": cordis_programmes,
        },
        "errors": errors,
    }

    manifest_path = data_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Manifest written to {manifest_path}")

    return 1 if errors else 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Acquire NIH and CORDIS grant data."
    )
    parser.add_argument(
        "--start-year", type=int, required=True,
        help="First fiscal year to include (e.g. 2007).",
    )
    parser.add_argument(
        "--data-dir", type=Path, required=True,
        help="Directory where downloaded files and manifest are written.",
    )
    parser.add_argument(
        "--force-redownload", action="store_true",
        help="Re-download all files even if they already exist.",
    )
    args = parser.parse_args()
    sys.exit(run(args.start_year, args.data_dir, args.force_redownload))


if __name__ == "__main__":
    main()
