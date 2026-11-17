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
    # ...and the same user cannot replay it either.
    assert client_as(sam).post(f"/classrooms/invites/{invite_token}/accept").status_code == 404


@pytest.mark.asyncio
async def test_invite_token_survives_a_backend_restart(clean_db):
    """Tokens live in the database, not in process memory: after the app's
    connection pool is torn down and rebuilt (what a restart does to
    everything held in memory), an issued invite still works."""
    import app.api.classrooms as classrooms_module
    import app.db.session as db_session
    import asyncpg
    from tests.integration.conftest import TEST_DATABASE_URL
    from tests.integration.helpers import run_in_app_loop

    pool = clean_db
    dana = await create_auth_user(pool)
    sam = await create_auth_user(pool)
    classroom_id = client_as(dana).post("/classrooms", json={"name": "AppSec 101"}).json()["id"]
    invite_token = client_as(dana).post(f"/classrooms/{classroom_id}/invites").json()["invite_token"]

    assert not hasattr(classrooms_module, "_invite_tokens")  # no in-process store left

    async def _restart():
        await db_session._pool.close()
        db_session._pool = await asyncpg.create_pool(TEST_DATABASE_URL, min_size=1, max_size=5)

    run_in_app_loop(_restart())

    assert client_as(sam).post(f"/classrooms/invites/{invite_token}/accept").status_code == 201


@pytest.mark.asyncio
async def test_expired_invite_is_rejected_and_does_not_enrol(clean_db):
    pool = clean_db
    dana = await create_auth_user(pool)
    sam = await create_auth_user(pool)
    classroom_id = client_as(dana).post("/classrooms", json={"name": "AppSec 101"}).json()["id"]
    invite_token = client_as(dana).post(f"/classrooms/{classroom_id}/invites").json()["invite_token"]

    await pool.execute("update classroom_invites set expires_at = now() - interval '1 minute'")

    resp = client_as(sam).post(f"/classrooms/invites/{invite_token}/accept")
    assert resp.status_code == 404
    assert client_as(dana).get(f"/classrooms/{classroom_id}/students").json() == []


@pytest.mark.asyncio
async def test_only_a_hash_of_the_token_is_stored(clean_db):
    import hashlib

    pool = clean_db
    dana = await create_auth_user(pool)
    classroom_id = client_as(dana).post("/classrooms", json={"name": "AppSec 101"}).json()["id"]
    invite_token = client_as(dana).post(f"/classrooms/{classroom_id}/invites").json()["invite_token"]

    stored = await pool.fetchval("select token_hash from classroom_invites")
    assert stored == hashlib.sha256(invite_token.encode()).hexdigest()
    assert stored != invite_token


@pytest.mark.asyncio
async def test_concurrent_accepts_of_one_token_only_one_wins(clean_db):
    """The consume step is a single conditional UPDATE, so two simultaneous
    accepts of the same token cannot both succeed (the old in-memory dict
    could raise a KeyError on exactly this race)."""
    import asyncio

    from app.api.classrooms import consume_invite

    pool = clean_db
    dana = await create_auth_user(pool)
    sam = await create_auth_user(pool)
    mallory = await create_auth_user(pool)
    classroom_id = client_as(dana).post("/classrooms", json={"name": "AppSec 101"}).json()["id"]
    invite_token = client_as(dana).post(f"/classrooms/{classroom_id}/invites").json()["invite_token"]

    async def attempt(user_id):
        async with pool.acquire() as conn:
            return await consume_invite(conn, invite_token, user_id)

    results = await asyncio.gather(attempt(sam), attempt(mallory))
    assert sorted(r is not None for r in results) == [False, True]
