# Deployment

AEGIS Platform (frontend + backend + Supabase) can be deployed publicly.
**AEGIS Labs must never be deployed publicly** — see below.

## 1. Supabase (production project)

1. Create a new Supabase project (not the one you use for local dev).
2. Apply `supabase/migrations/*.sql` in order via the Supabase CLI
   (`supabase db push`) or the SQL editor.
3. Run the catalog seed scripts against it (point `DATABASE_URL` at the
   production project's connection string):
   ```bash
   python3 backend/scripts/seed_challenges.py
   python3 backend/scripts/seed_achievements.py
   ```
4. Copy the project's URL, anon key, service role key, and JWT secret
   into your deployment's environment (never into a committed `.env`).
5. Confirm RLS is enabled on every table (migration `0003` /
   `0005` do this, but double-check in the dashboard after any manual
   schema change).

## 2. Backend (FastAPI)

Any container host works (Fly.io, Render, a VPS, ECS, etc.). Required
environment variables — see `.env.example`:

```
SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET
DATABASE_URL            # production Supabase Postgres connection string
REDIS_URL               # a managed Redis instance for rate limiting
WEBHOOK_SIGNING_SECRET
CORS_ALLOWED_ORIGINS    # comma-separated, e.g. "https://app.example.com" — defaults to localhost:3000 only
```

Leave `LAB_RETEST_RUNNER_ENABLED` unset (it defaults to off) in this
deployment too: it makes the backend run test code and send traffic to a
lab, which is local-dev only.

Leave `LAB_DATABASE_URL` **unset** in this deployment. Without it,
challenge submissions are recorded as `local_unverified` and award zero
leaderboard points — which is the correct, safe behavior for a hosted
platform with no network path to anyone's local lab. (A learner who
wants server-verified points runs the backend locally alongside their
own lab stack, per the main README's quick start.)

Run with a process manager, e.g.:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

## 3. Frontend (Next.js)

Deploy to Vercel, or any Node host that can run `next build && next start`.
Required environment variables:
```
NEXT_PUBLIC_API_URL             # the backend's public URL
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
```

## 4. What never goes to production

- `lab/` and `docker-compose.yml`'s `lab-*` services. These are for the
  learner's own machine only (see `SECURITY.md` and `docs/THREAT_MODEL.md`).
  Do not build or push the `lab/Dockerfile` or
  `lab/mock-services/internal-metadata/Dockerfile` images to any public
  registry, and do not point `LAB_DATABASE_URL` at anything other than a
  learner's own local lab stack.
- Any `.env.lab` value. Lab secrets are intentionally weak/synthetic and
  must stay that way — swapping in "real" secrets there defeats the
  point and adds risk for no benefit.
- Real Supabase service-role keys in client-side (`NEXT_PUBLIC_*`) env
  vars. Only the anon key belongs in the frontend.

## 5. Post-deploy checklist

- [ ] RLS verified enabled on all tables in the production project
- [ ] `backend/scripts/seed_challenges.py` and `seed_achievements.py` run
      against production
- [ ] `LAB_DATABASE_URL` absent from the backend's production environment
- [ ] `CORS_ALLOWED_ORIGINS` set to the real frontend origin(s) — the
      default only allows `localhost:3000`
- [ ] Redis reachable from the backend (rate limiting silently becomes a
      no-op-adjacent failure mode otherwise — verify it, don't assume it)
