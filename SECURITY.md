# Security Policy

## Scope

AEGIS has two very different trust boundaries:

- **AEGIS Platform** (`frontend/`, `backend/`, Supabase): intended to be a
  secure-by-design multi-tenant SaaS application. Vulnerabilities here are
  real security issues — please report them.
- **AEGIS Labs** (`lab/`): *intentionally* vulnerable, by design, for
  training purposes. Reports like "the BOLA endpoint has no authorization
  check" are the point of the lab, not a bug. Do not file these.

If you are unsure which side a finding falls on, report it — we will
triage.

## Reporting a vulnerability in the platform

Please do **not** open a public GitHub issue for a suspected platform
vulnerability. Instead, use GitHub's private vulnerability reporting
("Security" tab → "Report a vulnerability") or email the maintainers
listed in `CONTRIBUTORS.md`. Include:

- A description of the issue and its impact
- Steps to reproduce (minimal repro appreciated)
- Any relevant logs or screenshots

We aim to acknowledge reports within 5 business days.

## Responsible use of AEGIS Labs

AEGIS Labs ships real, working exploits against synthetic services. By
running the lab you agree to:

- Test **only** your own local lab instance (bound to `localhost`/
  `127.0.0.1` by default — see `docker-compose.yml`)
- Never point lab techniques at systems you do not own or have explicit
  authorization to test
- Never deploy `LAB_MODE=vulnerable` services to a public network or
  production infrastructure

The lab's isolation controls (internal-only Docker network, no host socket
access, non-root containers, resource limits, localhost-only port
bindings) are part of its threat model, not optional hardening — please
report any way to break out of that isolation as a platform-severity
issue.
