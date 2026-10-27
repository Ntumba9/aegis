from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    mode: str = Field(default="mixed", pattern="^(red|blue|mixed)$")


class TeamOut(BaseModel):
    id: UUID
    name: str
    mode: str
    created_by: UUID
    created_at: datetime


class TeamMemberOut(BaseModel):
    team_id: UUID
    user_id: UUID
    role: str
    joined_at: datetime


class TeamSessionCreate(BaseModel):
    challenge_id: str
    mode: str = Field(pattern="^(attack|defense)$")


class TeamSessionOut(BaseModel):
    id: UUID
    team_id: UUID
    challenge_id: str
    mode: str
    started_at: datetime
    ended_at: datetime | None


class VulnReportCreate(BaseModel):
    challenge_id: str
    title: str = Field(min_length=1, max_length=200)
    severity: str = Field(pattern="^(low|medium|high|critical)$")
    description: str = Field(min_length=1, max_length=5000)
    team_id: UUID | None = None


class VulnReportOut(BaseModel):
    id: UUID
    team_id: UUID | None
    reporter_id: UUID
    challenge_id: str
    title: str
    severity: str
    description: str
    remediation_status: str
    assignee_id: UUID | None
    created_at: datetime


class VulnReportAssign(BaseModel):
    assignee_id: UUID
    remediation_status: str = Field(default="in_progress", pattern="^(open|in_progress|fixed|wont_fix)$")


class RetestCreate(BaseModel):
    result: str = Field(pattern="^(still_vulnerable|fixed)$")
    notes: str | None = Field(default=None, max_length=2000)


class RetestOut(BaseModel):
    id: UUID
    report_id: UUID
    tester_id: UUID
    result: str
    notes: str | None
    created_at: datetime
