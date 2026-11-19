# AEGIS — Build. Break. Defend.

An open-source multi-tenant SaaS platform paired with a hands-on OWASP API
Security Top 10 (2023) training laboratory. Learn API security by attacking
real, intentionally vulnerable services running on your own machine, then
compare against a hardened implementation and verify your understanding
with automated tests.

**Status: Milestone 4 (in progress).** Milestones 1–3 are implemented:
auth, challenge catalog, server-side verification, all ten OWASP API
Security Top 10 (2023) categories as vulnerable + hardened pairs with a
regression test (see [Challenge catalog](#challenge-catalog)), plus teams,
leaderboards, achievements, and instructor classrooms — see
[Roadmap](#roadmap). Nothing below is claimed as done unless it has a
test backing it.

**Verified on 2026-11-17** (one Windows machine, no Docker: plain
processes, PostgreSQL 16.15, Python 3.12, everything bound to 127.0.0.1):
backend unit tests 3/3, backend integration tests 94/94 (including 58
Schemathesis cases), lab regression tests 24/24, and the API1 BOLA
challenge end to end (attack on the vulnerable endpoint, server-side flag
verification through the UI, 403 on the hardened endpoint). That run used
a local stand-in for Supabase auth, not a real Supabase project.
**GitHub Actions:** the first run (2026-10-27) failed all four jobs; the
run on 2026-11-17 (commit `761cd6b`) passed all four — backend unit 3,
backend integration 94, lab regression 24, and frontend lint, type-check
and build — using the default `docker-compose.yml`. The lab network is
`internal: true`, which Docker will not publish host ports for, so the
lab is reached through two loopback forwarders (`lab-proxy-api`,
`lab-proxy-db`); the same 24 lab tests also passed against it locally on
Docker Desktop.

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
and only when `LAB_DATABASE_URL` is configured for a local dev stack. The one
exception is the optional lab verification runner (below), which is off by
default.

### Lab verification runner (optional, local dev only, off by default)

A team lead can ask the backend to run the lab's own regression test for a
vulnerability report's challenge (`POST /teams/reports/{id}/lab-verification`)
and records the real result as `passed`, `failed`, `error` or `unreachable`
(never collapsed). **This is evidence about the lab's reference
implementation — its vulnerable and hardened endpoints — not proof that a
team fixed anything:** users never submit code, so nothing here can test a
team's own remediation, and a run never changes a report's remediation
status or its human-declared retests.

It is a test runner inside a server, so it is constrained: each challenge
maps to one fixed test file in server config (no request value reaches the
command, path or environment); the child gets a scrubbed environment (no
database URLs or keys); the lab address comes from server config and must be
loopback or `lab-api`; raw test output is discarded (it can contain response
bodies, i.e. flags) and only counts and failing test names are kept; there
is a timeout, a one-run-at-a-time cap across workers (busy answers 429), a
per-challenge cooldown (the lab's own rate limiters are stateful) and a
per-user rate limit. On POSIX the child also gets CPU, memory and file
rlimits; on Windows it does not, so only the timeout, discarded output and
scrubbed environment apply there. Enable it with `LAB_RETEST_RUNNER_ENABLED=true`
(plus `LAB_RETEST_BASE_URL`, default `http://127.0.0.1:8100`, and
`LAB_RETEST_TIMEOUT_SECONDS`) on a local dev backend only — never in a hosted
deployment, exactly like `LAB_DATABASE_URL`. It has been exercised against
the real lab under Docker Compose (2026-11-17, local, synthetic data): a
team lead's run came back `passed`, an immediate second run was refused by
the cooldown (429), and the report's remediation status stayed `open`.

**The core multi-tenant SaaS app** (not just the training platform) has
working endpoints and UI for: organizations + invitations (`/orgs`),
projects + tasks, document upload/download via Supabase Storage
(`/orgs/{id}/documents`), API key generation/rotation/revocation (keys authenticate the read-only org endpoints, with scope enforcement and last-used tracking), CSV export of the security event feed,
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

When the platform runs through Docker Compose, the backend (8000) and
frontend (3000) are published on `127.0.0.1` only. `BACKEND_BIND_ADDR` and
`FRONTEND_BIND_ADDR` in `.env` change that (see `.env.example`); they run
dev servers, so widen them only deliberately. The lab's ports are not
configurable and always stay on `127.0.0.1`.

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
  Currently covers all 52 paths / 61 route+method combinations across
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
  instance for verification — it never calls a vulnerable endpoint itself
  (unless the optional, off-by-default lab verification runner is enabled).
- Tenant isolation in the main app is enforced twice: explicit `org_id`
  checks in every query (`backend/app/api/`), and Postgres RLS policies
  (`supabase/migrations/0003_rls_policies.sql`) as defense in depth.
- API keys are stored as SHA-256 hashes; plaintext is shown exactly once. A key authenticates only the read-only org endpoints, only for its own org, and only with the `read` scope; everything else still requires a user JWT.
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
# Backend unit tests (no database): 14 tests (11 run the lab runner for real)
cd backend && pytest -q tests --ignore=tests/integration

# Backend integration tests: 131 tests — RLS, tenant isolation, achievements,
# security events + CSV export, API-key auth, team-less report RLS, teams/
# leaderboard/classrooms/orgs/documents/webhooks/
# projects/lab-verification APIs, plus 60 Schemathesis fuzz cases. Needs an EMPTY Postgres
# database (see the notes below).
cd backend && TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5434/aegis_test pytest -q tests/integration

# Lab regression tests: 24 tests in 10 files, against a freshly seeded lab
pytest -q lab/tests
```

The lab tests talk to `LAB_BASE_URL` (default `http://localhost:8100`). The
SSRF test targets `LAB_INTERNAL_MOCK_URL` (default
`http://lab-internal-mock:9000`, the Docker hostname); set it if you run
the lab as plain processes instead of with Docker Compose.

`backend/tests/integration/` runs the real `supabase/migrations/*.sql`
against a throwaway Postgres (CI spins one up as a service container —
see `.github/workflows/ci.yml`). The RLS/tenant-isolation tests connect
directly as the `authenticated` role with `request.jwt.claim.sub` set per
test user — the same mechanism
PostgREST uses — so these actually exercise the RLS policies, not just
application code that happens to filter by `org_id` correctly. The
teams/leaderboard/classrooms/projects/documents/webhooks tests instead
drive the real FastAPI app through an ASGI client
(`backend/tests/integration/helpers.py`, run on one dedicated event loop
so it can share an asyncpg pool), with `get_current_user` overridden to a
given test user (standing in for a verified Supabase JWT) — so these
exercise actual routing, validation, and the app's own authorization
checks end-to-end. The integration database is seeded with the public
challenge catalog because many tables have foreign keys to it.

**Re-running.** Two of the suites are not idempotent, and CI avoids this by
always starting from a fresh database / fresh lab:

- The integration schema setup fails with `DuplicateTableError` on a
  database that already has the tables — drop and recreate the test
  database before each run.
- The lab suite is stateful: the hardened export endpoint keeps an
  in-process rate limit (5 requests per minute), so running the lab tests
  twice within a minute fails `test_hardened_export_caps_at_50`. Reseed and
  recreate `lab-api` between runs (`./lab/scripts/reset.sh` does this).

**What has actually run.** CI runs the unit, integration and lab suites
plus a frontend lint, type-check and build on every push to `main` and
every PR. As of 2026-11-17 all four CI jobs pass (3 unit, 94 integration,
24 lab tests), and the same counts passed in a local run on Windows
without Docker (plain processes, PostgreSQL 16.15, Python 3.12). Later
work (persisted invites, the lab verification runner, report-RLS
hardening, API-key auth, CSV export) has so far been run locally only;
CI has not yet run it. On 2026-11-19, 14 unit and 131 integration tests
passed on Linux (Python 3.10, PostgreSQL 14 — not the usual 16, noted as
an environment difference, not a claimed equivalence). The frontend has no tests of its own — CI only lints, type-checks and builds
it. The end-to-end API1 BOLA walkthrough (attack the vulnerable endpoint,
submit the flag through the UI, server-side verification, 403 from the
hardened endpoint) was run by hand, using a local stand-in for Supabase
auth; it is not automated.

## Roadmap

- **Milestone 1**: auth, challenge catalog, BOLA + SSRF challenges,
  server-side verification, progress tracking. ✅
- **Milestone 2**: remaining 8 OWASP API Top 10 challenges (all 10 now
  have vulnerable+hardened pairs and regression tests), remediation
  walkthroughs (`METADATA.remediation_markdown` per challenge). ✅
  Security *reports* now ship as part of Milestone 3's vulnerability-report
  flow rather than a separate dashboard — see below.
- **Milestone 3**: teams (`/teams`), Red/Blue Team
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
  The Milestone 3 endpoint integration tests and the CHANGELOG now exist.
  CI is green as of 2026-11-17, the frontend builds, and the lab runs
  under the default `docker-compose.yml`. Still open: replacing the `any`
  types in the frontend (currently lint warnings).

**What's still thin in Milestone 3:** classroom invite tokens are now
persisted with expiry and single use (`classroom_invites`, migration
`0008`). A retest outcome (`fixed` / `still_vulnerable`) is still
declared by a person; the optional lab verification runner adds a
separately recorded, server-run check of the lab's own regression test,
but it cannot verify a team's own fix (see above), and a defense-mode
session is not linked to retests or reports.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for local setup and the guide to
adding a new OWASP challenge module, and [CHANGELOG.md](CHANGELOG.md) for
what's shipped in each milestone.

## License

MIT — see [LICENSE](LICENSE).
