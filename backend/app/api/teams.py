"""Red Team / Blue Team collaboration: teams, shared testing sessions,
vulnerability reports, remediation assignment, and retesting.

The backend connects with a service-role-equivalent connection and
therefore bypasses Postgres RLS, so every membership/ownership check that
RLS would otherwise enforce (see supabase/migrations/0005_challenge_platform_rls.sql)
is re-implemented explicitly here.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.core.auth import CurrentUser, get_current_user
from app.db.session import get_pool
from app.services.achievements import evaluate_after_team_session
from app.schemas.teams import (
    RetestCreate,
    RetestOut,
    TeamCreate,
    TeamMemberOut,
    TeamOut,
    TeamSessionCreate,
    TeamSessionOut,
    VulnReportAssign,
    VulnReportCreate,
    VulnReportOut,
)

router = APIRouter(prefix="/teams", tags=["teams"])


async def _require_member(pool, team_id: UUID, user_id: UUID) -> None:
    row = await pool.fetchrow(
        "select 1 from team_members where team_id = $1 and user_id = $2", team_id, user_id
    )
    if row is None:
        raise HTTPException(status_code=403, detail="Not a member of this team")


@router.post("", response_model=TeamOut, status_code=201)
async def create_team(body: TeamCreate, user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            team = await conn.fetchrow(
                "insert into teams (name, mode, created_by) values ($1, $2, $3) "
                "returning id, name, mode, created_by, created_at",
                body.name,
                body.mode,
                user.id,
            )
            await conn.execute(
                "insert into team_members (team_id, user_id, role) values ($1, $2, 'lead')",
                team["id"],
                user.id,
            )
    return dict(team)


@router.get("/mine", response_model=list[TeamOut])
async def my_teams(user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    rows = await pool.fetch(
        "select t.id, t.name, t.mode, t.created_by, t.created_at from teams t "
        "join team_members m on m.team_id = t.id where m.user_id = $1",
        user.id,
    )
    return [dict(r) for r in rows]


@router.post("/{team_id}/join", response_model=TeamMemberOut, status_code=201)
async def join_team(team_id: UUID, user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    team = await pool.fetchrow("select 1 from teams where id = $1", team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    row = await pool.fetchrow(
        "insert into team_members (team_id, user_id, role) values ($1, $2, 'member') "
        "on conflict (team_id, user_id) do nothing "
        "returning team_id, user_id, role, joined_at",
        team_id,
        user.id,
    )
    if row is None:
        row = await pool.fetchrow(
            "select team_id, user_id, role, joined_at from team_members "
            "where team_id = $1 and user_id = $2",
            team_id,
            user.id,
        )
    return dict(row)


@router.get("/{team_id}/members", response_model=list[TeamMemberOut])
async def list_team_members(team_id: UUID, user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    await _require_member(pool, team_id, user.id)
    rows = await pool.fetch(
        "select team_id, user_id, role, joined_at from team_members where team_id = $1", team_id
    )
    return [dict(r) for r in rows]


@router.post("/{team_id}/sessions", response_model=TeamSessionOut, status_code=201)
async def start_team_session(
    team_id: UUID, body: TeamSessionCreate, user: CurrentUser = Depends(get_current_user)
):
    pool = await get_pool()
    await _require_member(pool, team_id, user.id)
    row = await pool.fetchrow(
        "insert into team_sessions (team_id, challenge_id, mode) values ($1, $2, $3) "
        "returning id, team_id, challenge_id, mode, started_at, ended_at",
        team_id,
        body.challenge_id,
        body.mode,
    )
    await evaluate_after_team_session(user.id, body.mode)
    return dict(row)


@router.post("/{team_id}/sessions/{session_id}/end", status_code=204)
async def end_team_session(team_id: UUID, session_id: UUID, user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    await _require_member(pool, team_id, user.id)
    await pool.execute(
        "update team_sessions set ended_at = now() where id = $1 and team_id = $2", session_id, team_id
    )


@router.get("/{team_id}/sessions", response_model=list[TeamSessionOut])
async def list_team_sessions(team_id: UUID, user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    await _require_member(pool, team_id, user.id)
    rows = await pool.fetch(
        "select id, team_id, challenge_id, mode, started_at, ended_at from team_sessions "
        "where team_id = $1 order by started_at desc",
        team_id,
    )
    return [dict(r) for r in rows]


@router.post("/reports", response_model=VulnReportOut, status_code=201)
async def create_report(body: VulnReportCreate, user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    if body.team_id is not None:
        await _require_member(pool, body.team_id, user.id)
    row = await pool.fetchrow(
        "insert into vulnerability_reports (team_id, reporter_id, challenge_id, title, severity, description) "
        "values ($1, $2, $3, $4, $5, $6) "
        "returning id, team_id, reporter_id, challenge_id, title, severity, description, "
        "remediation_status, assignee_id, created_at",
        body.team_id,
        user.id,
        body.challenge_id,
        body.title,
        body.severity,
        body.description,
    )
    return dict(row)


@router.get("/reports/mine", response_model=list[VulnReportOut])
async def my_reports(user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    rows = await pool.fetch(
        "select id, team_id, reporter_id, challenge_id, title, severity, description, "
        "remediation_status, assignee_id, created_at from vulnerability_reports "
        "where reporter_id = $1 or assignee_id = $1 order by created_at desc",
        user.id,
    )
    return [dict(r) for r in rows]


@router.get("/{team_id}/reports", response_model=list[VulnReportOut])
async def list_team_reports(team_id: UUID, user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    await _require_member(pool, team_id, user.id)
    rows = await pool.fetch(
        "select id, team_id, reporter_id, challenge_id, title, severity, description, "
        "remediation_status, assignee_id, created_at from vulnerability_reports "
        "where team_id = $1 order by created_at desc",
        team_id,
    )
    return [dict(r) for r in rows]


@router.patch("/reports/{report_id}/assign", response_model=VulnReportOut)
async def assign_report(
    report_id: UUID, body: VulnReportAssign, user: CurrentUser = Depends(get_current_user)
):
    pool = await get_pool()
    report = await pool.fetchrow("select team_id from vulnerability_reports where id = $1", report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if report["team_id"] is not None:
        await _require_member(pool, report["team_id"], user.id)
    row = await pool.fetchrow(
        "update vulnerability_reports set assignee_id = $1, remediation_status = $2 "
        "where id = $3 returning id, team_id, reporter_id, challenge_id, title, severity, "
        "description, remediation_status, assignee_id, created_at",
        body.assignee_id,
        body.remediation_status,
        report_id,
    )
    return dict(row)


@router.post("/reports/{report_id}/retest", response_model=RetestOut, status_code=201)
async def retest_report(
    report_id: UUID, body: RetestCreate, user: CurrentUser = Depends(get_current_user)
):
    pool = await get_pool()
    report = await pool.fetchrow("select team_id from vulnerability_reports where id = $1", report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if report["team_id"] is not None:
        await _require_member(pool, report["team_id"], user.id)
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "insert into retests (report_id, tester_id, result, notes) values ($1, $2, $3, $4) "
                "returning id, report_id, tester_id, result, notes, created_at",
                report_id,
                user.id,
                body.result,
                body.notes,
            )
            if body.result == "fixed":
                await conn.execute(
                    "update vulnerability_reports set remediation_status = 'fixed' where id = $1",
                    report_id,
                )
    return dict(row)


@router.get("/reports/{report_id}/export")
async def export_report_markdown(report_id: UUID, user: CurrentUser = Depends(get_current_user)):
    """Red Team report export. Markdown only (no PDF renderer dependency) —
    pipe through `pandoc` or any Markdown-to-PDF tool if a PDF is needed."""
    pool = await get_pool()
    report = await pool.fetchrow(
        "select id, team_id, reporter_id, challenge_id, title, severity, description, "
        "remediation_status, assignee_id, created_at from vulnerability_reports where id = $1",
        report_id,
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if report["team_id"] is not None:
        await _require_member(pool, report["team_id"], user.id)

    retests = await pool.fetch(
        "select tester_id, result, notes, created_at from retests where report_id = $1 order by created_at",
        report_id,
    )

    lines = [
        f"# {report['title']}",
        "",
        f"- **Challenge:** `{report['challenge_id']}`",
        f"- **Severity:** {report['severity']}",
        f"- **Status:** {report['remediation_status']}",
        f"- **Reported:** {report['created_at'].isoformat()}",
        f"- **Assignee:** {report['assignee_id'] or '_unassigned_'}",
        "",
        "## Description",
        "",
        report["description"],
    ]
    if retests:
        lines += ["", "## Retest history", ""]
        for rt in retests:
            lines.append(f"- {rt['created_at'].isoformat()} — **{rt['result']}**" + (f" — {rt['notes']}" if rt["notes"] else ""))

    markdown = "\n".join(lines) + "\n"
    return Response(
        content=markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="report-{report_id}.md"'},
    )
