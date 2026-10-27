"""Integration test for the achievement-awarding service against a real
database — proves achievements are only granted through
app.services.achievements, never by a client writing to user_achievements
directly (which RLS has no INSERT policy for at all; see
0005_challenge_platform_rls.sql)."""
import pytest

from app.services.achievements import FIRST_BLOOD, evaluate_after_completion
from tests.integration.conftest import AsUser, create_auth_user

pytestmark = pytest.mark.usefixtures("clean_db")


@pytest.mark.asyncio
async def test_first_blood_awarded_on_first_completion(clean_db, monkeypatch):
    pool = clean_db
    user_id = await create_auth_user(pool)
    await pool.execute(
        "insert into achievements (id, title, description, icon) values "
        "('first-blood', 'First Blood', 'Completed your first challenge.', 'flag')"
    )

    monkeypatch.setattr("app.services.achievements.get_pool", lambda: _fake_pool(pool))

    await pool.execute(
        "insert into user_progress (user_id, challenge_id, status, points_awarded, completed_at) "
        "values ($1, 'api1-bola-project-files', 'completed', 100, now())",
        user_id,
    )

    granted = await evaluate_after_completion(user_id)
    assert FIRST_BLOOD in granted

    row = await pool.fetchrow(
        "select 1 from user_achievements where user_id = $1 and achievement_id = $2",
        user_id,
        FIRST_BLOOD,
    )
    assert row is not None


@pytest.mark.asyncio
async def test_client_cannot_write_achievements_directly(clean_db):
    """No RLS policy grants INSERT on user_achievements to the
    authenticated role at all — only the backend's own service-role
    connection (which bypasses RLS entirely) can write here."""
    pool = clean_db
    user_id = await create_auth_user(pool)
    await pool.execute(
        "insert into achievements (id, title, description, icon) values "
        "('first-blood', 'First Blood', 'Completed your first challenge.', 'flag')"
    )

    as_user = AsUser(pool, user_id)
    with pytest.raises(Exception):
        await as_user.execute(
            "insert into user_achievements (user_id, achievement_id) values ($1, 'first-blood')",
            user_id,
        )


async def _fake_pool(pool):
    return pool
