"""API4:2023 - Unrestricted Resource Consumption.

The vulnerable export endpoint accepts a client-supplied `limit` with no
upper bound and no rate limiting, letting a single request pull the
entire synthetic dataset — including a sensitive record buried near the
end that should require pagination (and authorization) to ever reach in
practice. The hardened endpoint caps `limit` at 50 and throttles callers
to 5 requests/minute.
"""
import time

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_lab_user
from app.db import get_pool

router = APIRouter(tags=["api4-resource-consumption"])

_hardened_call_log: dict[str, list[float]] = {}


@router.get("/vulnerable/export")
async def export_vulnerable(limit: int = 50, user: dict = Depends(get_current_lab_user)):
    """BUG: `limit` is unbounded, and there is no rate limiting at all."""
    pool = await get_pool()
    rows = await pool.fetch("select id, payload from sensitive_records order by id limit $1", limit)
    return {"count": len(rows), "records": [dict(r) for r in rows]}


@router.get("/hardened/export")
async def export_hardened(limit: int = 50, user: dict = Depends(get_current_lab_user)):
    MAX_LIMIT = 50
    WINDOW_SECONDS = 60
    MAX_CALLS_PER_WINDOW = 5

    now = time.time()
    history = [t for t in _hardened_call_log.get(user["sub"], []) if now - t < WINDOW_SECONDS]
    if len(history) >= MAX_CALLS_PER_WINDOW:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    history.append(now)
    _hardened_call_log[user["sub"]] = history

    capped_limit = min(limit, MAX_LIMIT)
    pool = await get_pool()
    rows = await pool.fetch(
        "select id, payload from sensitive_records order by id limit $1", capped_limit
    )
    return {"count": len(rows), "records": [dict(r) for r in rows], "limit_applied": capped_limit}
