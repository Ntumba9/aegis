from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WebhookCreate(BaseModel):
    target_url: str = Field(min_length=1, max_length=2000)
    event_types: list[str] = Field(min_length=1)


class WebhookOut(BaseModel):
    id: UUID
    org_id: UUID
    target_url: str
    event_types: list[str]
    is_active: bool
    created_at: datetime


class WebhookCreated(WebhookOut):
    signing_secret: str  # returned exactly once, at creation time — never again


class WebhookDeliveryOut(BaseModel):
    id: UUID
    webhook_id: UUID
    event_type: str
    status: str
    attempt_count: int
    created_at: datetime
