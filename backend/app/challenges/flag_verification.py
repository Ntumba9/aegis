"""Shared helper for the challenges that use the generic `challenge_flags`
lab table: the user submits a flag string, we independently read the
expected value from the (isolated, synthetic) lab database and compare."""
import asyncpg

from app.challenges.base import VerificationContext, VerificationResult


async def verify_against_flag_table(ctx: VerificationContext, lab_db_url: str, challenge_id: str) -> VerificationResult:
    submitted = (ctx.submitted_evidence or {}).get("flag", "").strip()
    if not submitted:
        return VerificationResult(passed=False, evidence_summary="No flag submitted")

    conn = await asyncpg.connect(lab_db_url)
    try:
        row = await conn.fetchrow(
            "select flag from challenge_flags where challenge_id = $1", challenge_id
        )
    finally:
        await conn.close()

    if row is None:
        return VerificationResult(passed=False, evidence_summary="Lab not seeded")

    passed = submitted == row["flag"]
    return VerificationResult(passed=passed, evidence_summary="Flag matched" if passed else "Flag did not match")
