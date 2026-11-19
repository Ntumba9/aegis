"""Blue Team security operations: the event feed and aggregate metrics
every security-ops dashboard needs. Scoped per-organization (admin/owner
only) — there's no cross-tenant "platform admin" view, matching the rest
of the multi-tenant model.

Every number here comes from `request_logs` / `security_events`, written
by `app/middleware/security_logging.py` on every real request — nothing
on this page is a fabricated statistic.
"""
import csv
import io
import json
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.core.auth import ApiKeyPrincipal, CurrentUser, RequireReadAccess
from app.db.session import get_pool
from app.schemas.security import SecurityEventOut, SecurityMetrics

router = APIRouter(prefix="/orgs/{org_id}/security", tags=["security-ops"])


@router.get("/events", response_model=list[SecurityEventOut])
async def list_events(
    org_id: UUID,
    limit: int = 50,
    severity: str | None = None,
    principal: CurrentUser | ApiKeyPrincipal = Depends(RequireReadAccess("admin")),
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
    principal: CurrentUser | ApiKeyPrincipal = Depends(RequireReadAccess("admin")),
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



@router.get("/events/export")
async def export_events(
    org_id: UUID,
    severity: str | None = None,
    limit: int = 1000,
    principal: CurrentUser | ApiKeyPrincipal = Depends(RequireReadAccess("admin")),
):
    """The same security-event feed as GET /events, as a CSV download for
    offline review. Same identity rules (admin/owner JWT, or an org API key
    with the read scope), same filters, capped at 5000 rows per export."""
    limit = max(1, min(limit, 5000))
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

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "created_at", "event_type", "severity", "actor_id", "metadata"])
    for r in rows:
        metadata = r["metadata"]
        if not isinstance(metadata, str):
            metadata = json.dumps(metadata)
        writer.writerow(
            [
                str(r["id"]),
                r["created_at"].isoformat(),
                r["event_type"],
                r["severity"],
                str(r["actor_id"]) if r["actor_id"] else "",
                metadata,
            ]
        )

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="aegis-security-events-{org_id}.csv"'
        },
    )
