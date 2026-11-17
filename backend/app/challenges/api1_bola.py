"""API1:2023 - Broken Object Level Authorization.

The lab seeds a "victim" project (`lab/scripts/seed.py`) containing a
unique flag in its description. The vulnerable endpoint
`GET /vulnerable/projects/{id}` returns ANY project to ANY authenticated
lab user, regardless of ownership. The hardened endpoint
`GET /hardened/projects/{id}` checks `owner_id` server-side and returns 403.

Verification never trusts a client-submitted boolean. The user submits the
flag string they recovered; the backend independently re-reads the
expected flag from the lab's database (a synthetic, local-only instance)
and compares.
"""
import asyncpg

from app.challenges.base import ChallengeMetadata, VerificationContext, VerificationResult

METADATA = ChallengeMetadata(
    id="api1-bola-project-files",
    owasp_category="API1-BOLA",
    title="Peeking Into Someone Else's Project",
    difficulty="beginner",
    summary=(
        "The project API trusts the `project_id` in the URL without checking "
        "that the caller actually owns it. Retrieve the flag stored in a "
        "victim project you were never given access to."
    ),
    learning_objectives=[
        "Understand why object IDs must never double as an authorization check",
        "Practice enumerating/guessing object identifiers",
        "Compare a vulnerable endpoint to its ownership-checked hardened twin",
    ],
    prerequisites=["Basic HTTP/REST familiarity", "A REST client (curl, httpie, Postman)"],
    authorized_scope=(
        "You are authorized to test ONLY the lab instance running on your own "
        "machine at http://localhost:8100 (bound to 127.0.0.1 only). "
        "Testing any other host is out of scope."
    ),
    required_services=["lab-api", "lab-db"],
    hints=[
        "Log in as the seeded user `alice` and list your own projects first — note the ID format.",
        "Project IDs are sequential integers in the vulnerable mode. Try adjacent IDs.",
        "Compare the response from /vulnerable/projects/{id} against /hardened/projects/{id}.",
    ],
    remediation_markdown=(
        "## Remediation\n\n"
        "Never authorize a request based solely on a client-supplied object ID. "
        "The hardened handler loads the resource, then checks "
        "`resource.owner_id == current_user.id` (or org membership for "
        "multi-tenant resources) before returning any data — see "
        "`lab/challenges/api1_bola/hardened.py`. Pair this with Postgres RLS "
        "as a second line of defense."
    ),
    points=100,
)


async def verify(ctx: VerificationContext, lab_db_url: str) -> VerificationResult:
    submitted_flag = (ctx.submitted_evidence or {}).get("flag", "").strip()
    if not submitted_flag:
        return VerificationResult(passed=False, evidence_summary="No flag submitted")

    conn = await asyncpg.connect(lab_db_url)
    try:
        row = await conn.fetchrow(
            "select flag from bola_victim_projects where challenge_id = $1 limit 1",
            METADATA.id,
        )
    finally:
        await conn.close()

    if row is None:
        return VerificationResult(passed=False, evidence_summary="Lab not seeded")

    passed = submitted_flag == row["flag"]
    return VerificationResult(
        passed=passed,
        evidence_summary="Flag matched victim project" if passed else "Flag did not match",
    )
