"""API-layer integration tests for webhook registration + test delivery.
app.services.webhooks.deliver is monkeypatched so these don't make a real
network call."""
import pytest

from tests.integration.conftest import create_auth_user
from tests.integration.helpers import client_as

pytestmark = pytest.mark.usefixtures("clean_db")


async def _make_org_with_admin(pool, admin_id):
    org = await pool.fetchrow("insert into organizations (name) values ('Acme') returning id")
    await pool.execute(
        "insert into memberships (org_id, user_id, role) values ($1, $2, 'owner')", org["id"], admin_id
    )
    return org["id"]


@pytest.mark.asyncio
async def test_create_webhook_returns_secret_once(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    org_id = await _make_org_with_admin(pool, alice)

    resp = client_as(alice).post(
        f"/orgs/{org_id}/webhooks",
        json={"target_url": "https://example.com/hook", "event_types": ["task.created"]},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "signing_secret" in body

    listed = client_as(alice).get(f"/orgs/{org_id}/webhooks").json()
    assert "signing_secret" not in listed[0]


@pytest.mark.asyncio
async def test_send_test_event_records_delivery(clean_db, monkeypatch):
    pool = clean_db
    alice = await create_auth_user(pool)
    org_id = await _make_org_with_admin(pool, alice)

    async def fake_deliver(url, secret, payload, max_retries=1):
        return True

    monkeypatch.setattr("app.api.webhooks.webhook_service.deliver", fake_deliver)

    webhook_id = client_as(alice).post(
        f"/orgs/{org_id}/webhooks",
        json={"target_url": "https://example.com/hook", "event_types": ["task.created"]},
    ).json()["id"]

    resp = client_as(alice).post(f"/orgs/{org_id}/webhooks/{webhook_id}/test")
    assert resp.status_code == 200
    assert resp.json()["status"] == "delivered"

    row = await pool.fetchrow("select status from webhook_deliveries where webhook_id = $1", webhook_id)
    assert row["status"] == "delivered"


@pytest.mark.asyncio
async def test_deleted_webhook_cannot_be_tested(clean_db, monkeypatch):
    pool = clean_db
    alice = await create_auth_user(pool)
    org_id = await _make_org_with_admin(pool, alice)

    webhook_id = client_as(alice).post(
        f"/orgs/{org_id}/webhooks",
        json={"target_url": "https://example.com/hook", "event_types": ["task.created"]},
    ).json()["id"]
    client_as(alice).delete(f"/orgs/{org_id}/webhooks/{webhook_id}")

    resp = client_as(alice).post(f"/orgs/{org_id}/webhooks/{webhook_id}/test")
    assert resp.status_code == 404
