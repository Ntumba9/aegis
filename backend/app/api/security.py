"""Blue Team security operations: the event feed and aggregate metrics
every security-ops dashboard needs. Scoped per-organization (admin/owner
only) — there's no cross-tenant "platform admin" view, matching the rest
of the multi-tenant model.

Every number here comes from `request_logs` / `security_events`, written
by `app/middleware/security_logging.py` on every real request — nothing
on this page is a fabricated statistic.
"""
import json
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, RequireRole
from app.db.session import get_pool
from app.schemas.security import SecurityEventOut, SecurityMetrics

router = APIRouter(prefix="/orgs/{org_id}/security", tags=["security-ops"])


@router.get("/events", response_model=list[SecurityEventOut])
async def list_events(
    org_id: UUID,
    limit: int = 50,
    severity: str | None = None,
    user: CurrentUser = Depends(RequireRole("admin")),
):
    pool = await get_pool()
    if severity:
        rows = await pool.fetch(
            "select id, actor_id, event_type, severity, metadata, created_at "
            "from security_events where org_id = $1 and severity = $2 "
            "order by created_at desc limit $3",
            org_id,
            severity,
            limit,
        )
    else:
        rows = await pool.fetch(
            "select id, actor_id, event_type, severity, metadata, created_at "
            "from security_events where org_id = $1 order by created_at desc limit $2",
            org_id,
            limit,
        )
    out = []
    for r in rows:
        d = dict(r)
        d["metadata"] = json.loads(d["metadata"]) if isinstance(d["metadata"], str) else d["metadata"]
        out.append(d)
    return out


@router.get("/metrics", response_model=SecurityMetrics)
async def metrics(
    org_id: UUID,
    window_hours: int = 24,
    user: CurrentUser = Depends(RequireRole("admin")),
):
    pool = await get_pool()

    total_requests = await pool.fetchval(
        "select count(*) from request_logs where org_id = $1 and created_at > now() - make_interval(hours => $2)",
        org_id,
        window_hours,
    )

    status_rows = await pool.fetch(
        "select status_code, count(*) as c from request_logs "
        "where org_id = $1 and created_at > now() - make_interval(hours => $2) "
        "group by status_code",
        org_id,
        window_hours,
    )
    requests_by_status = {str(r["status_code"]): r["c"] for r in status_rows}

    async def _count(event_type: str) -> int:
        return await pool.fetchval(
            "select count(*) from security_events where org_id = $1 and event_type = $2 "
            "and created_at > now() - make_interval(hours => $3)",
            org_id,
            event_type,
            window_hours,
        )

    alerts = await pool.fetchval(
        "select count(*) from security_events where org_id = $1 and severity in ('high', 'critical') "
        "and created_at > now() - make_interval(hours => $2)",
        org_id,
        window_hours,
    )

    return SecurityMetrics(
        window_hours=window_hours,
        total_requests=total_requests or 0,
        auth_failures=await _count("auth_failure"),
        authorization_denials=await _count("authorization_denied"),
        rate_limit_violations=await _count("rate_limit_exceeded"),
        alerts=alerts or 0,
        requests_by_status=requests_by_status,
    )
