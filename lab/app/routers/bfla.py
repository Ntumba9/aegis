"""API5:2023 - Broken Function Level Authorization.

The vulnerable endpoint implements an administrative action (broadcasting
an announcement to every tenant) but never checks that the caller is
actually an administrator — only that they are logged in at all. The
hardened endpoint checks `lab_users.role` before doing anything.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_lab_user
from app.db import get_pool

router = APIRouter(tags=["api5-bfla"])


@router.post("/vulnerable/admin/broadcast")
async def broadcast_vulnerable(user: dict = Depends(get_current_lab_user)):
    """BUG: any authenticated user can trigger an admin-only function —
    there is no role/permission check here at all, just `Depends(get_current_lab_user)`."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "select flag from challenge_flags where challenge_id = 'api5-bfla-admin-broadcast'"
    )
    return {
        "status": "broadcast sent to all tenants",
        "triggered_by": user["sub"],
        "flag": row["flag"] if row else None,
    }


@router.post("/hardened/admin/broadcast")
async def broadcast_hardened(user: dict = Depends(get_current_lab_user)):
    pool = await get_pool()
    role_row = await pool.fetchrow("select role from lab_users where id = $1", user["user_id"])
    if role_row is None or role_row["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin function, admin-only")
    flag_row = await pool.fetchrow(
        "select flag from challenge_flags where challenge_id = 'api5-bfla-admin-broadcast'"
    )
    return {
        "status": "broadcast sent to all tenants",
        "triggered_by": user["sub"],
        "flag": flag_row["flag"] if flag_row else None,
    }
