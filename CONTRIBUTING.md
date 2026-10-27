# Contributing to AEGIS

## Setup

```bash
git clone <repo-url>
cd aegis
cp .env.example .env
cp .env.lab.example .env.lab
# fill in your own Supabase project URL/keys in .env

docker compose up -d redis lab-db lab-internal-mock lab-api
python3 lab/scripts/seed.py

cd backend && pip install -r requirements.txt && cd ..
cd frontend && npm install && cd ..

# run backend: uvicorn app.main:app --reload (from backend/)
# run frontend: npm run dev (from frontend/)
```

Apply the Supabase migrations in `supabase/migrations/` in order (via the
Supabase CLI or the SQL editor), then:

```bash
python3 backend/scripts/seed_challenges.py
```

## Adding a new OWASP challenge

1. Create `backend/app/challenges/<id>.py` implementing `METADATA` and an
   async `verify(ctx, lab_db_url)` function — see `api1_bola.py` for the
   pattern. Keep `METADATA` entirely public (no exploit secrets); keep
   `verify()` as the only place that decides pass/fail.
2. Register it in `backend/app/challenges/registry.py`.
3. Add the vulnerable + hardened route pair under `lab/app/routers/`.
4. Seed any fixtures the challenge needs in `lab/scripts/seed.py`.
5. Write a vulnerable-vs-hardened regression test in `lab/tests/`.
6. Run `python3 backend/scripts/seed_challenges.py` to publish the
   catalog entry.

## Code style

- Backend: `black`/`ruff` defaults, type hints on public functions.
- Frontend: `next lint`.
- Keep PRs scoped to one change; include the regression test for any
  security-relevant fix.
- If your change adds, removes, or renames a route or changes a request/
  response schema, regenerate the API docs before committing:
  ```bash
  python3 backend/scripts/export_openapi.py
  ```
  CI fails the build if `backend/openapi.json` doesn't match what the
  live app actually serves.

## Tests

```bash
cd backend && pytest -q tests --ignore=tests/integration   # pure unit tests, no DB

# RLS / tenant isolation / achievement tests — need a throwaway Postgres:
docker run -d --rm -p 5434:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=aegis_test postgres:16-alpine
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5434/aegis_test pytest -q tests/integration

cd ../lab && docker compose up -d lab-db lab-internal-mock lab-api && pytest -q tests
```

A change to `supabase/migrations/*.sql` or an RLS policy should come with
a test in `backend/tests/integration/` that proves the policy actually
blocks what it's supposed to — see `test_rls_tenant_isolation.py` for the
pattern (connect as the `authenticated` role with `request.jwt.claim.sub`
set, not as the backend's own service-role connection, or you're not
testing RLS at all).

## Pull requests

Target `main` via a feature branch. CI runs backend unit tests, the lab's
vulnerable-vs-hardened regression suite, and a frontend lint/build.
