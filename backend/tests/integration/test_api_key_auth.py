"""API-key authentication for read-only org endpoints, plus the security
events CSV export.

Keys are created over the JWT-authenticated API (`POST /orgs/{id}/api-keys`,
plaintext shown once) and then presented as `Authorization: Bearer aegis_...`.
These tests drive the real app with real headers — no dependency override —
so they exercise the actual bearer-token path end to end.
"""
import hashlib

import pytest

from app.core.auth import get_current_principal, get_current_user
from app.main import app as fastapi_app
from tests.integration.conftest import create_auth_user
from tests.integration.helpers import SyncAppClient, client_as

pytestmark = pytest.mark.usefixtures("clean_db")


def _clear_auth_overrides():
    """Overrides from client_as are global; key-path tests must resolve the
    real bearer token, so drop any override a previous test left behind."""
    fastapi_app.dependency_overrides.pop(get_current_user, None)
    fastapi_app.dependency_overrides.pop(get_current_principal, None)



async def _setup(pool, scopes=("read",), token="aegis_testtoken_0123456789"):
    owner = await create_auth_user(pool)
    org = await pool.fetchrow("insert into organizations (name) values ('Acme') returning id")
    await pool.execute(
        "insert into memberships (org_id, user_id, role) values ($1, $2, 'owner')",
        org["id"],
        owner,
    )
    digest = hashlib.sha256(token.encode()).hexdigest()
    key = await pool.fetchrow(
        "insert into api_keys (org_id, name, key_hash, scopes, created_by) "
        "values ($1, 'ci', $2, $3, $4) returning id",
        org["id"],
        digest,
        list(scopes),
        owner,
    )
    return owner, org["id"], key["id"], token


def _key_client(token):
    _clear_auth_overrides()
    c = SyncAppClient()
    c._auth_headers = {"Authorization": f"Bearer {token}"}
    return c


def _get(c, url):
    return c.get(url, headers=getattr(c, "_auth_headers", {}))


@pytest.mark.asyncio
async def test_read_scoped_key_can_list_projects(clean_db):
    pool = clean_db
    _, org_id, _, token = await _setup(pool)
    await pool.execute(
        "insert into projects (org_id, name, created_by) "
        "select $1, 'Roadmap', (select created_by from api_keys limit 1)",
        org_id,
    )
    resp = _get(_key_client(token), f"/orgs/{org_id}/projects")
    assert resp.status_code == 200
    assert [p["name"] for p in resp.json()] == ["Roadmap"]


@pytest.mark.asyncio
async def test_key_from_another_org_gets_404(clean_db):
    pool = clean_db
    _, org_id, _, token = await _setup(pool)
    other = await create_auth_user(pool)
    other_org = await pool.fetchrow("insert into organizations (name) values ('Other') returning id")
    await pool.execute(
        "insert into memberships (org_id, user_id, role) values ($1, $2, 'owner')",
        other_org["id"],
        other,
    )
    resp = _get(_key_client(token), f"/orgs/{other_org['id']}/projects")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_key_without_read_scope_gets_403(clean_db):
    pool = clean_db
    _, org_id, _, token = await _setup(pool, scopes=("webhooks",))
    resp = _get(_key_client(token), f"/orgs/{org_id}/projects")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_revoked_key_gets_401(clean_db):
    pool = clean_db
    _, org_id, key_id, token = await _setup(pool)
    await pool.execute("update api_keys set revoked_at = now() where id = $1", key_id)
    resp = _get(_key_client(token), f"/orgs/{org_id}/projects")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_key_use_stamps_last_used_at(clean_db):
    pool = clean_db
    _, org_id, key_id, token = await _setup(pool)
    assert (await pool.fetchrow("select last_used_at from api_keys where id = $1", key_id))[
        "last_used_at"
    ] is None
    resp = _get(_key_client(token), f"/orgs/{org_id}/projects")
    assert resp.status_code == 200
    row = await pool.fetchrow("select last_used_at from api_keys where id = $1", key_id)
    assert row["last_used_at"] is not None


@pytest.mark.asyncio
async def test_key_cannot_use_write_endpoints(clean_db):
    pool = clean_db
    _, org_id, _, token = await _setup(pool)
    _clear_auth_overrides()
    resp = SyncAppClient().post(
        f"/orgs/{org_id}/projects",
        json={"name": "nope"},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Write endpoints are JWT-only: the key fails JWT decoding like any
    # invalid token.
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_security_events_csv_export(clean_db):
    import csv
    import io

    pool = clean_db
    _, org_id, _, token = await _setup(pool)
    await pool.execute(
        "insert into security_events (org_id, event_type, severity, metadata) values "
        "($1, 'authorization_denied', 'warning', '{}'::jsonb), "
        "($1, 'auth_failure', 'info', '{}'::jsonb)",
        org_id,
    )
    resp = _get(_key_client(token), f"/orgs/{org_id}/security/events/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(resp.text)))
    assert rows[0] == ["id", "created_at", "event_type", "severity", "actor_id", "metadata"]
    assert {r[2] for r in rows[1:]} == {"authorization_denied", "auth_failure"}


@pytest.mark.asyncio
async def test_csv_export_requires_admin_for_jwt_users(clean_db):
    pool = clean_db
    _, org_id, _, _ = await _setup(pool)
    employee = await create_auth_user(pool)
    await pool.execute(
        "insert into memberships (org_id, user_id, role) values ($1, $2, 'employee')",
        org_id,
        employee,
    )
    assert client_as(employee).get(f"/orgs/{org_id}/security/events/export").status_code == 403
    owner = await create_auth_user(pool)
    await pool.execute(
        "insert into memberships (org_id, user_id, role) values ($1, $2, 'owner')",
        org_id,
        owner,
    )
    assert client_as(owner).get(f"/orgs/{org_id}/security/events/export").status_code == 200
