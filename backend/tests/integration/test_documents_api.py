"""API-layer integration tests for document upload/list/download/delete.

`app.services.storage` is monkeypatched to avoid needing a real Supabase
Storage bucket — these tests cover the database side (ownership checks,
size limit, listing, deletion), not the actual Storage API call, which
has no equivalent in CI without a real Supabase project.
"""
import io

import pytest

from tests.integration.conftest import create_auth_user
from tests.integration.helpers import client_as

pytestmark = pytest.mark.usefixtures("clean_db")


@pytest.fixture(autouse=True)
def mock_storage(monkeypatch):
    uploaded = {}
    monkeypatch.setattr("app.api.documents.storage.upload", lambda path, data, ct: uploaded.setdefault(path, data))
    monkeypatch.setattr("app.api.documents.storage.get_signed_url", lambda path, expires_in=3600: f"https://fake/{path}")
    monkeypatch.setattr("app.api.documents.storage.delete", lambda path: uploaded.pop(path, None))
    return uploaded


async def _make_org_with_admin(pool, admin_id):
    org = await pool.fetchrow("insert into organizations (name) values ('Acme') returning id")
    await pool.execute(
        "insert into memberships (org_id, user_id, role) values ($1, $2, 'owner')", org["id"], admin_id
    )
    return org["id"]


@pytest.mark.asyncio
async def test_upload_list_and_download_document(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    org_id = await _make_org_with_admin(pool, alice)

    resp = client_as(alice).post(
        f"/orgs/{org_id}/documents",
        files={"file": ("notes.txt", io.BytesIO(b"hello world"), "text/plain")},
    )
    assert resp.status_code == 201
    doc = resp.json()
    assert doc["filename"] == "notes.txt"
    assert doc["size_bytes"] == len(b"hello world")

    listed = client_as(alice).get(f"/orgs/{org_id}/documents").json()
    assert len(listed) == 1

    download = client_as(alice).get(f"/orgs/{org_id}/documents/{doc['id']}/download")
    assert download.status_code == 200
    assert download.json()["download_url"].startswith("https://fake/")


@pytest.mark.asyncio
async def test_employee_cannot_delete_but_can_upload(clean_db):
    pool = clean_db
    owner = await create_auth_user(pool)
    employee = await create_auth_user(pool)
    org_id = await _make_org_with_admin(pool, owner)
    await pool.execute(
        "insert into memberships (org_id, user_id, role) values ($1, $2, 'employee')", org_id, employee
    )

    upload = client_as(employee).post(
        f"/orgs/{org_id}/documents",
        files={"file": ("a.txt", io.BytesIO(b"x"), "text/plain")},
    )
    assert upload.status_code == 201

    delete = client_as(employee).delete(f"/orgs/{org_id}/documents/{upload.json()['id']}")
    assert delete.status_code == 403


@pytest.mark.asyncio
async def test_upload_rejected_over_size_limit(clean_db, monkeypatch):
    pool = clean_db
    alice = await create_auth_user(pool)
    org_id = await _make_org_with_admin(pool, alice)

    monkeypatch.setattr("app.api.documents.MAX_UPLOAD_BYTES", 5)

    resp = client_as(alice).post(
        f"/orgs/{org_id}/documents",
        files={"file": ("big.txt", io.BytesIO(b"this is more than five bytes"), "text/plain")},
    )
    assert resp.status_code == 413
