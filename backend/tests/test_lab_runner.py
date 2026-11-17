"""Unit tests for app/services/lab_runner.py. No database needed: they run the
REAL subprocess runner against tiny throwaway test files and a local fake lab
(a /healthz endpoint on a random loopback port)."""
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.challenges.registry import all_metadata
from app.services import lab_runner
from app.services.lab_runner import RunnerMisconfigured, run_lab_tests, validate_base_url


class _Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.path == "/healthz" else 404)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, *args):  # keep test output quiet
        pass


@pytest.fixture
def fake_lab():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Health)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def allowlist(monkeypatch, tmp_path):
    """Points challenge 'c' at a throwaway test file (absolute path, so the
    runner's join with the repo root leaves it unchanged)."""

    def _make(source: str) -> str:
        path = tmp_path / "test_case.py"
        path.write_text(source)
        monkeypatch.setitem(lab_runner.LAB_TEST_ALLOWLIST, "c", (str(path),))
        return str(path)

    return _make


async def _run(base, timeout=30):
    return await run_lab_tests("c", base_url=base, timeout_seconds=timeout)


@pytest.mark.asyncio
async def test_all_passing_is_passed(fake_lab, allowlist):
    allowlist("def test_ok():\n    assert True\n")
    r = await _run(fake_lab)
    assert r.outcome == "passed" and r.detail["tests"] == 1
    assert r.duration_ms >= 0 and r.tests


@pytest.mark.asyncio
async def test_a_failing_test_is_failed_not_passed(fake_lab, allowlist):
    allowlist("def test_bad():\n    assert False\n")
    r = await _run(fake_lab)
    assert r.outcome == "failed" and r.detail["failures"] == 1


@pytest.mark.asyncio
async def test_failure_output_never_leaks_into_the_result(fake_lab, allowlist):
    """A failing lab test can print a response body that contains the
    challenge flag. The result must keep only counts and test names."""
    allowlist(
        "def test_leaky():\n"
        "    body = {'description': 'AEGIS{do-not-leak-this-flag}'}\n"
        "    assert body['description'] == 'something else', body\n"
    )
    r = await _run(fake_lab)
    assert r.outcome == "failed"
    assert "AEGIS{" not in r.summary and "AEGIS{" not in repr(r.detail)
    assert "test_leaky" in r.summary  # the failing test is named, nothing more


@pytest.mark.asyncio
async def test_collection_error_is_error(fake_lab, allowlist):
    allowlist("def broken(:\n")
    r = await _run(fake_lab)
    assert r.outcome == "error"


@pytest.mark.asyncio
async def test_no_tests_collected_is_error_not_passed(fake_lab, allowlist):
    allowlist("x = 1\n")
    r = await _run(fake_lab)
    assert r.outcome == "error"


@pytest.mark.asyncio
async def test_timeout_is_error_and_kills_the_run(fake_lab, allowlist):
    allowlist("import time\n\ndef test_hang():\n    time.sleep(60)\n")
    r = await _run(fake_lab, timeout=2)
    assert r.outcome == "error" and "Timed out" in r.summary
    assert r.duration_ms < 20_000  # returned promptly, did not wait out the sleep


@pytest.mark.asyncio
async def test_lab_down_before_the_run_is_unreachable(allowlist):
    allowlist("def test_ok():\n    assert True\n")
    r = await _run("http://127.0.0.1:1")  # nothing listens on port 1
    assert r.outcome == "unreachable"


@pytest.mark.asyncio
async def test_connection_errors_inside_the_run_are_unreachable_not_failed(fake_lab, allowlist):
    allowlist(
        "import httpx\n\n"
        "def test_lab_call():\n"
        "    httpx.get('http://127.0.0.1:1/x', timeout=2)\n"
    )
    r = await _run(fake_lab)
    assert r.outcome == "unreachable"


@pytest.mark.asyncio
async def test_child_environment_is_scrubbed(fake_lab, allowlist, monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "must-not-leak")
    monkeypatch.setenv("DATABASE_URL", "postgresql://must-not-leak")
    allowlist(
        "import os\n\n"
        "def test_env():\n"
        "    assert 'SUPABASE_JWT_SECRET' not in os.environ\n"
        "    assert 'DATABASE_URL' not in os.environ\n"
        f"    assert os.environ['LAB_BASE_URL'] == {fake_lab!r}\n"
    )
    r = await _run(fake_lab)
    assert r.outcome == "passed", r.summary


def test_only_loopback_or_lab_api_hosts_are_allowed():
    assert validate_base_url("http://127.0.0.1:8100/") == "http://127.0.0.1:8100"
    assert validate_base_url("http://lab-api:8100") == "http://lab-api:8100"
    for bad in ("http://example.com:8100", "http://192.168.1.5:8100", "file:///etc/passwd", "ftp://127.0.0.1"):
        with pytest.raises(RunnerMisconfigured):
            validate_base_url(bad)


def test_allowlist_covers_exactly_the_catalog_and_files_exist():
    catalog = {m.id for m in all_metadata()}
    assert set(lab_runner.LAB_TEST_ALLOWLIST) == catalog
    for files in lab_runner.LAB_TEST_ALLOWLIST.values():
        for rel in files:
            assert os.path.isfile(os.path.join(lab_runner.REPO_ROOT, rel)), rel
            assert rel.startswith("lab/tests/test_")  # nothing outside the lab test dir
