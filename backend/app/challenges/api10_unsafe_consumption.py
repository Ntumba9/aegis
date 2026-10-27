from app.challenges.base import ChallengeMetadata, VerificationContext, VerificationResult
from app.challenges.flag_verification import verify_against_flag_table

METADATA = ChallengeMetadata(
    id="api10-unsafe-consumption-pricing",
    owasp_category="API10-UNSAFE-CONSUMPTION",
    title="The Pricing Engine Trusts Its Supplier",
    difficulty="advanced",
    summary=(
        "POST /vulnerable/pricing/quote calls a 'third-party' discount "
        "service and applies whatever `discount_percent` it returns with "
        "no validation. Drive the discount past 100% and break the price."
    ),
    learning_objectives=[
        "Understand that calling a third-party/internal API is not inherently safe",
        "See how blind trust in an upstream response enables a client-reachable exploit",
        "Compare against a hardened consumer that validates and clamps the upstream value",
    ],
    prerequisites=["Challenge api7-ssrf-url-preview recommended first"],
    authorized_scope="Your own local lab instance only (default http://localhost:8100).",
    required_services=["lab-api", "lab-internal-mock"],
    hints=[
        "The request body lets you pick `discount_percent_requested` — where does it actually go?",
        "The 'third-party' service (lab-internal-mock) echoes back whatever discount it's asked for.",
        "What happens to final_price when the discount passed through exceeds 100?",
    ],
    remediation_markdown=(
        "## Remediation\n\nNever apply a value from an external or "
        "third-party API without validating it against your own business "
        "rules first — clamp, type-check, and bound every field before "
        "using it, regardless of how trusted the source seems. See "
        "`lab/app/routers/unsafe_consumption.py::pricing_quote_hardened`."
    ),
    points=200,
)


async def verify(ctx: VerificationContext, lab_db_url: str) -> VerificationResult:
    return await verify_against_flag_table(ctx, lab_db_url, METADATA.id)
