"""Server-run lab regression check for a vulnerability report.

LOCAL DEV ONLY and OFF by default (settings.lab_retest_runner_enabled).
It runs the lab's own vulnerable-vs-hardened regression test for the
report's challenge and records the real outcome. That is evidence about the
lab's reference implementation, NOT about a team's fix — see
app/services/lab_runner.py. It never changes a report's remediation status
or writes a `retests` row (those stay human-declared).
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.api.teams import _require_member, require_report_access
from app.core.audit import record_event
from app.core.auth import CurrentUser, get_current_user
from app.core.config import settings
from app.db.session import get_pool
from app.schemas.lab_verification import LabRunOut
from app.services import lab_runner

router = APIRouter(prefix="/teams/reports", tags=["lab-verification"])

COOLDOWN_SECONDS = 60  # per challenge: the lab's own rate limiters are stateful
MAX_RUNS_PER_USER_PER_MINUTE = 3
# One run at a time across ALL backend workers (a Postgres advisory lock).
LAB_RUN_LOCK_KEY = 0x4145_4749_5301

_COLUMNS = (
    "id, report_id, challenge_id, requested_by, outcome, tests, duration_ms, "
    "summary, started_at, finished_at"
)


def _busy(detail: str, retry_after: int) -> HTTPException:
    return HTTPException(status_code=429, detail=detail, headers={"Retry-After": str(retry_after)})


async def _authorize_run(pool, report, user: CurrentUser) -> None:
    """Team report: team leads only. Team-less report: its reporter only."""
    if report["team_id"] is not None:
        await _require_member(pool, report["team_id"], user.id)
        role = await pool.fetchval(
            "select role from team_members where team_id = $1 and user_id = $2",
            report["team_id"],
            user.id,
        )
        if role != "lead":
            raise HTTPException(status_code=403, detail="Only a team lead can run lab verification")
    elif report["reporter_id"] != user.id:
        raise HTTPException(status_code=403, detail="Only the reporter can run lab verification")


@router.post("/{report_id}/lab-verification", response_model=LabRunOut, status_code=201)
async def run_lab_verification(report_id: UUID, user: CurrentUser = Depends(get_current_user)):
    if not settings.lab_retest_runner_enabled:
        raise HTTPException(status_code=404, detail="Not found")

    pool = await get_pool()
    report = await pool.fetchrow(
        "select id, team_id, reporter_id, assignee_id, challenge_id "
        "from vulnerability_reports where id = $1",
        report_id,
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    try:
        await _authorize_run(pool, report, user)
    except HTTPException as exc:
        await record_event(
            org_id=None,
            actor_id=user.id,
            event_type="lab_verification_denied",
            severity="warning",
            metadata={"report_id": str(report_id), "reason": exc.detail},
        )
        raise

    challenge_id = report["challenge_id"]
    tests = lab_runner.tests_for(challenge_id)
    if tests is None:
        raise HTTPException(status_code=422, detail="No lab test is configured for this challenge")
    try:
        base_url = lab_runner.validate_base_url(settings.lab_retest_base_url)
    except lab_runner.RunnerMisconfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    recent_by_user = await pool.fetchval(
        "select count(*) from retest_lab_runs "
        "where requested_by = $1 and started_at > now() - interval '1 minute'",
        user.id,
    )
    if recent_by_user >= MAX_RUNS_PER_USER_PER_MINUTE:
        raise _busy("Too many lab verification runs, slow down", 60)
    cooling = await pool.fetchval(
        "select count(*) from retest_lab_runs "
        "where challenge_id = $1 and finished_at > now() - make_interval(secs => $2)",
        challenge_id,
        COOLDOWN_SECONDS,
    )
    if cooling:
        raise _busy("This challenge's lab test ran very recently; try again shortly", COOLDOWN_SECONDS)

    async with pool.acquire() as lock_conn:
        if not await lock_conn.fetchval("select pg_try_advisory_lock($1)", LAB_RUN_LOCK_KEY):
            raise _busy("Another lab verification is running; try again shortly", 10)
        try:
            started_at = datetime.now(timezone.utc)
            await record_event(
                org_id=None,
                actor_id=user.id,
                event_type="lab_verification_started",
                severity="info",
                metadata={"report_id": str(report_id), "challenge_id": challenge_id, "tests": list(tests)},
            )
            result = await lab_runner.run_lab_tests(
                challenge_id,
                base_url=base_url,
                timeout_seconds=settings.lab_retest_timeout_seconds,
            )
            finished_at = datetime.now(timezone.utc)
            row = await pool.fetchrow(
                "insert into retest_lab_runs (report_id, challenge_id, requested_by, outcome, tests, "
                "duration_ms, summary, started_at, finished_at) "
                "values ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
                f"returning {_COLUMNS}",
                report_id,
                challenge_id,
                user.id,
                result.outcome,
                result.tests,
                result.duration_ms,
                result.summary,
                started_at,
                finished_at,
            )
            await record_event(
                org_id=None,
                actor_id=user.id,
                event_type="lab_verification_finished",
                severity="info" if result.outcome == "passed" else "warning",
                metadata={
                    "report_id": str(report_id),
                    "run_id": str(row["id"]),
                    "challenge_id": challenge_id,
                    "tests": result.tests,
                    "outcome": result.outcome,
                    "duration_ms": result.duration_ms,
                },
            )
        finally:
            await lock_conn.execute("select pg_advisory_unlock($1)", LAB_RUN_LOCK_KEY)
    return dict(row)


@router.get("/{report_id}/lab-verifications", response_model=list[LabRunOut])
async def list_lab_verifications(report_id: UUID, user: CurrentUser = Depends(get_current_user)):
    if not settings.lab_retest_runner_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    pool = await get_pool()
    report = await pool.fetchrow(
        "select team_id, reporter_id, assignee_id from vulnerability_reports where id = $1", report_id
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    await require_report_access(pool, report, user.id)
    rows = await pool.fetch(
        f"select {_COLUMNS} from retest_lab_runs where report_id = $1 order by started_at desc",
        report_id,
    )
    return [dict(r) for r in rows]
