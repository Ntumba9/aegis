# AEGIS Threat Model

AEGIS has two deliberately different trust boundaries. Confusing them is
the single biggest risk in this project, so the model is organized around
that split first.

## 1. AEGIS Platform (frontend, backend, Supabase)

**Goal:** be a genuinely secure multi-tenant SaaS app and public training
platform — the opposite of the lab.

**Assets:** user credentials, organization data (projects/tasks/documents),
API keys, webhook secrets, challenge progress, team/report data.

**Trust boundaries:**
- Browser ↔ backend: Supabase-issued JWT, verified locally on every
  request (`app/core/auth.py`). No session state trusted from the client
  beyond that signed token.
- Backend ↔ Supabase Postgres: the backend connects with a
  service-role-equivalent connection and therefore **bypasses RLS** — it
  must and does re-implement every authorization check RLS would
  otherwise enforce (org membership, role, resource ownership). RLS is
  the second line of defense if an app-layer check is ever missed; the
  integration tests in `backend/tests/integration/` exercise RLS
  directly, not just the app layer.
- Backend ↔ AEGIS Labs: the backend reads the **lab's** Postgres instance
  (`LAB_DATABASE_URL`) only to verify challenge completions. It never
  calls a lab HTTP endpoint, vulnerable or hardened.

**Key mitigations already in place:**
- API keys stored as SHA-256 hashes; shown in plaintext exactly once.
- Webhooks HMAC-signed with a bounded replay window.
- Rate limiting on challenge verification submissions (abuse/score
  manipulation).
- Achievements and leaderboard points are only ever written by backend
  services (`app/services/achievements.py`), never by a client-reachable
  write path — there is no RLS INSERT policy on `user_achievements` or
  `user_progress` for the `authenticated` role at all.
- Every request is logged, and auth failures/authorization denials/rate-limit
  hits are recorded as `security_events` (`app/middleware/security_logging.py`)
  — same principle: no RLS INSERT policy for `authenticated` on that table
  either, so a compromised frontend can observe its own denials via the
  dashboard (if it's an admin) but can't forge or erase the record of them.
- Challenge completion is independently re-derived server-side
  (`app/challenges/*.py::verify()`), never trusted from a client boolean.

Classroom invite tokens are persisted in `classroom_invites` (migration
`0008`): only a SHA-256 of the token is stored, tokens expire after 72
hours, and each can be used once (a single conditional `UPDATE`, so two
concurrent accepts cannot both succeed). Integration tests cover
persistence across a pool restart, expiry, reuse, and the concurrent case.

## 2. AEGIS Labs (the vulnerable training targets)

**Goal:** be realistically exploitable, entirely on the learner's own
machine, with zero path to anything real.

**Threat we're defending against:** a learner (or their browser/tooling)
accidentally or intentionally using a lab exploit against something that
isn't the lab.

**Isolation controls, and why each one matters:**

| Control | Defends against |
|---|---|
| `lab-net` is a Docker network with `internal: true` | The lab's "internal" SSRF target (`lab-internal-mock`) and lab-db have **no route to the public internet** — even a full RCE inside `lab-api` can't reach out through the network layer. |
| Lab ports bind to `127.0.0.1` only | Nothing on the lab is reachable from another machine on the LAN, let alone the internet. |
| Containers run as a non-root user | Caps the blast radius of any exploit that does land inside a container. |
| CPU/memory limits (`deploy.resources.limits`) | A resource-consumption exploit (API4) can't take down the host. |
| Synthetic data only, generated at seed time | There is nothing sensitive in the lab to actually steal, even if isolation somehow failed. |
| Separate `.env.lab` / `LAB_JWT_SECRET` | Lab credentials and signing secrets are never shared with the production platform's secrets. |
| `backend` joins `lab-net` *only* for DB reads | The one bridge between "secure platform" and "insecure lab" is narrow, explicit, and read-only in practice (verification queries only). |

**Out of scope for the lab's threat model (by design):** every
vulnerability documented in `backend/app/challenges/*.py::METADATA` is
intentional and not a bug to report (see `SECURITY.md`). What *is* in
scope: any way to escape `lab-net`'s isolation, gain host access from a
container, or reach the real Supabase project's credentials from inside
the lab.

## 3. Shared concerns

- **Secrets:** `.env` / `.env.lab` are gitignored; `.env.example` /
  `.env.lab.example` contain no real values. `LAB_JWT_SECRET` and
  `SUPABASE_JWT_SECRET` are never the same value, and the lab's synthetic
  user passwords are documented as intentionally weak/public (`lab/app/auth.py`).
- **Supply chain:** dependencies are pinned in `requirements.txt` /
  `package.json`; CI builds from a clean checkout on every PR.
- **What we do NOT defend against:** a learner running the lab stack
  while also exposing their Docker daemon or host network in some other
  unrelated way. The isolation guarantees above assume a standard local
  Docker Desktop/Engine setup, not a deliberately misconfigured host.
