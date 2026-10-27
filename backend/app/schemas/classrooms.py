from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ClassroomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ClassroomOut(BaseModel):
    id: UUID
    name: str
    instructor_id: UUID
    created_at: datetime


class StudentOut(BaseModel):
    classroom_id: UUID
    student_id: UUID
    joined_at: datetime


class AssignmentCreate(BaseModel):
    challenge_id: str
    due_at: datetime | None = None


class AssignmentOut(BaseModel):
    id: UUID
    classroom_id: UUID
    challenge_id: str
    due_at: datetime | None
    created_at: datetime


class StudentProgressOut(BaseModel):
    student_id: UUID
    challenge_id: str
    status: str
    points_awarded: int
    completed_at: datetime | None
