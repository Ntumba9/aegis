from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ChallengeOut(BaseModel):
    id: str
    owasp_category: str
    title: str
    difficulty: str
    summary: str
    learning_objectives: list[str]
    prerequisites: list[str]
    authorized_scope: str
    required_services: list[str]
    hints: list[str]
    points: int


class SubmissionRequest(BaseModel):
    lab_base_url: str = "http://localhost:8100"
    evidence: dict[str, Any] = {}


class SubmissionResult(BaseModel):
    passed: bool
    evidence_summary: str
    verification_mode: str
    points_awarded: int
    newly_granted_achievements: list[str] = []


class ProgressOut(BaseModel):
    challenge_id: str
    status: str
    verification_mode: str | None
    points_awarded: int
    completed_at: datetime | None
