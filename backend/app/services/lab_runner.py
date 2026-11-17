"""Server-side lab regression runner for vulnerability-report verification.

WHAT THIS IS, AND IS NOT. The lab's tests (`lab/tests/`) check that the lab's
own *vulnerable* endpoint still leaks and its own *hardened* twin still
blocks. They say nothing about a team's own fix: users never submit code and
nothing a user does changes the lab. So a `passed` outcome is evidence about
the lab's reference implementation, and callers must present it as that —
never as proof that a team remediated anything.

HOW IT IS CONSTRAINED. This module runs a test runner inside a server, so:
  * Fixed allowlist: each challenge maps to ONE specific test file below. No
    request value reaches the command line, the path, or the environment.
  * One fixed invocation shape: `python -m pytest ... <allowlisted file>` as
    an argument list (never a shell, never string-built).
  * Scrubbed environment: the child gets PATH/system basics plus LAB_BASE_URL
    only — none of the backend's database URLs, keys or secrets.
  * Fixed target: the lab URL comes from server config and its host must be
    loopback or the compose service name `lab-api`.
  * Timeout (process killed); raw test output is discarded (it can contain
    response bodies, i.e. challenge flags) and only a structured summary of
    counts and failing test names is kept; on POSIX CPU/memory/file-count
    rlimits. Windows has no equivalent of those rlimits here, so there the
    protections are the timeout, discarded output and scrubbed env.
  * Outcomes are four distinct states and are never collapsed:
    passed / failed / error / unreachable.
"""
import asyncio
import os
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# challenge id -> test file (relative to the repo root). Server config only.
LAB_TEST_ALLOWLIST: dict[str, tuple[str, ...]] = {
    "api1-bola-project-files": ("lab/tests/test_bola.py",),
    "api2-broken-auth-predictable-session": ("lab/tests/test_broken_auth.py",),
    "api3-bopla-role-escalation": ("lab/tests/test_bopla.py",),
    "api4-resource-consumption-pagination": ("lab/tests/test_resource_consumption.py",),
    "api5-bfla-admin-broadcast": ("lab/tests/test_bfla.py",),
    "api6-sensitive-flows-coupon-replay": ("lab/tests/test_business_flows.py",),
    "api7-ssrf-url-preview": ("lab/tests/test_ssrf.py",),
    "api8-misconfiguration-verbose-errors": ("lab/tests/test_misconfiguration.py",),
    "api9-inventory-shadow-v1-endpoint": ("lab/tests/test_inventory.py",),
    "api10-unsafe-consumption-pricing": ("lab/tests/test_unsafe_consumption.py",),
}

ALLOWED_LAB_HOSTS = {"127.0.0.1", "localhost", "::1", "lab-api"}
OUTCOMES = ("passed", "failed", "error", "unreachable")
PREFLIGHT_TIMEOUT_SECONDS = 3.0

# Connection-level failures inside a test run mean the lab went away, which
# is "unreachable", not a genuine test failure.
_CONNECTION_MARKERS = ("ConnectError", "ConnectTimeout", "ConnectionRefused", "Connection refused")


class RunnerMisconfigured(Exception):
    """The configured lab URL is not an allowed local lab address."""


@dataclass
class RunResult:
    outcome: str
    tests: list[str]
    duration_ms: int
    summary: str = ""
    detail: dict = field(default_factory=dict)

    def __post_init__(self):
        assert self.outcome in OUTCOMES, f"unknown outcome {self.outcome!r}"


def validate_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ALLOWED_LAB_HOSTS:
        raise RunnerMisconfigured(
            "lab_retest_base_url must be http(s) to 127.0.0.1, localhost, ::1 or lab-api"
        )
    return base_url.rstrip("/")


def tests_for(challenge_id: str) -> tuple[str, ...] | None:
    return LAB_TEST_ALLOWLIST.get(challenge_id)


def _scrubbed_env(base_url: str) -> dict[str, str]:
    env = {"LAB_BASE_URL": base_url, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
    for key in ("PATH", "SYSTEMROOT", "SystemRoot", "TEMP", "TMP", "TMPDIR"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _posix_limits():  # pragma: no cover - POSIX only
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_AS, (2048 * 1024 * 1024, 2048 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))


async def _preflight(base_url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=PREFLIGHT_TIMEOUT_SECONDS) as client:
            resp = await client.get(f"{base_url}/healthz")
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


def _parse_junit(path: str) -> tuple[int, int, int, bool, list[str]]:
    """Returns (tests, failures, errors, saw_connection_error, failing_test_names)."""
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    tests = failures = errors = 0
    connection = False
    failing: list[str] = []
    for suite in suites:
        tests += int(suite.get("tests", 0))
        failures += int(suite.get("failures", 0))
        errors += int(suite.get("errors", 0))
    for case in root.iter("testcase"):
        for node in case:
            if node.tag in ("failure", "error"):
                failing.append(case.get("name", "?"))
                # The message is only inspected for the connection check; it is
                # never stored or returned (it can contain response bodies,
                # including challenge flags).
                text = (node.get("message") or "") + (node.text or "")
                if any(marker in text for marker in _CONNECTION_MARKERS):
                    connection = True
    return tests, failures, errors, connection, failing


def _summary(n_tests: int, n_fail: int, n_err: int, failing: list[str]) -> str:
    text = f"{n_tests} test(s): {n_fail} failure(s), {n_err} error(s)."
    if failing:
        text += " Not passing: " + ", ".join(failing[:20]) + "."
    return text


async def run_lab_tests(
    challenge_id: str, *, base_url: str, timeout_seconds: int
) -> RunResult:
    """Runs the allowlisted test file(s) for one challenge and classifies the
    result. Raises KeyError for a challenge with no allowlist entry and
    RunnerMisconfigured for a disallowed lab address (callers check first)."""
    tests = list(LAB_TEST_ALLOWLIST[challenge_id])
    base_url = validate_base_url(base_url)
    started = time.monotonic()

    def _elapsed_ms() -> int:
        return int((time.monotonic() - started) * 1000)

    if not await _preflight(base_url):
        return RunResult("unreachable", tests, _elapsed_ms(), "Lab did not answer /healthz.")

    with tempfile.TemporaryDirectory(prefix="aegis-labrun-") as tmp:
        junit_path = os.path.join(tmp, "result.xml")
        argv = [
            sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "--junitxml", junit_path, "--rootdir", REPO_ROOT,
            *[os.path.join(REPO_ROOT, t) for t in tests],
        ]
        kwargs: dict = {}
        if os.name == "posix":  # pragma: no cover - POSIX only
            kwargs["preexec_fn"] = _posix_limits
            kwargs["start_new_session"] = True
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=REPO_ROOT,
                env=_scrubbed_env(base_url),
                stdin=asyncio.subprocess.DEVNULL,
                # Raw pytest output is deliberately discarded: on a failing
                # test it can include response bodies (and so challenge
                # flags). Only the structured junit result is used.
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                **kwargs,
            )
        except OSError as exc:
            return RunResult("error", tests, _elapsed_ms(), f"Could not start the test runner: {exc}")

        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            _kill(proc)
            await proc.wait()
            return RunResult("error", tests, _elapsed_ms(), f"Timed out after {timeout_seconds}s.")

        code = proc.returncode
        n_tests = n_fail = n_err = 0
        connection = False
        failing: list[str] = []
        try:
            n_tests, n_fail, n_err, connection, failing = _parse_junit(junit_path)
        except (OSError, ET.ParseError):
            if code in (0, 1):
                return RunResult(
                    "error", tests, _elapsed_ms(), "No structured result was produced.", {"exit_code": code}
                )
        summary = _summary(n_tests, n_fail, n_err, failing)
        if code not in (0, 1):
            summary = f"Test runner exited with code {code}. " + summary

        detail = {"exit_code": code, "tests": n_tests, "failures": n_fail, "errors": n_err}
        if code == 0:
            if n_tests == 0:
                return RunResult("error", tests, _elapsed_ms(), summary, {**detail, "reason": "no tests ran"})
            return RunResult("passed", tests, _elapsed_ms(), summary, detail)
        if code == 1:
            if connection:
                return RunResult("unreachable", tests, _elapsed_ms(), summary, detail)
            return RunResult("failed", tests, _elapsed_ms(), summary, detail)
        # 2 interrupted, 3 internal error, 4 usage error, 5 no tests collected, anything else
        return RunResult("error", tests, _elapsed_ms(), summary, detail)


def _kill(proc: "asyncio.subprocess.Process") -> None:
    try:
        if os.name == "posix":  # pragma: no cover - POSIX only
            import signal

            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except (ProcessLookupError, PermissionError):
        pass
