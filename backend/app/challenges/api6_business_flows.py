from app.challenges.base import ChallengeMetadata, VerificationContext, VerificationResult
from app.challenges.flag_verification import verify_against_flag_table

METADATA = ChallengeMetadata(
    id="api6-sensitive-flows-coupon-replay",
    owasp_category="API6-SENSITIVE-FLOWS",
    title="This Coupon Works Every Time",
    difficulty="beginner",
    summary=(
        "POST /vulnerable/coupons/redeem credits your wallet every single "
        "time it's called with the same code — there's no single-use "
        "enforcement. Replay it until your balance crosses 100 and claim the flag."
    ),
    learning_objectives=[
        "Understand business-logic abuse vs. traditional injection/auth bugs",
        "See why 'this action should only happen once' needs its own server-side check",
        "Compare against a hardened endpoint enforcing single-use-per-user",
    ],
    prerequisites=[],
    authorized_scope="Your own local lab instance only (default http://localhost:8100).",
    required_services=["lab-api", "lab-db"],
    hints=[
        "POST /vulnerable/coupons/redeem {\"code\": \"WELCOME10\"} repeatedly — same code, same result?",
        "Each redemption adds 10 to your wallet. GET /vulnerable/wallet/flag needs balance >= 100.",
        "Try the identical replay against /hardened/coupons/redeem.",
    ],
    remediation_markdown=(
        "## Remediation\n\nEnforce single-use business rules at the "
        "database layer with a unique constraint (here, on `(username, "
        "code)`), not just in application logic that can be raced or "
        "simply never checked — see `lab/app/routers/business_flows.py::redeem_hardened`."
    ),
    points=150,
)


async def verify(ctx: VerificationContext, lab_db_url: str) -> VerificationResult:
    return await verify_against_flag_table(ctx, lab_db_url, METADATA.id)
