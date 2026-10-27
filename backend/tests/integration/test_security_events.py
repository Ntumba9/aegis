"""Proves app/middleware/security_logging.py actually writes rows — the
bug this closes is that app/core/audit.py's record_event() pointed at a
security_events table that didn't exist in any migration, and was never
called from anywhere. This test would have caught that: it drives the
real app through TestClient and asserts rows land in the real database.
"""
import pytest

from tests.integration.conftest import create_auth_user
from tests.integration.helpers import client_as

pytestmark = pytest.mark.usefixtures("clean_db")


async def _make_org_and_member(pool, owner_id, role="employee"):
    org = await pool.fetchrow("insert into organizations (name) values ('Acme') returning id")
    await pool.execute(
        "insert into memberships (org_id, user_id, role) values ($1, $2, $3)",
        org["id"],
        owner_id,
        role,
    )
    return org["id"]


@pytest.mark.asyncio
async def test_authorization_denial_is_logged_as_a_security_event(clean_db):
    pool = clean_db
    owner = await create_auth_user(pool)
    employee = await create_auth_user(pool)
    org_id = await _make_org_and_member(pool, owner, role="owner")
    # employee is a genuine member of org_id, just not admin/owner — RequireRole
    # returns 404 for a non-member (nothing to be unauthorized about) and 403
    # only for an actual member whose role is too low, so that's what we need here.
    await pool.execute(
        "insert into memberships (org_id, user_id, role) values ($1, $2, 'employee')", org_id, employee
    )

    resp = client_as(employee).get(f"/orgs/{org_id}/api-keys")
    assert resp.status_code == 403

    row = await pool.fetchrow(
        "select event_type, severity, org_id from security_events where org_id = $1 "
        "and event_type = 'authorization_denied'",
        org_id,
    )
    assert row is not None
    assert row["severity"] == "warning"


@pytest.mark.asyncio
async def test_every_request_is_logged_to_request_logs(clean_db):
    pool = clean_db
    before = await pool.fetchval("select count(*) from request_logs")

    client_as(await create_auth_user(pool)).get("/challenges")

    after = await pool.fetchval("select count(*) from request_logs")
    assert after == before + 1


@pytest.mark.asyncio
async def test_security_metrics_endpoint_reflects_real_denials(clean_db):
    pool = clean_db
    owner = await create_auth_user(pool)
    employee = await create_auth_user(pool)
    org_id = await _make_org_and_member(pool, owner, role="owner")
    await pool.execute(
        "insert into memberships (org_id, user_id, role) values ($1, $2, 'employee')", org_id, employee
    )

    for _ in range(3):
        client_as(employee).get(f"/orgs/{org_id}/api-keys")

    metrics = client_as(owner).get(f"/orgs/{org_id}/security/metrics").json()
    assert metrics["authorization_denials"] >= 3

    events = client_as(owner).get(f"/orgs/{org_id}/security/events").json()
    assert any(e["event_type"] == "authorization_denied" for e in events)


@pytest.mark.asyncio
async def test_non_admin_cannot_read_security_events(clean_db):
    pool = clean_db
    owner = await create_auth_user(pool)
    employee = await create_auth_user(pool)
    org_id = await _make_org_and_member(pool, owner, role="owner")
    await pool.execute(
        "insert into memberships (org_id, user_id, role) values ($1, $2, 'employee')", org_id, employee
    )

    resp = client_as(employee).get(f"/orgs/{org_id}/security/events")
    assert resp.status_code == 403
