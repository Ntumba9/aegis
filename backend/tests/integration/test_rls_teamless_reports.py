"""RLS regression for migration 0010: team-less vulnerability reports and
their retests must not be readable or editable by an arbitrary
authenticated user through PostgREST.

Before 0010, `vuln_reports_team_select`/`vuln_reports_team_update` used
`team_id is null or is_team_member(team_id)` — `team_id is null` made
every team-less report visible to everyone. These tests connect as the
RLS-restricted `authenticated` role (same mechanism PostgREST uses), so
they would have caught that at the database layer.
"""
import pytest

from tests.integration.conftest import AsUser, create_auth_user

pytestmark = pytest.mark.usefixtures("clean_db")

CHALLENGE_ID = "api1-bola-project-files"  # seeded from the public catalog


async def _make_report(pool, reporter_id, assignee_id=None, team_id=None):
    row = await pool.fetchrow(
        "insert into vulnerability_reports (team_id, reporter_id, challenge_id, "
        "title, severity, description, assignee_id) "
        "values ($1, $2, $3, 'Reflected SSRF in preview', 'high', 'details', $4) "
        "returning id",
        team_id,
        reporter_id,
        CHALLENGE_ID,
        assignee_id,
    )
    return row["id"]


@pytest.mark.asyncio
async def test_teamless_report_hidden_from_unrelated_user(clean_db):
    pool = clean_db
    reporter = await create_auth_user(pool)
    stranger = await create_auth_user(pool)
    report_id = await _make_report(pool, reporter)

    rows = await AsUser(pool, stranger).fetch(
        "select id from vulnerability_reports where id = $1", report_id
    )
    assert rows == []


@pytest.mark.asyncio
async def test_teamless_report_visible_to_reporter_and_assignee(clean_db):
    pool = clean_db
    reporter = await create_auth_user(pool)
    assignee = await create_auth_user(pool)
    report_id = await _make_report(pool, reporter, assignee_id=assignee)

    for uid in (reporter, assignee):
        rows = await AsUser(pool, uid).fetch(
            "select id from vulnerability_reports where id = $1", report_id
        )
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_teamless_report_not_updatable_by_unrelated_user(clean_db):
    pool = clean_db
    reporter = await create_auth_user(pool)
    stranger = await create_auth_user(pool)
    report_id = await _make_report(pool, reporter)

    status = await AsUser(pool, stranger).execute(
        "update vulnerability_reports set remediation_status = 'fixed' where id = $1",
        report_id,
    )
    assert status == "UPDATE 0"
    row = await pool.fetchrow(
        "select remediation_status from vulnerability_reports where id = $1", report_id
    )
    assert row["remediation_status"] == "open"


@pytest.mark.asyncio
async def test_team_report_still_visible_to_team_member(clean_db):
    pool = clean_db
    reporter = await create_auth_user(pool)
    member = await create_auth_user(pool)
    stranger = await create_auth_user(pool)
    team = await pool.fetchrow(
        "insert into teams (name, mode, created_by) values ('Blue', 'blue', $1) returning id",
        reporter,
    )
    await pool.execute(
        "insert into team_members (team_id, user_id) values ($1, $2)", team["id"], reporter
    )
    await pool.execute(
        "insert into team_members (team_id, user_id) values ($1, $2)", team["id"], member
    )
    report_id = await _make_report(pool, reporter, team_id=team["id"])

    rows = await AsUser(pool, member).fetch(
        "select id from vulnerability_reports where id = $1", report_id
    )
    assert len(rows) == 1
    rows = await AsUser(pool, stranger).fetch(
        "select id from vulnerability_reports where id = $1", report_id
    )
    assert rows == []


@pytest.mark.asyncio
async def test_retests_follow_parent_report_visibility(clean_db):
    pool = clean_db
    reporter = await create_auth_user(pool)
    assignee = await create_auth_user(pool)
    stranger = await create_auth_user(pool)
    report_id = await _make_report(pool, reporter, assignee_id=assignee)
    await pool.execute(
        "insert into retests (report_id, tester_id, result) values ($1, $2, 'still_vulnerable')",
        report_id,
        reporter,
    )

    assert await AsUser(pool, stranger).fetch("select id from retests") == []
    assert len(await AsUser(pool, assignee).fetch("select id from retests")) == 1
