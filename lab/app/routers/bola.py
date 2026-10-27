"""API1 - BOLA challenge: vulnerable vs. hardened project read endpoints."""
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_lab_user
from app.db import get_pool

router = APIRouter(tags=["api1-bola"])


@router.get("/vulnerable/projects/{project_id}")
async def get_project_vulnerable(project_id: int, user: dict = Depends(get_current_lab_user)):
    """VULNERABLE: returns any project by ID with no ownership check at all.
    This is the bug: `project_id` from the URL is trusted as if it were an
    authorization decision."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "select id, owner_id, name, description from bola_projects where id = $1", project_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return dict(row)


@router.get("/hardened/projects/{project_id}")
async def get_project_hardened(project_id: int, user: dict = Depends(get_current_lab_user)):
    """HARDENED: loads the resource, then checks ownership before returning
    anything. A request for someone else's project yields 403, not data."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "select id, owner_id, name, description from bola_projects where id = $1", project_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if row["owner_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized to view this project")
    return dict(row)


@router.get("/vulnerable/me/projects")
@router.get("/hardened/me/projects")
async def my_projects(user: dict = Depends(get_current_lab_user)):
    pool = await get_pool()
    rows = await pool.fetch(
        "select id, owner_id, name, description from bola_projects where owner_id = $1",
        user["user_id"],
    )
    return [dict(r) for r in rows]
