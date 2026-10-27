from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class OrgOut(BaseModel):
    id: UUID
    name: str
    created_at: datetime


class MemberOut(BaseModel):
    user_id: UUID
    org_id: UUID
    role: str
    created_at: datetime


class InviteCreate(BaseModel):
    email: EmailStr
    role: str = Field(default="employee", pattern="^(employee|admin)$")


class InviteOut(BaseModel):
    id: UUID
    org_id: UUID
    email: EmailStr
    role: str
    status: str
    created_at: datetime
