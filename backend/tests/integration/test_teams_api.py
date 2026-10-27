"""API-layer integration tests for the Red Team / Blue Team collaboration
endpoints (app/api/teams.py), run against the real app + a real Postgres."""
import pytest

from tests.integration.conftest import create_auth_user
from tests.integration.helpers import client_as

pytestmark = pytest.mark.usefixtures("clean_db")


@pytest.mark.asyncio
async def test_create_team_makes_creator_a_lead(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)

    resp = client_as(alice).post("/teams", json={"name": "Night Owls", "mode": "red"})
    assert resp.status_code == 201
    team_id = resp.json()["id"]

    members = client_as(alice).get(f"/teams/{team_id}/members").json()
    assert len(members) == 1
    assert members[0]["role"] == "lead"


@pytest.mark.asyncio
async def test_non_member_cannot_list_members(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    bob = await create_auth_user(pool)

    team_id = client_as(alice).post("/teams", json={"name": "Night Owls", "mode": "red"}).json()["id"]

    resp = client_as(bob).get(f"/teams/{team_id}/members")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_join_then_list_members_shows_both(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    bob = await create_auth_user(pool)

    team_id = client_as(alice).post("/teams", json={"name": "Night Owls", "mode": "red"}).json()["id"]
    join_resp = client_as(bob).post(f"/teams/{team_id}/join")
    assert join_resp.status_code == 201
    assert join_resp.json()["role"] == "member"

    members = client_as(alice).get(f"/teams/{team_id}/members").json()
    assert {m["user_id"] for m in members} == {str(alice), str(bob)}


@pytest.mark.asyncio
async def test_report_assign_and_retest_flow(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    bob = await create_auth_user(pool)
    team_id = client_as(alice).post("/teams", json={"name": "Night Owls", "mode": "mixed"}).json()["id"]
    client_as(bob).post(f"/teams/{team_id}/join")

    report = client_as(alice).post(
        "/teams/reports",
        json={
            "team_id": team_id,
            "challenge_id": "api1-bola-project-files",
            "title": "BOLA on /projects/{id}",
            "severity": "high",
            "description": "No ownership check on project read.",
        },
    ).json()
    assert report["remediation_status"] == "open"

    assigned = client_as(alice).patch(
        f"/teams/reports/{report['id']}/assign",
        json={"assignee_id": str(bob), "remediation_status": "in_progress"},
    ).json()
    assert assigned["assignee_id"] == str(bob)
    assert assigned["remediation_status"] == "in_progress"

    retest = client_as(bob).post(
        f"/teams/reports/{report['id']}/retest", json={"result": "fixed", "notes": "Added ownership check."}
    )
    assert retest.status_code == 201

    reports = client_as(alice).get(f"/teams/{team_id}/reports").json()
    assert reports[0]["remediation_status"] == "fixed"


@pytest.mark.asyncio
async def test_outsider_cannot_file_a_report_against_a_team_they_are_not_in(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    mallory = await create_auth_user(pool)
    team_id = client_as(alice).post("/teams", json={"name": "Night Owls", "mode": "mixed"}).json()["id"]

    resp = client_as(mallory).post(
        "/teams/reports",
        json={
            "team_id": team_id,
            "challenge_id": "api1-bola-project-files",
            "title": "x",
            "severity": "low",
            "description": "x",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_export_report_as_markdown(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    team_id = client_as(alice).post("/teams", json={"name": "Night Owls", "mode": "red"}).json()["id"]
    report = client_as(alice).post(
        "/teams/reports",
        json={
            "team_id": team_id,
            "challenge_id": "api7-ssrf-url-preview",
            "title": "SSRF via url-preview",
            "severity": "critical",
            "description": "Internal mock reachable from the preview endpoint.",
        },
    ).json()

    resp = client_as(alice).get(f"/teams/reports/{report['id']}/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert "SSRF via url-preview" in resp.text
    assert "api7-ssrf-url-preview" in resp.text
    assert "critical" in resp.text


@pytest.mark.asyncio
async def test_starting_an_attack_session_awards_red_team_rookie(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    await pool.execute(
        "insert into achievements (id, title, description, icon) values "
        "('red-team-rookie', 'Red Team Rookie', 'x', 'sword')"
    )
    team_id = client_as(alice).post("/teams", json={"name": "Night Owls", "mode": "red"}).json()["id"]

    resp = client_as(alice).post(
        f"/teams/{team_id}/sessions", json={"challenge_id": "api1-bola-project-files", "mode": "attack"}
    )
    assert resp.status_code == 201

    row = await pool.fetchrow(
        "select 1 from user_achievements where user_id = $1 and achievement_id = 'red-team-rookie'",
        alice,
    )
    assert row is not None
