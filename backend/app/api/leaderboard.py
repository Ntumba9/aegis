"""Public leaderboards, aggregated from `user_progress`.

Only `points_awarded` is summed, and that column is only ever non-zero for
`verification_mode = 'server_verified'` completions (see
app/api/challenges.py::submit_challenge) — a local/unverified submission
is recorded for the user's own history but contributes zero here, per the
project's anti-cheating requirement.
"""
from fastapi import APIRouter, Query

from app.db.session import get_pool
from app.schemas.leaderboard import LeaderboardEntry, TeamLeaderboardEntry

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/users", response_model=list[LeaderboardEntry])
async def user_leaderboard(limit: int = Query(50, ge=1, le=100)):
    pool = await get_pool()
    rows = await pool.fetch(
        """
        select
            p.user_id,
            pr.full_name as display_name,
            sum(p.points_awarded) as total_points,
            count(*) filter (where p.status = 'completed') as challenges_completed,
            rank() over (order by sum(p.points_awarded) desc) as rank
        from user_progress p
        left join profiles pr on pr.id = p.user_id
        where p.status = 'completed'
        group by p.user_id, pr.full_name
        order by total_points desc
        limit $1
        """,
        limit,
    )
    return [dict(r) for r in rows]


@router.get("/teams", response_model=list[TeamLeaderboardEntry])
async def team_leaderboard(limit: int = Query(50, ge=1, le=100)):
    pool = await get_pool()
    rows = await pool.fetch(
        """
        select
            t.id as team_id,
            t.name as team_name,
            coalesce(sum(p.points_awarded), 0) as total_points,
            count(distinct m.user_id) as members,
            rank() over (order by coalesce(sum(p.points_awarded), 0) desc) as rank
        from teams t
        join team_members m on m.team_id = t.id
        left join user_progress p on p.user_id = m.user_id and p.status = 'completed'
        group by t.id, t.name
        order by total_points desc
        limit $1
        """,
        limit,
    )
    return [dict(r) for r in rows]
