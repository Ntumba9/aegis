"""Server-run lab regression check (app/api/lab_verification.py).

Most tests replace the runner with a fake so authorization, limits and
outcome recording can be checked quickly and deterministically; two tests
drive the REAL subprocess runner end to end (a passing run, and a timeout).
"""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.core.config import settings
from app.services import lab_runner
from app.services.lab_runner import RunResult
from tests.integration.conftest import create_auth_user
from tests.integration.helpers import client_as

pytestmark = pytest.mark.usefixtures("clean_db")

CHALLENGE = "api1-bola-project-files"


class _Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_runner(monkeypatch):
    """Feature on; runner replaced. Set `fake_runner.outcome` per test."""
    monkeypatch.setattr(settings, "lab_retest_runner_enabled", True)

    class Fake:
        outcome = "passed"
        calls = 0

    async def _fake(challenge_id, *, base_url, timeout_seconds):
        Fake.calls += 1
        return RunResult(Fake.outcome, list(lab_runner.LAB_TEST_ALLOWLIST[challenge_id]), 7, "fake run")

    Fake.outcome, Fake.calls = "passed", 0
    monkeypatch.setattr(lab_runner, "run_lab_tests", _fake)
    return Fake


async def _team_with_report(pool, challenge=CHALLENGE):
    lead = await create_auth_user(pool)
    member = await create_auth_user(pool)
    team_id = client_as(lead).post("/teams", json={"name": "Blue", "mode": "blue"}).json()["id"]
    client_as(member).post(f"/teams/{team_id}/join")
    report = client_as(lead).post(
        "/teams/reports",
        json={"team_id": team_id, "challenge_id": challenge, "title": "BOLA", "severity": "high",
              "description": "x"},
    ).json()
    return lead, member, team_id, report["id"]


def _run(user, report_id):
    return client_as(user).post(f"/teams/reports/{report_id}/lab-verification")


@pytest.mark.asyncio
async def test_off_by_default(clean_db):
    lead, _, _, report_id = await _team_with_report(clean_db)
    assert settings.lab_retest_runner_enabled is False
    assert _run(lead, report_id).status_code == 404


@pytest.mark.asyncio
async def test_lead_runs_it_and_the_real_outcome_is_recorded(clean_db, fake_runner):
    pool = clean_db
    lead, _, _, report_id = await _team_with_report(pool)

    resp = _run(lead, report_id)
    assert resp.status_code == 201
    body = resp.json()
    assert body["outcome"] == "passed" and body["challenge_id"] == CHALLENGE
    assert body["tests"] == ["lab/tests/test_bola.py"] and body["requested_by"] == str(lead)
    assert "not proof that a team remediated" in body["scope_note"]

    # It is evidence only: the human-declared remediation state is untouched.
    assert await pool.fetchval("select remediation_status from vulnerability_reports") == "open"
    assert await pool.fetchval("select count(*) from retests") == 0

    # Trigger, tests run and outcome all land in the audit trail.
    events = await pool.fetch(
        "select event_type, metadata::text as m from security_events "
        "where event_type like 'lab_verification_%' order by created_at"
    )
    assert [e["event_type"] for e in events] == ["lab_verification_started", "lab_verification_finished"]
    assert "test_bola.py" in events[0]["m"] and '"passed"' in events[1]["m"]


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["passed", "failed", "error", "unreachable"])
async def test_each_outcome_state_is_recorded_distinctly(clean_db, fake_runner, outcome):
    pool = clean_db
    lead, _, _, report_id = await _team_with_report(pool)
    fake_runner.outcome = outcome

    assert _run(lead, report_id).json()["outcome"] == outcome
    assert await pool.fetchval("select outcome from retest_lab_runs") == outcome
    finished = await pool.fetchval(
        "select metadata->>'outcome' from security_events where event_type = 'lab_verification_finished'"
    )
    assert finished == outcome


@pytest.mark.asyncio
async def test_a_plain_member_cannot_trigger_it(clean_db, fake_runner):
    pool = clean_db
    _, member, _, report_id = await _team_with_report(pool)
    assert _run(member, report_id).status_code == 403
    assert fake_runner.calls == 0
    assert await pool.fetchval("select count(*) from security_events where event_type = 'lab_verification_denied'") == 1


@pytest.mark.asyncio
async def test_an_outsider_and_another_teams_lead_cannot_trigger_it(clean_db, fake_runner):
    pool = clean_db
    _, _, _, report_id = await _team_with_report(pool)
    outsider = await create_auth_user(pool)
    other_lead = await create_auth_user(pool)
    client_as(other_lead).post("/teams", json={"name": "Rival", "mode": "blue"})  # leads a different team

    assert _run(outsider, report_id).status_code == 403
    assert _run(other_lead, report_id).status_code == 403  # cross-tenant trigger
    assert fake_runner.calls == 0
    assert await pool.fetchval("select count(*) from retest_lab_runs") == 0


@pytest.mark.asyncio
async def test_team_less_report_is_reporter_only(clean_db, fake_runner):
    pool = clean_db
    alice = await create_auth_user(pool)
    mallory = await create_auth_user(pool)
    report_id = client_as(alice).post(
        "/teams/reports",
        json={"challenge_id": CHALLENGE, "title": "T", "severity": "low", "description": "x"},
    ).json()["id"]

    assert _run(mallory, report_id).status_code == 403
    assert _run(alice, report_id).status_code == 201


@pytest.mark.asyncio
async def test_team_less_reports_are_no_longer_open_to_every_user(clean_db):
    """Previously assign / retest / export skipped every check when a report
    had no team, so any signed-in user could use them by id."""
    pool = clean_db
    alice = await create_auth_user(pool)
    mallory = await create_auth_user(pool)
    report_id = client_as(alice).post(
        "/teams/reports",
        json={"challenge_id": CHALLENGE, "title": "T", "severity": "low", "description": "x"},
    ).json()["id"]

    assert client_as(mallory).get(f"/teams/reports/{report_id}/export").status_code == 403
    assert client_as(mallory).post(
        f"/teams/reports/{report_id}/retest", json={"result": "fixed"}
    ).status_code == 403
    assert client_as(mallory).patch(
        f"/teams/reports/{report_id}/assign", json={"assignee_id": str(mallory)}
    ).status_code == 403
    assert client_as(alice).get(f"/teams/reports/{report_id}/export").status_code == 200


@pytest.mark.asyncio
async def test_unknown_challenge_and_bad_lab_address_are_refused(clean_db, fake_runner, monkeypatch):
    lead, _, _, report_id = await _team_with_report(clean_db)
    monkeypatch.setattr(settings, "lab_retest_base_url", "http://example.com:8100")
    assert _run(lead, report_id).status_code == 503  # lab host not on the allowed list

    monkeypatch.setattr(settings, "lab_retest_base_url", "http://127.0.0.1:8100")
    monkeypatch.delitem(lab_runner.LAB_TEST_ALLOWLIST, CHALLENGE)
    assert _run(lead, report_id).status_code == 422
    assert fake_runner.calls == 0


@pytest.mark.asyncio
async def test_busy_when_another_run_holds_the_lock(clean_db, fake_runner):
    pool = clean_db
    lead, _, _, report_id = await _team_with_report(pool)
    from app.api.lab_verification import LAB_RUN_LOCK_KEY

    async with pool.acquire() as holder:
        await holder.fetchval("select pg_advisory_lock($1)", LAB_RUN_LOCK_KEY)
        try:
            resp = _run(lead, report_id)
        finally:
            await holder.fetchval("select pg_advisory_unlock($1)", LAB_RUN_LOCK_KEY)

    assert resp.status_code == 429 and "Retry-After" in resp.headers
    assert fake_runner.calls == 0
    assert _run(lead, report_id).status_code == 201  # and it works once the lock is free


@pytest.mark.asyncio
async def test_same_challenge_has_a_cooldown(clean_db, fake_runner):
    lead, _, _, report_id = await _team_with_report(clean_db)
    assert _run(lead, report_id).status_code == 201
    second = _run(lead, report_id)
    assert second.status_code == 429 and "Retry-After" in second.headers
    assert fake_runner.calls == 1


@pytest.mark.asyncio
async def test_per_user_rate_limit(clean_db, fake_runner):
    pool = clean_db
    lead, _, _, report_id = await _team_with_report(pool)
    for other in ("api2-broken-auth-predictable-session", "api3-bopla-role-escalation", "api5-bfla-admin-broadcast"):
        await pool.execute(
            "insert into retest_lab_runs (report_id, challenge_id, requested_by, outcome, tests, duration_ms, "
            "summary, started_at, finished_at) values ($1, $2, $3, 'passed', '{}', 1, '', now(), now() - interval '5 minutes')",
            report_id, other, lead,
        )
    resp = _run(lead, report_id)  # 4th run inside a minute (started_at recent), different challenge is irrelevant
    assert resp.status_code == 429
    assert fake_runner.calls == 0


@pytest.mark.asyncio
async def test_members_can_list_runs_outsiders_cannot(clean_db, fake_runner):
    pool = clean_db
    lead, member, _, report_id = await _team_with_report(pool)
    _run(lead, report_id)
    outsider = await create_auth_user(pool)

    assert len(client_as(member).get(f"/teams/reports/{report_id}/lab-verifications").json()) == 1
    assert client_as(outsider).get(f"/teams/reports/{report_id}/lab-verifications").status_code == 403


# --- the REAL runner, end to end through the API ----------------------------

@pytest.fixture
def real_runner_env(monkeypatch, tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Health)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(settings, "lab_retest_runner_enabled", True)
    monkeypatch.setattr(settings, "lab_retest_base_url", f"http://127.0.0.1:{server.server_address[1]}")

    def _install(source: str):
        path = tmp_path / "test_real.py"
        path.write_text(source)
        monkeypatch.setitem(lab_runner.LAB_TEST_ALLOWLIST, CHALLENGE, (str(path),))

    yield _install
    server.shutdown()


@pytest.mark.asyncio
async def test_real_runner_passing_run(clean_db, real_runner_env):
    lead, _, _, report_id = await _team_with_report(clean_db)
    real_runner_env("def test_ok():\n    assert True\n")
    body = _run(lead, report_id).json()
    assert body["outcome"] == "passed" and "1 test(s)" in body["summary"]


@pytest.mark.asyncio
async def test_real_runner_timeout_is_recorded_as_error_not_passed(clean_db, real_runner_env, monkeypatch):
    pool = clean_db
    lead, _, _, report_id = await _team_with_report(pool)
    monkeypatch.setattr(settings, "lab_retest_timeout_seconds", 2)
    real_runner_env("import time\n\ndef test_hang():\n    time.sleep(60)\n")

    resp = _run(lead, report_id)
    assert resp.status_code == 201
    assert resp.json()["outcome"] == "error" and "Timed out" in resp.json()["summary"]
    assert await pool.fetchval("select outcome from retest_lab_runs") == "error"
