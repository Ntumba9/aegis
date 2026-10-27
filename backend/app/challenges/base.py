"""Challenge module contract.

Each OWASP challenge is a Python module exposing:
  - METADATA: the public catalog entry (synced into the `challenges` table
    by scripts/seed_challenges.py) — descriptions, objectives, hints,
    remediation. Nothing here is secret.
  - async def verify(ctx: VerificationContext) -> VerificationResult

`verify()` is the ONLY place that decides whether a challenge is complete.
It never trusts a client-submitted boolean; it re-derives the outcome by
calling the lab target itself with credentials/identities the backend
controls, or by inspecting state the lab exposes for grading only.
"""
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class ChallengeMetadata:
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
    remediation_markdown: str
    points: int = 100


@dataclass
class VerificationContext:
    user_id: UUID
    lab_base_url: str  # user's local lab instance, e.g. http://localhost:8100
    submitted_evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    passed: bool
    evidence_summary: str
