"""Achievement rules. Called only from the server-side verification path
(app/api/challenges.py), never from a client-reachable endpoint directly —
so an achievement can't be granted without an actual completed+server-verified
challenge behind it.
"""
from uuid import UUID

from app.challenges.registry import all_metadata
from app.db.session import get_pool

FIRST_BLOOD = "first-blood"
API_TOP_10_GRADUATE = "api-top-10-graduate"
RED_TEAM_ROOKIE = "red-team-rookie"


async def _award(pool, user_id: UUID, achievement_id: str) -> None:
    await pool.execute(
        "insert into user_achievements (user_id, achievement_id) values ($1, $2) "
        "on conflict (user_id, achievement_id) do nothing",
        user_id,
        achievement_id,
    )


async def evaluate_after_completion(user_id: UUID) -> list[str]:
    """Runs after a challenge is marked completed for `user_id`. Returns the
    ids of any newly-granted achievements."""
    pool = await get_pool()
    newly_granted: list[str] = []

    completed_count = await pool.fetchval(
        "select count(*) from user_progress where user_id = $1 and status = 'completed'",
        user_id,
    )

    if completed_count == 1:
        await _award(pool, user_id, FIRST_BLOOD)
        newly_granted.append(FIRST_BLOOD)

    total_challenges = len(all_metadata())
    if completed_count >= total_challenges:
        await _award(pool, user_id, API_TOP_10_GRADUATE)
        newly_granted.append(API_TOP_10_GRADUATE)

    return newly_granted


async def evaluate_after_team_session(user_id: UUID, mode: str) -> list[str]:
    """Runs after a team session is started. Awards RED_TEAM_ROOKIE the
    first time a user participates in an 'attack'-mode session."""
    if mode != "attack":
        return []
    pool = await get_pool()
    already = await pool.fetchrow(
        "select 1 from user_achievements where user_id = $1 and achievement_id = $2",
        user_id,
        RED_TEAM_ROOKIE,
    )
    if already is not None:
        return []
    await _award(pool, user_id, RED_TEAM_ROOKIE)
    return [RED_TEAM_ROOKIE]
