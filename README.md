# AEGIS — Build. Break. Defend.

An open-source multi-tenant SaaS platform paired with a hands-on OWASP API
Security Top 10 (2023) training laboratory. Learn API security by attacking
real, intentionally vulnerable services running on your own machine, then
compare against a hardened implementation and verify your understanding
with automated tests.

**Status: Milestone 2 (in progress).** Auth, challenge catalog, and
server-side verification are implemented, and all ten OWASP API Security
Top 10 (2023) categories now have a working vulnerable + hardened
implementation pair with a regression test — see [Challenge catalog](#challenge-catalog).
Teams, leaderboards, achievements, and instructor features (Milestone 3)
are not yet built — see [Roadmap](#roadmap). Nothing below is claimed as
done unless it has a test backing it, and the lab regression suite has
only been verified by static review + compile checks in this environment
(no Docker available here) — run it yourself before trusting it.

## Architecture

```
aegis/
├── frontend/      Next.js (App Router) + TypeScript + Tailwind — AEGIS Platform UI
├── backend/       FastAPI — main SaaS API + challenge catalog + verification engine
├── supabase/      Postgres migrations + RLS policies (shared by platform & challenge data)
├── lab/           AEGIS Labs: isolated, intentionally vulnerable target services
│   ├── app/       lab-api: vulnerable/hardened endpoint pairs per OWASP category
│   ├── mock-services/   internal-only services (e.g. SSRF target), lab-net only
│   ├── scripts/   seed.py, reset.sh — reproducible lab state
│   └── tests/     vulnerable-vs-hardened regression tests
└── .github/workflows/ci.yml
```

**AEGIS Platform** (frontend + backend + Supabase) is the production-grade
application: real auth, real tenant isolation, real RLS. **AEGIS Labs**
(`lab/`) is a separate, deliberately insecure codebase whose only job is to
be exploitable in a controlled way. The platform backend never runs
vulnerable code; it only reads lab state to verify challenge completions,
and only when `LAB_DATABASE_URL` is configured for a local dev stack.

**The core multi-tenant SaaS app** (not just the training platform) has
working endpoints and UI for: organizations + invitations (`/orgs`),
projects + tasks, document upload/download via Supabase Storage
(`/orgs/{id}/documents`), API key generation/rotation/revocation,
signed-webhook registration + test delivery, and the Blue Team security
operations dashboard (`/orgs/{id}/security`) — all under one tabbed
dashboard at `/orgs/{id}` in the frontend.

## Quick start

```bash
git clone <repo-url> && cd aegis
cp .env.example .env            # fill in your Supabase project URL/keys
cp .env.lab.example .env.lab

# 1. Start the lab (isolated, localhost-only)
docker compose up -d lab-db lab-internal-mock lab-api
python3 lab/scripts/seed.py

# 2. Apply Supabase migrations (supabase/migrations/*.sql, in order)
#    via the Supabase CLI or SQL editor, then publish the challenge catalog:
cd backend && pip install -r requirements.txt
python3 scripts/seed_challenges.py
python3 scripts/seed_achievements.py

# 3. Run the platform
uvicorn app.main:app --reload --port 8000      # from backend/
cd ../frontend && npm install && npm run dev   # from frontend/
```

Visit `http://localhost:3000`, sign up, and browse the Challenge Catalog.

## API documentation

The backend auto-generates OpenAPI 3.1 documentation from its actual
route/schema definitions — nothing hand-written to drift out of sync:

- **Interactive:** `http://localhost:8000/docs` (Swagger UI) while the
  backend is running, or `/redoc` for the ReDoc view.
- **Static JSON:** [`backend/openapi.json`](backend/openapi.json), committed
  to the repo and regenerated with:
  ```bash
  python3 backend/scripts/export_openapi.py
  ```
  Currently covers all 49 paths / 62 route+method combinations across
  orgs, projects/tasks, documents, API keys, webhooks, challenges, teams,
  leaderboard, achievements, classrooms, and security operations.

## Challenge catalog

All ten OWASP API Security Top 10 (2023) categories, each as a
vulnerable/hardened endpoint pair plus a regression test in `lab/tests/`:

| Challenge ID | Category | Difficulty | Points |
|---|---|---|---|
| `api1-bola-project-files` | API1 BOLA | beginner | 100 |
| `api2-broken-auth-predictable-session` | API2 Broken Authentication | beginner | 100 |
| `api3-bopla-role-escalation` | API3 BOPLA | intermediate | 150 |
| `api4-resource-consumption-pagination` | API4 Resource Consumption | beginner | 100 |
| `api5-bfla-admin-broadcast` | API5 BFLA | beginner | 100 |
| `api6-sensitive-flows-coupon-replay` | API6 Sensitive Business Flows | beginner | 150 |
| `api7-ssrf-url-preview` | API7 SSRF | intermediate | 150 |
| `api8-misconfiguration-verbose-errors` | API8 Security Misconfiguration | beginner | 100 |
| `api9-inventory-shadow-v1-endpoint` | API9 Improper Inventory Management | beginner | 100 |
| `api10-unsafe-consumption-pricing` | API10 Unsafe Consumption of APIs | advanced | 200 |

Source of truth for descriptions, hints, and remediation is each
challenge's `METADATA` in `backend/app/challenges/`; `scripts/seed_challenges.py`
publishes it into Supabase.

## Why server-side verification

Challenge completion is **never** decided by a client-submitted boolean.
Each challenge's `verify()` function (see `backend/app/challenges/`)
independently re-derives the expected outcome — here, by reading the
seeded flag/secret directly from the isolated lab database — and compares
it to what the user submitted. If the backend has no network path to a
lab instance (e.g. a purely hosted deployment with no local lab attached),
a submission is recorded as `local_unverified` and **awarded zero
leaderboard points**, per the project's anti-cheating requirement.

## Security model

- Vulnerable lab services run only in Docker, bind to `127.0.0.1`, run as
  non-root, have CPU/memory limits, and sit on `lab-net`, a Docker network
  marked `internal: true` — no route to the outside world. This is what
  makes the SSRF challenge (`api7-ssrf-url-preview`) safe to ship: the
  "internal" service it reaches is only ever reachable from inside that
  network.
- The main backend joins `lab-net` *only* to read the lab's Postgres
  instance for verification — it never calls a vulnerable endpoint itself.
- Tenant isolation in the main app is enforced twice: explicit `org_id`
  checks in every query (`backend/app/api/`), and Postgres RLS policies
  (`supabase/migrations/0003_rls_policies.sql`) as defense in depth.
- API keys are stored as SHA-256 hashes; plaintext is shown exactly once.
- Webhooks are HMAC-signed with a replay window (`backend/app/services/webhooks.py`).
- Every request is logged, and every 401/403/429 response is additionally
  recorded as a `security_events` row (`backend/app/middleware/security_logging.py`)
  — this is what the Blue Team dashboard (`/orgs/{id}/security`, admin/owner
  only) reads from. No fabricated metrics: if nothing triggered a denial,
  the dashboard shows zero.

See [SECURITY.md](SECURITY.md) for the responsible-disclosure policy and
the rules of engagement for the lab, and [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md)
for the full breakdown of what's defended against on each side of the
platform/lab boundary. [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) covers
taking the platform (never the lab) to production.

## Testing

```bash
cd backend && pytest -q tests --ignore=tests/integration   # unit tests — passing: 3/3
cd backend && TEST_DATABASE_URL=... pytest -q tests/integration  # RLS, tenant isolation, achievements, security events, teams/leaderboard/classrooms/orgs/documents/webhooks/projects APIs, + Schemathesis API fuzzing (needs Postgres) — 94 tests
cd ../lab && pytest -q tests                # 10 vulnerable-vs-hardened regression files (needs the lab stack running)
```

`backend/tests/integration/` runs the real `supabase/migrations/*.sql`
against a throwaway Postgres (CI spins one up as a service container —
see `.github/workflows/ci.yml`). The RLS/tenant-isolation tests connect
directly as the `authenticated` role with `request.jwt.claim.sub` set per
test user — the same mechanism
PostgREST uses — so these actually exercise the RLS policies, not just
application code that happens to filter by `org_id` correctly. The
teams/leaderboard/classrooms tests instead drive the real FastAPI app
through `TestClient`, with `get_current_user` overridden to a given test
user (standing in for a verified Supabase JWT) — so these exercise actual
routing, validation, and the app's own authorization checks end-to-end.

CI runs all three suites plus a frontend lint/build on every PR. No test
result is reported here unless it actually ran. In this development
environment: the backend unit tests ran and passed (3/3), all 97
backend tests (3 unit + 94 integration — including Schemathesis's 58
generated fuzz cases — across 11 test files) collect cleanly
under pytest (confirming imports/fixtures/async wiring are correct —
collection alone catches a real class of bugs, e.g. a bad import or a
fixture that doesn't exist), the full challenge registry
(all 10) imports cleanly, the lab FastAPI app was exercised directly via
`TestClient` (no Docker) with requests reaching real route handlers
through auth and business logic, and the frontend's `npm run build`
succeeded with zero type/lint errors across all 10 routes. What did
**not** run here, because neither a live Postgres nor the Docker daemon
was available: `backend/tests/integration/*` against a real database, and
`lab/tests/*` end-to-end. Run both yourself before relying on them.

## Roadmap

- **Milestone 1**: auth, challenge catalog, BOLA + SSRF challenges,
  server-side verification, progress tracking. ✅
- **Milestone 2**: remaining 8 OWASP API Top 10 challenges (all 10 now
  have vulnerable+hardened pairs and regression tests), remediation
  walkthroughs (`METADATA.remediation_markdown` per challenge). ✅
  Security *reports* now ship as part of Milestone 3's vulnerability-report
  flow rather than a separate dashboard — see below.
- **Milestone 3** (this release): teams (`/teams`), Red/Blue Team
  collaboration (attack/defense team sessions, vulnerability reports,
  assignment, retesting), achievements (auto-awarded server-side on
  verified completions/sessions — never client-settable), leaderboards
  (individual + team, points only from server-verified completions),
  and instructor classrooms (`/classrooms`: invites, assignments,
  completion reporting). ✅
- **Milestone 4** (in progress): RLS/tenant-isolation/achievement
  integration tests against a real Postgres in CI, a threat model
  (`docs/THREAT_MODEL.md`), a deployment guide (`docs/DEPLOYMENT.md`),
  and a configurable CORS origin (was hardcoded to `localhost:3000`).
  Still open: integration tests for the Milestone 3 endpoints
  themselves (teams/leaderboard/classrooms CRUD, as opposed to the RLS
  layer underneath them), and a CHANGELOG.

**What's still thin in Milestone 3:** classroom invite tokens are
in-process (`backend/app/api/classrooms.py::_invite_tokens`) rather than
persisted — fine for a single backend instance, not for multi-instance
deployment yet. There's no dedicated "Blue Team" defense-verification
flow beyond recording a `defense`-mode session and a `retest` outcome; a
defense session doesn't yet auto-run the `lab/tests/` regression suite
for you.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for local setup and the guide to
adding a new OWASP challenge module, and [CHANGELOG.md](CHANGELOG.md) for
what's shipped in each milestone.

## License

MIT — see [LICENSE](LICENSE).
