from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SecurityEventOut(BaseModel):
    id: UUID
    actor_id: UUID | None
    event_type: str
    severity: str
    metadata: dict
    created_at: datetime


class SecurityMetrics(BaseModel):
    window_hours: int
    total_requests: int
    auth_failures: int
    authorization_denials: int
    rate_limit_violations: int
    alerts: int  # high + critical severity events
    requests_by_status: dict[str, int]
