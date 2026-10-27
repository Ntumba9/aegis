from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.db.session import get_pool
from app.schemas.achievements import AchievementOut, EarnedAchievementOut

router = APIRouter(prefix="/achievements", tags=["achievements"])


@router.get("", response_model=list[AchievementOut])
async def list_achievements():
    pool = await get_pool()
    rows = await pool.fetch("select id, title, description, icon from achievements order by id")
    return [dict(r) for r in rows]


@router.get("/me", response_model=list[EarnedAchievementOut])
async def my_achievements(user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    rows = await pool.fetch(
        "select a.id as achievement_id, a.title, a.description, a.icon, ua.earned_at "
        "from user_achievements ua join achievements a on a.id = ua.achievement_id "
        "where ua.user_id = $1 order by ua.earned_at desc",
        user.id,
    )
    return [dict(r) for r in rows]
