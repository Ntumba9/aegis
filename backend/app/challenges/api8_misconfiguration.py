from app.challenges.base import ChallengeMetadata, VerificationContext, VerificationResult
from app.challenges.flag_verification import verify_against_flag_table

METADATA = ChallengeMetadata(
    id="api8-misconfiguration-verbose-errors",
    owasp_category="API8-MISCONFIGURATION",
    title="The Stack Trace Said Too Much",
    difficulty="beginner",
    summary=(
        "GET /vulnerable/items/{item_id} crashes on non-numeric input and "
        "returns a debug-style error body — including an internal secret "
        "that was never supposed to leave the server."
    ),
    learning_objectives=[
        "Understand why verbose/debug error responses are a real security risk",
        "Practice triggering an unhandled exception with malformed input",
        "Compare against a hardened handler that validates input and returns a generic error",
    ],
    prerequisites=[],
    authorized_scope="Your own local lab instance only (default http://localhost:8100).",
    required_services=["lab-api"],
    hints=[
        "/vulnerable/items/42 works fine. What about /vulnerable/items/not-a-number?",
        "Read the full JSON error body, not just the status code.",
        "Try the same malformed request against /hardened/items/{item_id}.",
    ],
    remediation_markdown=(
        "## Remediation\n\nValidate input before it reaches business logic "
        "(path converters, Pydantic types), and ensure unhandled exceptions "
        "are caught by a generic error handler that never serializes "
        "internal state to the client — see "
        "`lab/app/routers/misconfiguration.py::get_item_hardened`."
    ),
    points=100,
)


async def verify(ctx: VerificationContext, lab_db_url: str) -> VerificationResult:
    return await verify_against_flag_table(ctx, lab_db_url, METADATA.id)
