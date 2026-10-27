from app.challenges.base import ChallengeMetadata, VerificationContext, VerificationResult
from app.challenges.flag_verification import verify_against_flag_table

METADATA = ChallengeMetadata(
    id="api3-bopla-role-escalation",
    owasp_category="API3-BOPLA",
    title="Patch Yourself Into Admin",
    difficulty="intermediate",
    summary=(
        "The vulnerable profile-update endpoint accepts and writes ANY "
        "field in the request body, including `role`. Escalate your own "
        "account from 'user' to 'admin' and read the admin-only flag."
    ),
    learning_objectives=[
        "Understand mass-assignment vulnerabilities",
        "Practice reading an API response to find undocumented but writable fields",
        "Compare against a hardened handler using an explicit field allowlist",
    ],
    prerequisites=["Basic REST/JSON familiarity"],
    authorized_scope="Your own local lab instance only (default http://localhost:8100).",
    required_services=["lab-api", "lab-db"],
    hints=[
        "Log in as 'dave' and GET your own user object — note every field it returns.",
        "PATCH /vulnerable/users/{your_id} with a JSON body containing a field you were never given a form for.",
        "Once role=admin, call GET /vulnerable/admin/flag.",
    ],
    remediation_markdown=(
        "## Remediation\n\nNever deserialize a client-supplied body directly "
        "into a persisted model. Define an explicit allowlist of "
        "client-settable fields (a separate 'update' schema) and ignore "
        "everything else — see `lab/app/routers/bopla.py::HardenedPatch`."
    ),
    points=150,
)


async def verify(ctx: VerificationContext, lab_db_url: str) -> VerificationResult:
    return await verify_against_flag_table(ctx, lab_db_url, METADATA.id)
