"""db/models.py — Common data model for communication grants research.

Defines:
- SQLite schema (grants table + grants_fts FTS5 virtual table)
- Normalization helpers: NIH dates, CORDIS decimals, country codes
- Streaming ZIP reader for NIH ExPORTER project ZIPs (data-descriptor format)
- CORDIS coordinator join logic
- metadata dict constructors (NIH and CORDIS)
- source_url constructors
- source_programme derivation from filename
"""

from __future__ import annotations

import sqlite3
import struct
import sys
import zlib
from pathlib import Path
from typing import Iterator


# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_GRANTS_DDL = """
CREATE TABLE IF NOT EXISTS grants (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Core shared fields
    title             TEXT    NOT NULL,
    abstract          TEXT,
    start_date        TEXT,
    end_date          TEXT,
    funding_amount    REAL,
    funding_currency  TEXT,
    organization      TEXT,
    country           TEXT,

    -- Provenance (first-class, non-null)
    source            TEXT    NOT NULL CHECK(source IN ('nih', 'cordis')),
    source_id         TEXT    NOT NULL,
    source_programme  TEXT,
    source_url        TEXT,

    -- Source-specific metadata (JSON)
    metadata          TEXT,

    UNIQUE(source, source_id)
);
"""

_FTS_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS grants_fts USING fts5(
    title,
    abstract,
    content=grants,
    content_rowid=id,
    tokenize='unicode61'
);
"""


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the grants table and grants_fts FTS5 virtual table.

    Safe to call multiple times on the same connection (uses IF NOT EXISTS).
    """
    conn.execute(_GRANTS_DDL)
    conn.execute(_FTS_DDL)
    conn.commit()


# ---------------------------------------------------------------------------
# NIH date normalization (§6.1)
# ---------------------------------------------------------------------------


def normalize_nih_date(value: str | None) -> str | None:
    """Normalize a NIH date string to ISO 8601 YYYY-MM-DD.

    Accepts:
    - ``MM/DD/YYYY`` → ``YYYY-MM-DD``
    - ``YYYY-MM-DD`` → passthrough
    - blank / None / unparseable → ``None``
    """
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None

    # Try MM/DD/YYYY
    if "/" in value:
        parts = value.split("/")
        if len(parts) == 3:
            mm, dd, yyyy = parts
            try:
                m, d, y = int(mm), int(dd), int(yyyy)
                # Basic range check
                if 1 <= m <= 12 and 1 <= d <= 31 and 1900 <= y <= 2100:
                    return f"{y:04d}-{m:02d}-{d:02d}"
            except ValueError:
                pass
        return None

    # Try YYYY-MM-DD
    if "-" in value:
        parts = value.split("-")
        if len(parts) == 3:
            try:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                if 1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31:
                    return f"{y:04d}-{m:02d}-{d:02d}"
            except ValueError:
                pass
        return None

    return None


# ---------------------------------------------------------------------------
# CORDIS decimal normalization (§6.2)
# ---------------------------------------------------------------------------


def normalize_cordis_decimal(value: str | None) -> float | None:
    """Normalize a CORDIS amount string to a Python float.

    CORDIS uses comma as the decimal separator (e.g. ``"2073781,25"``).
    Strips surrounding double-quotes (from CSV quoting) and replaces commas
    with periods before casting. Blank or unparseable values → ``None``.
    """
    if value is None:
        return None
    value = value.strip().strip('"')
    if not value:
        return None
    # Replace comma decimal separator with period
    value = value.replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# NIH streaming ZIP reader (§4.1)
# ---------------------------------------------------------------------------


def iter_csv_lines(zip_path: Path) -> Iterator[bytes]:
    """Yield lines from a NIH ExPORTER streaming-ZIP file.

    NIH ExPORTER project ZIPs use ZIP general-purpose bit flag 0x0008 (data
    descriptor), which causes Python's ``zipfile.ZipFile`` to raise
    ``BadZipFile``.  This function bypasses the ZIP index entirely and reads
    the raw DEFLATE stream from the first local file entry.
    """
    with open(zip_path, "rb") as f:
        # Skip local file header signature (4 bytes)
        f.read(4)
        # Skip fixed fields: version(2) + flags(2) + method(2) + mod_time(2)
        #   + mod_date(2) + crc32(4) + compressed_size(4) + uncompressed_size(4)
        f.read(2 + 2 + 2 + 2 + 2 + 4 + 4 + 4)
        fname_len = struct.unpack("<H", f.read(2))[0]
        extra_len = struct.unpack("<H", f.read(2))[0]
        f.read(fname_len + extra_len)

        # Stream-decompress the raw DEFLATE payload
        d = zlib.decompressobj(-15)
        buf = b""
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            buf += d.decompress(chunk)
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                yield line
        if buf:
            yield buf


# ---------------------------------------------------------------------------
# NIH country lookup (§6.4)
# ---------------------------------------------------------------------------

#: Mapping from NIH uppercase country name to ISO 3166-1 alpha-2 code.
#: Used by :func:`normalize_country`.
NIH_COUNTRY_LOOKUP: dict[str, str] = {
    # North America
    "UNITED STATES": "US",
    "CANADA": "CA",
    "MEXICO": "MX",
    # Europe
    "UNITED KINGDOM": "GB",
    "GERMANY": "DE",
    "FRANCE": "FR",
    "NETHERLANDS": "NL",
    "SWEDEN": "SE",
    "SWITZERLAND": "CH",
    "ITALY": "IT",
    "SPAIN": "ES",
    "BELGIUM": "BE",
    "DENMARK": "DK",
    "NORWAY": "NO",
    "FINLAND": "FI",
    "AUSTRIA": "AT",
    "PORTUGAL": "PT",
    "POLAND": "PL",
    "CZECH REPUBLIC": "CZ",
    "HUNGARY": "HU",
    "GREECE": "GR",
    "IRELAND": "IE",
    "TURKEY": "TR",
    "RUSSIA": "RU",
    "UKRAINE": "UA",
    "ROMANIA": "RO",
    "SLOVAKIA": "SK",
    "BULGARIA": "BG",
    "CROATIA": "HR",
    "SLOVENIA": "SI",
    "SERBIA": "RS",
    "LUXEMBOURG": "LU",
    "ICELAND": "IS",
    "ESTONIA": "EE",
    "LATVIA": "LV",
    "LITHUANIA": "LT",
    "MALTA": "MT",
    "CYPRUS": "CY",
    # Asia-Pacific
    "JAPAN": "JP",
    "CHINA": "CN",
    "AUSTRALIA": "AU",
    "SOUTH KOREA": "KR",
    "INDIA": "IN",
    "NEW ZEALAND": "NZ",
    "SINGAPORE": "SG",
    "HONG KONG": "HK",
    "TAIWAN": "TW",
    "THAILAND": "TH",
    "MALAYSIA": "MY",
    "INDONESIA": "ID",
    "PHILIPPINES": "PH",
    "VIETNAM": "VN",
    "PAKISTAN": "PK",
    "BANGLADESH": "BD",
    "SRI LANKA": "LK",
    "NEPAL": "NP",
    # Middle East
    "ISRAEL": "IL",
    "SAUDI ARABIA": "SA",
    "UNITED ARAB EMIRATES": "AE",
    "IRAN": "IR",
    "JORDAN": "JO",
    "EGYPT": "EG",
    "LEBANON": "LB",
    "KUWAIT": "KW",
    "QATAR": "QA",
    "BAHRAIN": "BH",
    # Africa
    "SOUTH AFRICA": "ZA",
    "NIGERIA": "NG",
    "KENYA": "KE",
    "ETHIOPIA": "ET",
    "GHANA": "GH",
    "TANZANIA": "TZ",
    "UGANDA": "UG",
    "ZIMBABWE": "ZW",
    "ZAMBIA": "ZM",
    "MOZAMBIQUE": "MZ",
    "CAMEROON": "CM",
    "SENEGAL": "SN",
    "RWANDA": "RW",
    "MALAWI": "MW",
    "BOTSWANA": "BW",
    # Latin America / Caribbean
    "BRAZIL": "BR",
    "ARGENTINA": "AR",
    "CHILE": "CL",
    "COLOMBIA": "CO",
    "PERU": "PE",
    "VENEZUELA": "VE",
    "CUBA": "CU",
    "HAITI": "HT",
    "JAMAICA": "JM",
    "PANAMA": "PA",
    "COSTA RICA": "CR",
    "GUATEMALA": "GT",
    "HONDURAS": "HN",
    "EL SALVADOR": "SV",
    "ECUADOR": "EC",
    "BOLIVIA": "BO",
    "PARAGUAY": "PY",
    "URUGUAY": "UY",
    "TRINIDAD AND TOBAGO": "TT",
    # Other
    "PUERTO RICO": "PR",
}


def normalize_country(name: str | None) -> str | None:
    """Normalize a NIH country name to ISO 3166-1 alpha-2 code.

    Returns ``None`` and emits a stderr warning for unrecognized names.
    """
    if name is None:
        return None
    key = name.strip().upper()
    if not key:
        return None
    result = NIH_COUNTRY_LOOKUP.get(key)
    if result is None:
        print(
            f"WARNING: unrecognized country name: {name!r}",
            file=sys.stderr,
        )
    return result


# ---------------------------------------------------------------------------
# CORDIS coordinator join (§5)
# ---------------------------------------------------------------------------


def get_coordinator(
    orgs: list[dict],
    project_id: str | int,
) -> tuple[str | None, str | None]:
    """Return (name, country) for the coordinator org in *orgs*.

    If no coordinator row is found, emits a stderr warning that includes
    *project_id* and returns ``(None, None)``.
    """
    for org in orgs:
        role = (org.get("role") or "").strip().lower()
        if role == "coordinator":
            return org.get("name"), org.get("country")
    print(
        f"WARNING: no coordinator found for project {project_id}",
        file=sys.stderr,
    )
    return None, None


# ---------------------------------------------------------------------------
# source_programme derivation (§5.1)
# ---------------------------------------------------------------------------

_PROGRAMME_MAP: dict[str, str] = {
    "cordis-fp7projects-csv.zip": "fp7",
    "cordis-h2020projects-csv.zip": "h2020",
    "cordis-HORIZONprojects-csv.zip": "horizon_europe",
}


def source_programme_from_filename(filename: str | Path) -> str | None:
    """Derive the CORDIS source_programme slug from a ZIP filename.

    Accepts full paths or bare filenames; matches on the basename only.
    Returns ``'fp7'``, ``'h2020'``, or ``'horizon_europe'``.
    Returns ``None`` for unrecognized filenames.
    """
    basename = Path(filename).name
    return _PROGRAMME_MAP.get(basename)


# ---------------------------------------------------------------------------
# metadata dict constructors (§7)
# ---------------------------------------------------------------------------


def make_nih_metadata(row: dict) -> dict:
    """Build the NIH metadata dict from a project CSV row.

    Keys: ``activity_code``, ``ic_name``, ``core_project_num``,
    ``pi_names``, ``fy``.  Missing source fields produce ``None``
    for the corresponding key (never KeyError).
    """
    fy_raw = row.get("FY")
    fy: int | None
    try:
        fy = int(fy_raw) if fy_raw is not None else None
    except (ValueError, TypeError):
        fy = None

    return {
        "activity_code": row.get("ACTIVITY"),
        "ic_name": row.get("IC_NAME"),
        "core_project_num": row.get("CORE_PROJECT_NUM"),
        "pi_names": row.get("PI_NAMEs"),
        "fy": fy,
    }


def make_cordis_metadata(row: dict) -> dict:
    """Build the CORDIS metadata dict from a project CSV row.

    Keys: ``acronym``, ``topics``, ``status``, ``ec_signature_date``,
    ``keywords``.  Missing source fields produce ``None`` (never KeyError).
    """
    return {
        "acronym": row.get("acronym"),
        "topics": row.get("topics"),
        "status": row.get("status"),
        "ec_signature_date": row.get("ecSignatureDate"),
        "keywords": row.get("keywords"),
    }


# ---------------------------------------------------------------------------
# source_url constructors (§4, §5)
# ---------------------------------------------------------------------------


def nih_source_url(application_id: str | int) -> str:
    """Return the NIH RePORTER deep-link URL for *application_id*."""
    return f"https://reporter.nih.gov/project-details/{application_id}"


def cordis_source_url(project_id: str | int) -> str:
    """Return the CORDIS deep-link URL for *project_id*."""
    return f"https://cordis.europa.eu/project/id/{project_id}"
