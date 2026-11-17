from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

SCOPE_NOTE = (
    "Evidence about the lab's reference implementation (its vulnerable and "
    "hardened endpoints), not proof that a team remediated anything. This "
    "does not change the report's remediation status."
)


class LabRunOut(BaseModel):
    id: UUID
    report_id: UUID
    challenge_id: str
    requested_by: UUID
    outcome: str  # passed | failed | error | unreachable
    tests: list[str]
    duration_ms: int
    summary: str
    started_at: datetime
    finished_at: datetime
    scope_note: str = SCOPE_NOTE
