"""Structured audit logging. Every security-relevant event (auth, role
changes, API key lifecycle, security test runs) is written here, never to
an ad-hoc text log, so the Blue Team dashboard reads from one source."""
import json
from datetime import datetime, timezone
from uuid import UUID

from app.db.session import get_pool


async def record_event(
    *,
    org_id: UUID | None,
    actor_id: UUID | None,
    event_type: str,
    severity: str = "info",
    metadata: dict | None = None,
) -> None:
    pool = await get_pool()
    await pool.execute(
        "insert into security_events (org_id, actor_id, event_type, severity, metadata, created_at) "
        "values ($1, $2, $3, $4, $5, $6)",
        org_id,
        actor_id,
        event_type,
        severity,
        json.dumps(metadata or {}),
        datetime.now(timezone.utc),
    )
