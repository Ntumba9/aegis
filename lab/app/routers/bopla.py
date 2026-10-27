"""API3:2023 - Broken Object Property Level Authorization.

The vulnerable PATCH handler merges the ENTIRE client-supplied JSON body
into the user row, including `role` — a classic mass-assignment bug that
lets any user grant themselves administrator privileges. The hardened
handler only accepts an explicit allowlist of client-settable fields.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_lab_user
from app.db import get_pool

router = APIRouter(tags=["api3-bopla"])


class VulnerablePatch(BaseModel):
    class Config:
        extra = "allow"  # accept any field, including `role` — that's the bug


class HardenedPatch(BaseModel):
    display_name: str | None = None  # the ONLY field a user may change about themselves


@router.patch("/vulnerable/users/{user_id}")
async def patch_user_vulnerable(
    user_id: int, body: VulnerablePatch, user: dict = Depends(get_current_lab_user)
):
    if user_id != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your own user object")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    pool = await get_pool()
    if "role" in updates and updates["role"] not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role")
    # BUG: any field the client sends, including `role`, is written straight
    # through with no allowlist.
    if "role" in updates:
        await pool.execute("update lab_users set role = $1 where id = $2", updates["role"], user_id)
    if "display_name" in updates:
        await pool.execute(
            "update lab_users set display_name = $1 where id = $2", updates["display_name"], user_id
        )
    row = await pool.fetchrow("select id, username, role from lab_users where id = $1", user_id)
    return dict(row)


@router.patch("/hardened/users/{user_id}")
async def patch_user_hardened(
    user_id: int, body: HardenedPatch, user: dict = Depends(get_current_lab_user)
):
    if user_id != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your own user object")
    pool = await get_pool()
    if body.display_name is not None:
        await pool.execute(
            "update lab_users set display_name = $1 where id = $2", body.display_name, user_id
        )
    row = await pool.fetchrow("select id, username, role from lab_users where id = $1", user_id)
    return dict(row)


async def _get_role(user_id: int) -> str | None:
    pool = await get_pool()
    row = await pool.fetchrow("select role from lab_users where id = $1", user_id)
    return row["role"] if row else None


@router.get("/vulnerable/admin/flag")
async def admin_flag_vulnerable(user: dict = Depends(get_current_lab_user)):
    if await _get_role(user["user_id"]) != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    pool = await get_pool()
    row = await pool.fetchrow(
        "select flag from challenge_flags where challenge_id = 'api3-bopla-role-escalation'"
    )
    return {"flag": row["flag"] if row else None}


@router.get("/hardened/admin/flag")
async def admin_flag_hardened(user: dict = Depends(get_current_lab_user)):
    if await _get_role(user["user_id"]) != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    pool = await get_pool()
    row = await pool.fetchrow(
        "select flag from challenge_flags where challenge_id = 'api3-bopla-role-escalation'"
    )
    return {"flag": row["flag"] if row else None}
