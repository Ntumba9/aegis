"""Fixtures for integration tests that need a real Postgres database.

Point TEST_DATABASE_URL at a throwaway `postgres:16` instance (CI brings
one up as a service container — see .github/workflows/ci.yml). These
tests apply the real `supabase/migrations/*.sql` files unmodified, plus a
small stub (`stub_supabase.sql`) standing in for the parts of a genuine
Supabase project (auth schema, `auth.uid()`, the `authenticated` role)
that migration file assumes already exist.

Never point this at a real Supabase project — it truncates tables between
tests.
"""
import glob
import os
import uuid

import asyncpg
import pytest
import pytest_asyncio

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5434/aegis_test"
)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MIGRATIONS_DIR = os.path.join(REPO_ROOT, "supabase", "migrations")


async def _apply_schema(conn: asyncpg.Connection) -> None:
    with open(os.path.join(os.path.dirname(__file__), "stub_supabase.sql")) as f:
        await conn.execute(f.read())

    for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        with open(path) as f:
            await conn.execute(f.read())

    # Mirrors the broad table grants a real Supabase project gives its
    # `authenticated` role by default; RLS policies are what actually
    # restrict access on top of this.
    await conn.execute(
        "grant select, insert, update, delete on all tables in schema public to authenticated"
    )

    # Publish the challenge catalog (public METADATA only), as
    # scripts/seed_challenges.py does in a real deployment. Many tables
    # (user_progress, team_sessions, vulnerability_reports, ...) have a
    # foreign key to challenges(id), so tests need these rows to exist.
    from app.challenges.registry import all_metadata

    for m in all_metadata():
        await conn.execute(
            """
            insert into challenges (
                id, owasp_category, title, difficulty, summary,
                learning_objectives, prerequisites, authorized_scope,
                required_services, hints, remediation_markdown, points
            ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            on conflict (id) do nothing
            """,
            m.id, m.owasp_category, m.title, m.difficulty, m.summary,
            m.learning_objectives, m.prerequisites, m.authorized_scope,
            m.required_services, m.hints, m.remediation_markdown, m.points,
        )


@pytest_asyncio.fixture(scope="session")
async def db_pool():
    # Connect once as a superuser to build the schema.
    setup_conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await _apply_schema(setup_conn)
    finally:
        await setup_conn.close()

    pool = await asyncpg.create_pool(TEST_DATABASE_URL, min_size=1, max_size=5)
    yield pool
    await pool.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def bind_app_db_pool(db_pool):
    """Points app.db.session.get_pool() at the test database for the
    duration of the session, so API-layer tests (test_teams_api.py etc.)
    exercise the real endpoint code without needing a real DATABASE_URL."""
    import app.db.session as db_session
    from tests.integration.helpers import run_in_app_loop

    async def _open():
        return await asyncpg.create_pool(TEST_DATABASE_URL, min_size=1, max_size=5)

    db_session._pool = run_in_app_loop(_open())
    yield
    run_in_app_loop(db_session._pool.close())
    db_session._pool = None


@pytest_asyncio.fixture
async def clean_db(db_pool):
    """Truncates every table touched by the tests before each one runs, so
    tests don't leak state into each other."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            "truncate memberships, organizations, profiles, auth.users, "
            "teams, team_members, team_sessions, vulnerability_reports, retests, "
            "classrooms, classroom_students, classroom_assignments, "
            "user_progress, achievements, user_achievements, "
            "security_events, request_logs, api_keys restart identity cascade"
        )
    yield db_pool


async def create_auth_user(pool: asyncpg.Pool) -> uuid.UUID:
    row = await pool.fetchrow("insert into auth.users default values returning id")
    user_id = row["id"]
    await pool.execute("insert into profiles (id) values ($1)", user_id)
    return user_id


class AsUser:
    """Runs queries on a connection with `request.jwt.claim.sub` set to a
    given user, through the RLS-restricted `authenticated` role — exactly
    like PostgREST would for a real logged-in request."""

    def __init__(self, pool: asyncpg.Pool, user_id: uuid.UUID):
        self.pool = pool
        self.user_id = user_id

    async def fetch(self, query: str, *args):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("set local role authenticated")
                await conn.execute(
                    "select set_config('request.jwt.claim.sub', $1, true)", str(self.user_id)
                )
                return await conn.fetch(query, *args)

    async def execute(self, query: str, *args):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("set local role authenticated")
                await conn.execute(
                    "select set_config('request.jwt.claim.sub', $1, true)", str(self.user_id)
                )
                return await conn.execute(query, *args)
