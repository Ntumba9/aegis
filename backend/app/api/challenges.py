"""Public challenge catalog + server-side verification.

Server-verified completion requires the backend to reach the lab directly
(same-host dev stack with `lab_database_url` configured). Otherwise a
submission is accepted as `local_cli` evidence and recorded, but marked
`local_unverified` and awarded zero leaderboard points — per the
requirement to never award trusted points from client-controlled local
Docker results alone.
"""
from fastapi import APIRouter, HTTPException

from app.challenges.base import VerificationContext
from app.challenges.registry import all_metadata, get_challenge_module
from app.core.auth import CurrentUser, get_current_user
from app.core.config import settings
from app.db.session import get_pool
from app.schemas.challenges import ChallengeOut, ProgressOut, SubmissionRequest, SubmissionResult
from app.services.achievements import evaluate_after_completion
from app.services.rate_limit import check_rate_limit
from fastapi import Depends

router = APIRouter(prefix="/challenges", tags=["challenges"])


@router.get("", response_model=list[ChallengeOut])
async def list_challenges():
    return [m.__dict__ for m in all_metadata()]


@router.get("/{challenge_id}", response_model=ChallengeOut)
async def get_challenge(challenge_id: str):
    module = get_challenge_module(challenge_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return module.METADATA.__dict__


@router.get("/progress/me", response_model=list[ProgressOut])
async def my_progress(user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    rows = await pool.fetch(
        "select challenge_id, status, verification_mode, points_awarded, completed_at "
        "from user_progress where user_id = $1",
        user.id,
    )
    return [dict(r) for r in rows]


@router.post("/{challenge_id}/submit", response_model=SubmissionResult)
async def submit_challenge(
    challenge_id: str,
    body: SubmissionRequest,
    user: CurrentUser = Depends(get_current_user),
):
    module = get_challenge_module(challenge_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Challenge not found")

    allowed = await check_rate_limit(
        key=f"verify:{user.id}:{challenge_id}",
        max_requests=settings.verification_rate_limit_per_minute,
        window_seconds=60,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many verification attempts, slow down")

    server_reachable = bool(settings.lab_database_url)
    pool = await get_pool()

    if server_reachable:
        ctx = VerificationContext(
            user_id=user.id, lab_base_url=body.lab_base_url, submitted_evidence=body.evidence
        )
        result = await module.verify(ctx, settings.lab_database_url)
        verification_mode = "server_verified"
        points = module.METADATA.points if result.passed else 0
    else:
        # No network path to a lab database from this deployment: we cannot
        # independently confirm the exploit happened, so we record the
        # attempt but never grant trusted points for it.
        result_passed = bool(body.evidence)
        verification_mode = "local_unverified"
        points = 0
        from app.challenges.base import VerificationResult

        result = VerificationResult(
            passed=result_passed,
            evidence_summary="Recorded as unverified: no server-side lab connection configured",
        )

    await pool.execute(
        "insert into verification_attempts (user_id, challenge_id, outcome, evidence_summary, verified_by) "
        "values ($1, $2, $3, $4, $5)",
        user.id,
        challenge_id,
        "passed" if result.passed else "failed",
        result.evidence_summary,
        "server" if server_reachable else "local_cli",
    )

    newly_granted_achievements: list[str] = []
    if result.passed:
        await pool.execute(
            "insert into user_progress (user_id, challenge_id, status, verification_mode, points_awarded, completed_at) "
            "values ($1, $2, 'completed', $3, $4, now()) "
            "on conflict (user_id, challenge_id) do update set "
            "status = 'completed', verification_mode = excluded.verification_mode, "
            "points_awarded = excluded.points_awarded, completed_at = now()",
            user.id,
            challenge_id,
            verification_mode,
            points,
        )
        newly_granted_achievements = await evaluate_after_completion(user.id)

    return SubmissionResult(
        passed=result.passed,
        evidence_summary=result.evidence_summary,
        verification_mode=verification_mode,
        points_awarded=points,
        newly_granted_achievements=newly_granted_achievements,
    )


@router.post("/{challenge_id}/reset", status_code=204)
async def reset_challenge(challenge_id: str, user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    await pool.execute(
        "update user_progress set status = 'reset', completed_at = null, points_awarded = 0 "
        "where user_id = $1 and challenge_id = $2",
        user.id,
        challenge_id,
    )
