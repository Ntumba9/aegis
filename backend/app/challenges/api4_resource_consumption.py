from app.challenges.base import ChallengeMetadata, VerificationContext, VerificationResult
from app.challenges.flag_verification import verify_against_flag_table

METADATA = ChallengeMetadata(
    id="api4-resource-consumption-pagination",
    owasp_category="API4-RESOURCE-CONSUMPTION",
    title="Nobody Capped the Limit",
    difficulty="beginner",
    summary=(
        "GET /vulnerable/export accepts a `limit` query parameter with no "
        "upper bound and no rate limiting. A dataset of 500 harmless "
        "records hides one sensitive record at the very end — pull it in "
        "a single oversized request."
    ),
    learning_objectives=[
        "Understand why pagination limits are a security control, not just a UX nicety",
        "See how unbounded limit= parameters enable data exfiltration and resource exhaustion",
        "Compare against a hardened endpoint that caps limit and rate-limits callers",
    ],
    prerequisites=[],
    authorized_scope="Your own local lab instance only (default http://localhost:8100).",
    required_services=["lab-api", "lab-db"],
    hints=[
        "GET /vulnerable/export?limit=50 is the default — what happens if you ask for more?",
        "There are exactly 501 records seeded. The flag is the last one.",
        "GET /hardened/export?limit=1000 behaves very differently.",
    ],
    remediation_markdown=(
        "## Remediation\n\nAlways enforce a server-side maximum page size "
        "regardless of what the client requests, and rate-limit list/export "
        "endpoints per caller — see `lab/app/routers/resource_consumption.py::export_hardened`."
    ),
    points=100,
)


async def verify(ctx: VerificationContext, lab_db_url: str) -> VerificationResult:
    return await verify_against_flag_table(ctx, lab_db_url, METADATA.id)
