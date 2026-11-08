"""Tests for db/acquire_data.py — all HTTP calls mocked, no live network."""
import json
import sys
import urllib.error
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

# Make sure the project root is on the path.
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.acquire_data import (
    ZIP_MAGIC,
    INTER_HOST_DELAY,
    API_RATE_DELAY,
    RateLimiter,
    check_integrity,
    detect_gap_years,
    download_file,
    estimate_requests,
    get_anchor_date,
    run,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockResponse:
    """Minimal stand-in for urllib response (supports context-manager protocol)."""

    def __init__(self, body: bytes, headers: dict):
        self._body = body
        self.headers = headers  # plain dict; .get() works fine

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


def make_fast_monotonic():
    """Return a time.monotonic mock whose successive values are 100 s apart
    so the RateLimiter never sleeps during integration tests."""
    t = [1000.0]

    def _mono():
        v = t[0]
        t[0] += 100.0
        return v

    return _mono


VALID_ZIP = ZIP_MAGIC + b"\x00" * 100


# ---------------------------------------------------------------------------
# Integrity check
# ---------------------------------------------------------------------------

def test_integrity_missing_file(tmp_path):
    assert not check_integrity(tmp_path / "nonexistent.zip")


def test_integrity_zero_byte(tmp_path):
    p = tmp_path / "empty.zip"
    p.write_bytes(b"")
    assert not check_integrity(p)


def test_integrity_non_zip(tmp_path):
    p = tmp_path / "bad.zip"
    p.write_bytes(b"notazip____")
    assert not check_integrity(p)


def test_integrity_valid_zip(tmp_path):
    p = tmp_path / "good.zip"
    p.write_bytes(VALID_ZIP)
    assert check_integrity(p)


# ---------------------------------------------------------------------------
# Temporal anchor extraction
# ---------------------------------------------------------------------------

def test_anchor_extracted_from_last_modified():
    resp = MockResponse(b"", {"Last-Modified": "Sun, 14 Sep 2026 12:00:00 GMT"})
    rl = RateLimiter()
    with patch("db.acquire_data.urllib.request.urlopen", return_value=resp):
        anchor = get_anchor_date(rl)
    assert anchor == date(2026, 9, 14)


def test_anchor_missing_header_raises():
    resp = MockResponse(b"", {})
    rl = RateLimiter()
    with patch("db.acquire_data.urllib.request.urlopen", return_value=resp):
        with pytest.raises(RuntimeError, match="no Last-Modified header"):
            get_anchor_date(rl)


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------

def test_gap_detection_no_gap_anchor_before_next_start():
    # FY2026 starts Oct 1 2025; anchor Sep 1 2025 → not started yet.
    assert detect_gap_years(2025, date(2025, 9, 1)) == []


def test_gap_detection_anchor_on_exact_fy_end():
    # Anchor = Sep 30 2025 (= end of FY2025); FY2026 starts Oct 1 2025 > Sep 30 → no gap.
    assert detect_gap_years(2025, date(2025, 9, 30)) == []


def test_gap_detection_one_gap_year():
    # Anchor Sep 14 2026; FY2026 starts Oct 1 2025 ≤ anchor → included.
    # FY2027 starts Oct 1 2026 > anchor → excluded.
    assert detect_gap_years(2025, date(2026, 9, 14)) == [2026]


def test_gap_detection_multiple_gap_years():
    # last ExPORTER = FY2024; anchor Sep 14 2026
    # FY2025 starts Oct 1 2024 ≤ anchor ✓; FY2026 starts Oct 1 2025 ≤ anchor ✓
    assert detect_gap_years(2024, date(2026, 9, 14)) == [2025, 2026]


# ---------------------------------------------------------------------------
# Preflight estimate (ceil(total / 500))
# ---------------------------------------------------------------------------

def test_estimate_requests_exact_multiple():
    assert estimate_requests(1000) == 2


def test_estimate_requests_ceiling():
    assert estimate_requests(501) == 2


def test_estimate_requests_one():
    assert estimate_requests(1) == 1


def test_estimate_requests_zero():
    assert estimate_requests(0) == 0


def test_estimate_requests_exactly_30():
    # 15 000 records → 30 requests (at the threshold, no warning)
    assert estimate_requests(15_000) == 30


def test_estimate_requests_above_threshold():
    # 15 001 records → 31 requests (above threshold, should warn)
    assert estimate_requests(15_001) == 31


# ---------------------------------------------------------------------------
# Off-hours warning threshold
# ---------------------------------------------------------------------------

def _make_api_response(total: int) -> bytes:
    return json.dumps({"meta": {"total": total}, "results": []}).encode()


def test_no_warning_for_small_job(tmp_path):
    """≤ 30 estimated requests → input() is never called."""
    # 2 gap years × 7 500 records each = 15 000 → estimate = 30 → no prompt.
    api_resp = MockResponse(_make_api_response(7_500), {})

    with patch("db.acquire_data.urllib.request.urlopen", return_value=api_resp), \
         patch("db.acquire_data.time.sleep"), \
         patch("db.acquire_data.time.monotonic", side_effect=make_fast_monotonic()), \
         patch("builtins.input") as mock_input:
        from db.acquire_data import api_preflight
        rl = RateLimiter()
        counts = api_preflight([2025, 2026], rl)
        total = sum(counts.values())
        assert estimate_requests(total) <= 30
        mock_input.assert_not_called()


def test_warning_for_large_job_calls_input(tmp_path, monkeypatch):
    """estimate_requests > 30 → input() must be called."""
    # Simulate gap_fill calling input via full gap_fill execution.
    # 2 gap years × 10 000 records each = 20 000 → ceil(20000/500) = 40 > 30.
    input_called = []
    monkeypatch.setattr("builtins.input", lambda: input_called.append(True) or "")

    # preflight responses (limit=1 calls) then page responses (limit=500 calls)
    preflight_resp = MockResponse(_make_api_response(10_000), {})
    page_resp = MockResponse(
        json.dumps({"meta": {"total": 10_000}, "results": [{"x": i} for i in range(500)]}).encode(),
        {},
    )

    call_count = [0]

    def side_effect(req):
        call_count[0] += 1
        # First two calls are preflight (limit=1); rest are page fetches.
        if call_count[0] <= 2:
            return preflight_resp
        return page_resp

    from db.acquire_data import gap_fill

    with patch("db.acquire_data.urllib.request.urlopen", side_effect=side_effect), \
         patch("db.acquire_data.time.sleep"), \
         patch("db.acquire_data.time.monotonic", side_effect=make_fast_monotonic()):
        gap_fill([2025, 2026], tmp_path, RateLimiter())

    assert input_called, "input() should have been called for large job"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_skip_existing_valid_file(tmp_path):
    """Existing valid ZIP should not trigger a network request."""
    dest = tmp_path / "test.zip"
    dest.write_bytes(VALID_ZIP)

    with patch("db.acquire_data.urllib.request.urlopen") as mock_open:
        download_file("https://example.com/test.zip", dest, RateLimiter(), force=False)

    mock_open.assert_not_called()


def test_redownload_zero_byte_file(tmp_path):
    """Zero-byte file is re-downloaded even without --force."""
    dest = tmp_path / "test.zip"
    dest.write_bytes(b"")

    resp = MockResponse(VALID_ZIP, {})
    with patch("db.acquire_data.urllib.request.urlopen", return_value=resp), \
         patch("db.acquire_data.time.sleep"), \
         patch("db.acquire_data.time.monotonic", side_effect=make_fast_monotonic()):
        download_file("https://example.com/test.zip", dest, RateLimiter(), force=False)

    assert dest.read_bytes()[:4] == ZIP_MAGIC


def test_redownload_non_zip_file(tmp_path):
    """Non-ZIP file is re-downloaded even without --force."""
    dest = tmp_path / "test.zip"
    dest.write_bytes(b"garbage")

    resp = MockResponse(VALID_ZIP, {})
    with patch("db.acquire_data.urllib.request.urlopen", return_value=resp), \
         patch("db.acquire_data.time.sleep"), \
         patch("db.acquire_data.time.monotonic", side_effect=make_fast_monotonic()):
        download_file("https://example.com/test.zip", dest, RateLimiter(), force=False)

    assert dest.read_bytes()[:4] == ZIP_MAGIC


def test_force_redownload_overwrites_valid_file(tmp_path):
    """--force-redownload overwrites a valid file."""
    dest = tmp_path / "test.zip"
    dest.write_bytes(VALID_ZIP)

    new_content = ZIP_MAGIC + b"\xff" * 100
    resp = MockResponse(new_content, {})
    with patch("db.acquire_data.urllib.request.urlopen", return_value=resp), \
         patch("db.acquire_data.time.sleep"), \
         patch("db.acquire_data.time.monotonic", side_effect=make_fast_monotonic()):
        download_file("https://example.com/test.zip", dest, RateLimiter(), force=True)

    assert dest.read_bytes() == new_content


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def test_rate_limiter_enforces_delay_same_host():
    """Two requests 0.5 s apart should trigger sleep(1.5)."""
    rl = RateLimiter()
    sleep_calls = []

    # Calls to time.monotonic in order:
    # wait #1: now=100.0, then record last=100.0
    # wait #2: now=100.5, record last=102.0
    mono_seq = iter([100.0, 100.0, 100.5, 102.0])

    with patch("db.acquire_data.time.monotonic", side_effect=lambda: next(mono_seq)), \
         patch("db.acquire_data.time.sleep", side_effect=sleep_calls.append):
        rl.wait("example.com", 2.0)   # gap = 100.0 (no sleep)
        rl.wait("example.com", 2.0)   # gap = 0.5 → sleep(1.5)

    assert len(sleep_calls) == 1
    assert abs(sleep_calls[0] - 1.5) < 0.001


def test_rate_limiter_no_sleep_when_enough_time_elapsed():
    """If enough time has elapsed between requests, no sleep."""
    rl = RateLimiter()
    sleep_calls = []

    mono_seq = iter([100.0, 100.0, 103.0, 103.0])

    with patch("db.acquire_data.time.monotonic", side_effect=lambda: next(mono_seq)), \
         patch("db.acquire_data.time.sleep", side_effect=sleep_calls.append):
        rl.wait("example.com", 2.0)
        rl.wait("example.com", 2.0)   # gap = 3.0 >= 2.0 → no sleep

    assert len(sleep_calls) == 0


def test_rate_limiter_different_hosts_no_interference():
    """Requests to different hosts don't share rate-limit state."""
    rl = RateLimiter()
    sleep_calls = []

    # Both get "now = 100.0", no prior history for either host.
    mono_seq = iter([100.0, 100.0, 100.0, 100.0])

    with patch("db.acquire_data.time.monotonic", side_effect=lambda: next(mono_seq)), \
         patch("db.acquire_data.time.sleep", side_effect=sleep_calls.append):
        rl.wait("host1.com", 2.0)
        rl.wait("host2.com", 2.0)   # different host → no sleep

    assert len(sleep_calls) == 0


def test_rate_limiter_api_delay_one_second():
    """API calls enforce 1 s delay."""
    rl = RateLimiter()
    sleep_calls = []

    mono_seq = iter([50.0, 50.0, 50.3, 51.0])

    with patch("db.acquire_data.time.monotonic", side_effect=lambda: next(mono_seq)), \
         patch("db.acquire_data.time.sleep", side_effect=sleep_calls.append):
        rl.wait("api.reporter.nih.gov", API_RATE_DELAY)   # no sleep
        rl.wait("api.reporter.nih.gov", API_RATE_DELAY)   # gap=0.3 → sleep(0.7)

    assert len(sleep_calls) == 1
    assert abs(sleep_calls[0] - 0.7) < 0.001


# ---------------------------------------------------------------------------
# Manifest structure
# ---------------------------------------------------------------------------

def _build_run_mocks(anchor_header: str = "Tue, 30 Sep 2025 12:00:00 GMT"):
    """Return a side_effect function for urlopen covering a full success run."""

    def _side(req):
        if req.get_method() == "HEAD":
            return MockResponse(b"", {"Last-Modified": anchor_header})
        return MockResponse(VALID_ZIP, {})

    return _side


def test_manifest_written_on_success(tmp_path):
    with patch("db.acquire_data.urllib.request.urlopen", side_effect=_build_run_mocks()), \
         patch("db.acquire_data.time.sleep"), \
         patch("db.acquire_data.time.monotonic", side_effect=make_fast_monotonic()):
        code = run(2024, tmp_path, force=False)

    assert code == 0
    manifest_path = tmp_path / "manifest.json"
    assert manifest_path.exists()

    m = json.loads(manifest_path.read_text())
    assert m["schema_version"] == 1
    assert m["start_year"] == 2024
    assert m["cordis_anchor_date"] == "2025-09-30"
    assert m["cordis"]["anchor_source"] == "Last-Modified header"
    assert len(m["cordis"]["programmes"]) == 3
    assert all(p["status"] == "ok" for p in m["cordis"]["programmes"])
    assert m["nih_exporter"]["fiscal_years"] == [2024, 2025]
    assert all(f["status"] == "ok" for f in m["nih_exporter"]["files"])
    # No gap fill (anchor == FY2025 end date → no gap years)
    assert m["nih_gap_fill"]["fiscal_years"] == []
    assert m["errors"] == []


def test_manifest_file_paths_are_relative(tmp_path):
    """All file paths in manifest should be relative to data_dir, not absolute."""
    with patch("db.acquire_data.urllib.request.urlopen", side_effect=_build_run_mocks()), \
         patch("db.acquire_data.time.sleep"), \
         patch("db.acquire_data.time.monotonic", side_effect=make_fast_monotonic()):
        run(2024, tmp_path, force=False)

    m = json.loads((tmp_path / "manifest.json").read_text())
    for prog in m["cordis"]["programmes"]:
        assert not prog["file"].startswith("/"), f"absolute path: {prog['file']}"
    for f in m["nih_exporter"]["files"]:
        assert not f["project_file"].startswith("/")
        assert not f["abstract_file"].startswith("/")


def test_manifest_nih_exporter_filenames(tmp_path):
    """NIH ExPORTER manifest entries use the correct filename pattern."""
    with patch("db.acquire_data.urllib.request.urlopen", side_effect=_build_run_mocks()), \
         patch("db.acquire_data.time.sleep"), \
         patch("db.acquire_data.time.monotonic", side_effect=make_fast_monotonic()):
        run(2024, tmp_path, force=False)

    m = json.loads((tmp_path / "manifest.json").read_text())
    files = m["nih_exporter"]["files"]
    assert any("RePORTER_PRJ_C_FY2024.zip" in f["project_file"] for f in files)
    assert any("RePORTER_PRJABS_C_FY2024.zip" in f["abstract_file"] for f in files)


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

def test_exit_code_zero_all_success(tmp_path):
    with patch("db.acquire_data.urllib.request.urlopen", side_effect=_build_run_mocks()), \
         patch("db.acquire_data.time.sleep"), \
         patch("db.acquire_data.time.monotonic", side_effect=make_fast_monotonic()):
        assert run(2024, tmp_path, False) == 0


def test_exit_code_one_on_download_failure(tmp_path):
    """Any download failure → exit code 1 and manifest errors non-empty."""

    def _side(req):
        if req.get_method() == "HEAD":
            return MockResponse(b"", {"Last-Modified": "Tue, 30 Sep 2025 12:00:00 GMT"})
        raise urllib.error.URLError("connection refused")

    with patch("db.acquire_data.urllib.request.urlopen", side_effect=_side), \
         patch("db.acquire_data.time.sleep"), \
         patch("db.acquire_data.time.monotonic", side_effect=make_fast_monotonic()):
        code = run(2024, tmp_path, False)

    assert code == 1
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert len(m["errors"]) > 0


def test_manifest_written_even_on_failure(tmp_path):
    """manifest.json is always written, even when downloads fail."""

    def _side(req):
        if req.get_method() == "HEAD":
            return MockResponse(b"", {"Last-Modified": "Tue, 30 Sep 2025 12:00:00 GMT"})
        raise urllib.error.HTTPError("url", 503, "Service Unavailable", {}, None)

    with patch("db.acquire_data.urllib.request.urlopen", side_effect=_side), \
         patch("db.acquire_data.time.sleep"), \
         patch("db.acquire_data.time.monotonic", side_effect=make_fast_monotonic()):
        run(2024, tmp_path, False)

    assert (tmp_path / "manifest.json").exists()


# ---------------------------------------------------------------------------
# Gap fill with manifest validation
# ---------------------------------------------------------------------------

def test_gap_fill_pages_written_and_manifest_correct(tmp_path):
    """Gap fill writes page JSON files and records them in the manifest."""
    # Anchor = Sep 14 2026 → last ExPORTER = FY2025, gap = [FY2026]
    anchor_header = "Mon, 14 Sep 2026 12:00:00 GMT"

    # preflight (limit=1): total=600 → ceil(600/500) = 2 requests → ≤ 30, no prompt
    preflight_body = json.dumps({"meta": {"total": 600}, "results": []}).encode()

    # page 1: 500 records; page 2: 100 records
    page1_body = json.dumps({
        "meta": {"total": 600},
        "results": [{"id": i} for i in range(500)],
    }).encode()
    page2_body = json.dumps({
        "meta": {"total": 600},
        "results": [{"id": i} for i in range(100)],
    }).encode()

    call_seq = [
        # HEAD for anchor
        MockResponse(b"", {"Last-Modified": anchor_header}),
        # 3 CORDIS GETs
        MockResponse(VALID_ZIP, {}),
        MockResponse(VALID_ZIP, {}),
        MockResponse(VALID_ZIP, {}),
        # NIH ExPORTER: FY2024 prj+abs, FY2025 prj+abs
        MockResponse(VALID_ZIP, {}),
        MockResponse(VALID_ZIP, {}),
        MockResponse(VALID_ZIP, {}),
        MockResponse(VALID_ZIP, {}),
        # Preflight for FY2026
        MockResponse(preflight_body, {}),
        # Page fetches for FY2026
        MockResponse(page1_body, {}),
        MockResponse(page2_body, {}),
    ]
    idx = [0]

    def _side(_req):
        resp = call_seq[idx[0]]
        idx[0] += 1
        return resp

    with patch("db.acquire_data.urllib.request.urlopen", side_effect=_side), \
         patch("db.acquire_data.time.sleep"), \
         patch("db.acquire_data.time.monotonic", side_effect=make_fast_monotonic()), \
         patch("builtins.input", return_value=""):
        code = run(2024, tmp_path, force=False)

    assert code == 0
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert m["nih_gap_fill"]["fiscal_years"] == [2026]
    assert m["nih_gap_fill"]["total_records_retrieved"] == 600
    assert m["nih_gap_fill"]["total_records_available"] == 600
    assert not m["nih_gap_fill"]["shortfall"]
    assert len(m["nih_gap_fill"]["files"]) == 1
    gf = m["nih_gap_fill"]["files"][0]
    assert gf["fiscal_year"] == 2026
    assert gf["status"] == "ok"
    assert len(gf["pages"]) == 2

    # Verify actual page files exist on disk
    for rel_path in gf["pages"]:
        assert (tmp_path / rel_path).exists()
