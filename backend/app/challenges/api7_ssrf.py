"""API7:2023 - Server Side Request Forgery.

The vulnerable endpoint `POST /vulnerable/url-preview {"url": "..."}` fetches
whatever URL it is given and returns the response body — including
`http://lab-internal-mock:9000/*`, an internal-only mock metadata service
that only exists on the isolated `lab-net` Docker network. The hardened
endpoint validates the destination against an allowlist, blocks
redirects to private/link-local ranges, and enforces a timeout.

Success condition: retrieve the synthetic secret exposed by the internal
mock service's `/latest/internal-secret` path and submit it.
"""
import asyncpg

from app.challenges.base import ChallengeMetadata, VerificationContext, VerificationResult

METADATA = ChallengeMetadata(
    id="api7-ssrf-url-preview",
    owasp_category="API7-SSRF",
    title="The URL Preview That Trusted Too Much",
    difficulty="intermediate",
    summary=(
        "A 'link preview' feature fetches any URL a user supplies. Use it to "
        "reach an internal-only mock service that should never be reachable "
        "from outside the lab network, and recover its synthetic secret."
    ),
    learning_objectives=[
        "Understand the trust-boundary failure behind SSRF",
        "Learn why egress filtering and destination allowlists matter",
        "See how redirect-following can bypass naive hostname checks",
    ],
    prerequisites=["Basic HTTP familiarity", "Challenge api1-bola-project-files recommended first"],
    authorized_scope=(
        "Test ONLY your local lab instance (default http://localhost:8100). "
        "The internal mock service is intentionally unreachable from outside "
        "`lab-net` — do not attempt to reach real external hosts through it."
    ),
    required_services=["lab-api", "lab-internal-mock"],
    hints=[
        "The preview endpoint accepts any scheme/host — try the internal mock's hostname: lab-internal-mock.",
        "The mock service exposes synthetic cloud-metadata-style endpoints under /latest/.",
        "Hardened mode validates the resolved IP, not just the hostname string — redirects are checked too.",
    ],
    remediation_markdown=(
        "## Remediation\n\n"
        "1. Resolve the destination hostname and reject private/link-local/loopback "
        "ranges (RFC 1918, 127.0.0.0/8, 169.254.0.0/16) before connecting.\n"
        "2. Disable automatic redirect-following, or re-validate the destination "
        "of every redirect hop.\n"
        "3. Enforce a strict allowlist of permitted destination hosts where possible.\n"
        "4. Apply a short connect/read timeout and cap response size.\n"
        "5. Run the fetcher with no route to internal-only networks at the "
        "infrastructure layer (see `lab-net: internal: true` in docker-compose.yml) "
        "— see `lab/challenges/api7_ssrf/hardened.py`."
    ),
    points=150,
)


async def verify(ctx: VerificationContext, lab_db_url: str) -> VerificationResult:
    submitted_secret = (ctx.submitted_evidence or {}).get("secret", "").strip()
    if not submitted_secret:
        return VerificationResult(passed=False, evidence_summary="No secret submitted")

    conn = await asyncpg.connect(lab_db_url)
    try:
        row = await conn.fetchrow(
            "select secret from ssrf_internal_secrets where challenge_id = $1 limit 1",
            METADATA.id,
        )
    finally:
        await conn.close()

    if row is None:
        return VerificationResult(passed=False, evidence_summary="Lab not seeded")

    passed = submitted_secret == row["secret"]
    return VerificationResult(
        passed=passed,
        evidence_summary="Internal secret matched" if passed else "Secret did not match",
    )
