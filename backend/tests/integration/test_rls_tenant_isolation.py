"""Cross-tenant isolation + Supabase RLS tests.

These exercise the Postgres RLS policies directly (supabase/migrations/
0003_rls_policies.sql), connecting as the `authenticated` role with
`request.jwt.claim.sub` set per user — the same mechanism PostgREST (and
therefore Supabase) uses for every real request. This is what actually
proves tenant isolation holds even if an application-layer bug ever
forgot an `org_id` check.
"""
import pytest

from tests.integration.conftest import AsUser, create_auth_user

pytestmark = pytest.mark.usefixtures("clean_db")


async def _create_org_with_owner(pool, owner_id, name: str):
    row = await pool.fetchrow(
        "insert into organizations (name) values ($1) returning id", name
    )
    await pool.execute(
        "insert into memberships (org_id, user_id, role) values ($1, $2, 'owner')",
        row["id"],
        owner_id,
    )
    return row["id"]


@pytest.mark.asyncio
async def test_user_cannot_see_an_organization_they_do_not_belong_to(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    bob = await create_auth_user(pool)
    org_id = await _create_org_with_owner(pool, alice, "Alice Corp")

    bob_view = AsUser(pool, bob)
    rows = await bob_view.fetch("select id from organizations where id = $1", org_id)
    assert rows == []  # RLS hides it entirely — not a 403, just not there


@pytest.mark.asyncio
async def test_org_member_can_see_their_own_organization(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    org_id = await _create_org_with_owner(pool, alice, "Alice Corp")

    alice_view = AsUser(pool, alice)
    rows = await alice_view.fetch("select id from organizations where id = $1", org_id)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_project_is_isolated_across_tenants(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    bob = await create_auth_user(pool)
    alice_org = await _create_org_with_owner(pool, alice, "Alice Corp")
    bob_org = await _create_org_with_owner(pool, bob, "Bob LLC")

    await pool.execute(
        "insert into projects (org_id, name, created_by) values ($1, 'Secret Roadmap', $2)",
        alice_org,
        alice,
    )

    bob_view = AsUser(pool, bob)
    rows = await bob_view.fetch("select id from projects where org_id = $1", alice_org)
    assert rows == []

    alice_view = AsUser(pool, alice)
    rows = await alice_view.fetch("select id from projects where org_id = $1", alice_org)
    assert len(rows) == 1

    # And Bob genuinely cannot see it even without filtering by org_id —
    # proving this isn't just an app-layer WHERE clause working correctly.
    rows = await bob_view.fetch("select id from projects")
    assert rows == []


@pytest.mark.asyncio
async def test_non_admin_cannot_insert_a_project_for_their_own_org(clean_db):
    """RLS additionally enforces role, not just tenant membership: a plain
    'employee' member cannot create a project (projects_admin_write policy)."""
    pool = clean_db
    employee = await create_auth_user(pool)
    org_row = await pool.fetchrow("insert into organizations (name) values ('Acme') returning id")
    await pool.execute(
        "insert into memberships (org_id, user_id, role) values ($1, $2, 'employee')",
        org_row["id"],
        employee,
    )

    employee_view = AsUser(pool, employee)
    with pytest.raises(Exception):
        await employee_view.execute(
            "insert into projects (org_id, name, created_by) values ($1, 'New Project', $2)",
            org_row["id"],
            employee,
        )
