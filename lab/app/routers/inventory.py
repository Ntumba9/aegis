"""API9:2023 - Improper Inventory Management.

A "v1" export endpoint was supposed to be retired when "v2" shipped with
proper authentication and authorization, but it was never actually
removed or locked down — a classic shadow/zombie API. `/v1/internal/export`
requires nothing at all; `/v2/internal/export` requires a valid bearer AND
the admin role.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_lab_user
from app.db import get_pool

router = APIRouter(tags=["api9-inventory"])


@router.get("/v1/internal/export")
async def export_v1():
    """BUG: this legacy version was forgotten during the v2 rollout and
    carries none of v2's security controls — no auth check at all."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "select flag from challenge_flags where challenge_id = 'api9-inventory-shadow-v1-endpoint'"
    )
    return {"export": "full internal dataset", "flag": row["flag"] if row else None}


@router.get("/v2/internal/export")
async def export_v2(user: dict = Depends(get_current_lab_user)):
    pool = await get_pool()
    role_row = await pool.fetchrow("select role from lab_users where id = $1", user["user_id"])
    if role_row is None or role_row["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    flag_row = await pool.fetchrow(
        "select flag from challenge_flags where challenge_id = 'api9-inventory-shadow-v1-endpoint'"
    )
    return {"export": "full internal dataset", "flag": flag_row["flag"] if flag_row else None}
