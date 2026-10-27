from app.challenges.base import ChallengeMetadata, VerificationContext, VerificationResult
from app.challenges.flag_verification import verify_against_flag_table

METADATA = ChallengeMetadata(
    id="api2-broken-auth-predictable-session",
    owasp_category="API2-BROKEN-AUTH",
    title="The Session Token That Counts Up",
    difficulty="beginner",
    summary=(
        "The vulnerable login flow issues sequential session tokens "
        "(sess-000001, sess-000002, ...) and lets anyone who holds a token "
        "string read that session — no bearer header required. Recover the "
        "administrator's flag by guessing her earlier, lower-numbered session."
    ),
    learning_objectives=[
        "See why session identifiers must be unguessable, not just unique",
        "Understand why 'knowing the token' is not the same as 'being authorized'",
        "Compare against a hardened flow that requires bearer + ownership checks",
    ],
    prerequisites=["Challenge api1-bola-project-files recommended first"],
    authorized_scope="Your own local lab instance only (default http://localhost:8100).",
    required_services=["lab-api", "lab-db"],
    hints=[
        "Log in via POST /vulnerable/sessions/login and note the token format.",
        "The administrator 'erin' logged in before you — try an earlier counter value.",
        "GET /vulnerable/sessions/{token}/flag needs no Authorization header at all.",
    ],
    remediation_markdown=(
        "## Remediation\n\nIssue session tokens with at least 128 bits of "
        "cryptographically secure randomness (`secrets.token_urlsafe`), and "
        "require the caller to present their own valid credentials matching "
        "the session's owner before returning anything — see "
        "`lab/app/routers/broken_auth.py::hardened_read_session`."
    ),
    points=100,
)


async def verify(ctx: VerificationContext, lab_db_url: str) -> VerificationResult:
    return await verify_against_flag_table(ctx, lab_db_url, METADATA.id)
