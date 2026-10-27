from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(default_factory=lambda: ["read"])


class ApiKeyCreated(BaseModel):
    id: UUID
    name: str
    scopes: list[str]
    plaintext_key: str  # returned exactly once, at creation time
    created_at: datetime


class ApiKeyOut(BaseModel):
    id: UUID
    name: str
    scopes: list[str]
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
