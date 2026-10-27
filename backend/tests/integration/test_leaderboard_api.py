"""API-layer integration tests for /leaderboard. These insert directly
into user_progress (bypassing the challenge verification flow, which is
tested separately) to check the aggregation SQL itself: ranking, point
summation, and that only 'completed' rows count."""
import pytest

from tests.integration.conftest import create_auth_user
from tests.integration.helpers import client_as

pytestmark = pytest.mark.usefixtures("clean_db")


@pytest.mark.asyncio
async def test_leaderboard_ranks_by_total_points_descending(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    bob = await create_auth_user(pool)

    await pool.execute(
        "insert into user_progress (user_id, challenge_id, status, points_awarded, completed_at) "
        "values ($1, 'api1-bola-project-files', 'completed', 100, now()), "
        "($1, 'api7-ssrf-url-preview', 'completed', 150, now())",
        alice,
    )
    await pool.execute(
        "insert into user_progress (user_id, challenge_id, status, points_awarded, completed_at) "
        "values ($1, 'api1-bola-project-files', 'completed', 100, now())",
        bob,
    )

    board = client_as(alice).get("/leaderboard/users").json()
    assert board[0]["user_id"] == str(alice)
    assert board[0]["total_points"] == 250
    assert board[0]["challenges_completed"] == 2
    assert board[0]["rank"] == 1
    assert board[1]["user_id"] == str(bob)
    assert board[1]["rank"] == 2


@pytest.mark.asyncio
async def test_unverified_local_completions_contribute_zero_points(clean_db):
    """A local_unverified completion has points_awarded forced to 0 at
    write time (app/api/challenges.py), so it should never move the
    leaderboard — this checks the aggregation doesn't accidentally count
    it some other way (e.g. by row count instead of summed points)."""
    pool = clean_db
    mallory = await create_auth_user(pool)

    await pool.execute(
        "insert into user_progress (user_id, challenge_id, status, verification_mode, points_awarded, completed_at) "
        "values ($1, 'api1-bola-project-files', 'completed', 'local_unverified', 0, now())",
        mallory,
    )

    board = client_as(mallory).get("/leaderboard/users").json()
    assert board[0]["total_points"] == 0


@pytest.mark.asyncio
async def test_in_progress_rows_do_not_count_as_completed(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    await pool.execute(
        "insert into user_progress (user_id, challenge_id, status) values ($1, 'api3-bopla-role-escalation', 'in_progress')",
        alice,
    )

    board = client_as(alice).get("/leaderboard/users").json()
    assert board == []
