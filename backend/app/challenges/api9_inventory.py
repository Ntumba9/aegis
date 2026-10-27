from app.challenges.base import ChallengeMetadata, VerificationContext, VerificationResult
from app.challenges.flag_verification import verify_against_flag_table

METADATA = ChallengeMetadata(
    id="api9-inventory-shadow-v1-endpoint",
    owasp_category="API9-INVENTORY",
    title="The v1 Endpoint Nobody Decommissioned",
    difficulty="beginner",
    summary=(
        "GET /v2/internal/export is properly locked down behind "
        "authentication and the admin role. GET /v1/internal/export does "
        "the exact same thing — and was never secured, or removed."
    ),
    learning_objectives=[
        "Understand why API inventory management is itself a security control",
        "See how 'deprecated' endpoints that are still deployed remain live attack surface",
        "Compare the same functionality across two API versions with very different security postures",
    ],
    prerequisites=[],
    authorized_scope="Your own local lab instance only (default http://localhost:8100).",
    required_services=["lab-api", "lab-db"],
    hints=[
        "Try GET /v2/internal/export with no Authorization header first.",
        "Now try GET /v1/internal/export the same way.",
        "An inventory of every live route — including old ones — is the actual fix here.",
    ],
    remediation_markdown=(
        "## Remediation\n\nMaintain an explicit, automatically verified "
        "inventory of every deployed API version and endpoint. When a "
        "version is superseded, decommission it — don't just stop "
        "documenting it. See `lab/app/routers/inventory.py`."
    ),
    points=100,
)


async def verify(ctx: VerificationContext, lab_db_url: str) -> VerificationResult:
    return await verify_against_flag_table(ctx, lab_db_url, METADATA.id)
