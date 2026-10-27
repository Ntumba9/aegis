from app.challenges.base import ChallengeMetadata, VerificationContext, VerificationResult
from app.challenges.flag_verification import verify_against_flag_table

METADATA = ChallengeMetadata(
    id="api5-bfla-admin-broadcast",
    owasp_category="API5-BFLA",
    title="Anyone Can Push the Big Red Button",
    difficulty="beginner",
    summary=(
        "POST /vulnerable/admin/broadcast is meant to be an admin-only "
        "action, but the handler only checks that you're logged in at "
        "all — not that you hold the admin role. Trigger it as a regular user."
    ),
    learning_objectives=[
        "Understand the difference between authentication and authorization",
        "See why every privileged function needs its own explicit role check",
        "Compare against a hardened handler that checks role before acting",
    ],
    prerequisites=[],
    authorized_scope="Your own local lab instance only (default http://localhost:8100).",
    required_services=["lab-api", "lab-db"],
    hints=[
        "Log in as any non-admin user (e.g. 'bob').",
        "POST to /vulnerable/admin/broadcast with your bearer token — no special role needed.",
        "Try the same request against /hardened/admin/broadcast and compare.",
    ],
    remediation_markdown=(
        "## Remediation\n\nEvery administrative function needs its own "
        "explicit function-level authorization check — being authenticated "
        "is not the same as being authorized for that specific action. See "
        "`lab/app/routers/bfla.py::broadcast_hardened`."
    ),
    points=100,
)


async def verify(ctx: VerificationContext, lab_db_url: str) -> VerificationResult:
    return await verify_against_flag_table(ctx, lab_db_url, METADATA.id)
