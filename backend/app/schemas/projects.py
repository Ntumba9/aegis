from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class ProjectOut(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    description: str | None
    created_at: datetime


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    assignee_id: UUID | None = None
    status: str = Field(default="todo", pattern="^(todo|in_progress|done)$")


class TaskOut(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    description: str | None
    assignee_id: UUID | None
    status: str
    created_at: datetime


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    assignee_id: UUID | None = None
    status: str | None = Field(default=None, pattern="^(todo|in_progress|done)$")
