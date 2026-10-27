from uuid import UUID

from app.db.session import get_pool


async def get_role_for_user(org_id: UUID, user_id: UUID) -> str | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "select role from memberships where org_id = $1 and user_id = $2",
        org_id,
        user_id,
    )
    return row["role"] if row else None
