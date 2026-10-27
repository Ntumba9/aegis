"""API-layer integration tests for the instructor/classroom endpoints
(app/api/classrooms.py)."""
import pytest

from tests.integration.conftest import create_auth_user
from tests.integration.helpers import client_as

pytestmark = pytest.mark.usefixtures("clean_db")


@pytest.mark.asyncio
async def test_creating_a_classroom_makes_you_its_instructor(clean_db):
    pool = clean_db
    dana = await create_auth_user(pool)

    resp = client_as(dana).post("/classrooms", json={"name": "AppSec 101"})
    assert resp.status_code == 201
    assert resp.json()["instructor_id"] == str(dana)

    mine = client_as(dana).get("/classrooms/mine").json()
    assert len(mine) == 1


@pytest.mark.asyncio
async def test_invite_accept_assign_and_progress_flow(clean_db):
    pool = clean_db
    dana = await create_auth_user(pool)  # instructor
    sam = await create_auth_user(pool)   # student

    classroom_id = client_as(dana).post("/classrooms", json={"name": "AppSec 101"}).json()["id"]

    invite_token = client_as(dana).post(f"/classrooms/{classroom_id}/invites").json()["invite_token"]
    accept = client_as(sam).post(f"/classrooms/invites/{invite_token}/accept")
    assert accept.status_code == 201

    students = client_as(dana).get(f"/classrooms/{classroom_id}/students").json()
    assert students[0]["student_id"] == str(sam)

    assign = client_as(dana).post(
        f"/classrooms/{classroom_id}/assignments", json={"challenge_id": "api1-bola-project-files"}
    )
    assert assign.status_code == 201

    # Sam completes the assigned challenge (simulated directly in user_progress,
    # since the verification flow itself is tested in app/challenges/ tests).
    await pool.execute(
        "insert into user_progress (user_id, challenge_id, status, points_awarded, completed_at) "
        "values ($1, 'api1-bola-project-files', 'completed', 100, now())",
        sam,
    )

    report = client_as(dana).get(f"/classrooms/{classroom_id}/progress").json()
    assert report == [
        {
            "student_id": str(sam),
            "challenge_id": "api1-bola-project-files",
            "status": "completed",
            "points_awarded": 100,
            "completed_at": report[0]["completed_at"],
        }
    ]


@pytest.mark.asyncio
async def test_student_cannot_see_the_full_classroom_progress_report(clean_db):
    """Privacy boundary: a student sees their own progress via
    /challenges/progress/me, not their classmates' — only the instructor
    can call /classrooms/{id}/progress."""
    pool = clean_db
    dana = await create_auth_user(pool)
    sam = await create_auth_user(pool)

    classroom_id = client_as(dana).post("/classrooms", json={"name": "AppSec 101"}).json()["id"]
    invite_token = client_as(dana).post(f"/classrooms/{classroom_id}/invites").json()["invite_token"]
    client_as(sam).post(f"/classrooms/invites/{invite_token}/accept")

    resp = client_as(sam).get(f"/classrooms/{classroom_id}/progress")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_invite_token_is_single_use(clean_db):
    pool = clean_db
    dana = await create_auth_user(pool)
    sam = await create_auth_user(pool)
    mallory = await create_auth_user(pool)

    classroom_id = client_as(dana).post("/classrooms", json={"name": "AppSec 101"}).json()["id"]
    invite_token = client_as(dana).post(f"/classrooms/{classroom_id}/invites").json()["invite_token"]

    assert client_as(sam).post(f"/classrooms/invites/{invite_token}/accept").status_code == 201
    second_use = client_as(mallory).post(f"/classrooms/invites/{invite_token}/accept")
    assert second_use.status_code == 404
