"""API-layer integration tests for project/task CRUD, including the
update/delete endpoints that were previously missing entirely (create +
list only — no way to ever mark a task done)."""
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
async def test_update_project_name_and_description(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    org_id = await _make_org_with_admin(pool, alice)
    project_id = client_as(alice).post(f"/orgs/{org_id}/projects", json={"name": "Old name"}).json()["id"]

    resp = client_as(alice).patch(
        f"/orgs/{org_id}/projects/{project_id}", json={"name": "New name", "description": "updated"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New name"
    assert resp.json()["description"] == "updated"


@pytest.mark.asyncio
async def test_mark_task_done(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    org_id = await _make_org_with_admin(pool, alice)
    project_id = client_as(alice).post(f"/orgs/{org_id}/projects", json={"name": "P"}).json()["id"]
    task_id = client_as(alice).post(
        f"/orgs/{org_id}/projects/{project_id}/tasks", json={"title": "Fix the bug"}
    ).json()["id"]

    resp = client_as(alice).patch(
        f"/orgs/{org_id}/projects/{project_id}/tasks/{task_id}", json={"status": "done"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"

    tasks = client_as(alice).get(f"/orgs/{org_id}/projects/{project_id}/tasks").json()
    assert tasks[0]["status"] == "done"


@pytest.mark.asyncio
async def test_employee_can_update_task_but_not_delete(clean_db):
    pool = clean_db
    owner = await create_auth_user(pool)
    employee = await create_auth_user(pool)
    org_id = await _make_org_with_admin(pool, owner)
    await pool.execute(
        "insert into memberships (org_id, user_id, role) values ($1, $2, 'employee')", org_id, employee
    )
    project_id = client_as(owner).post(f"/orgs/{org_id}/projects", json={"name": "P"}).json()["id"]
    task_id = client_as(employee).post(
        f"/orgs/{org_id}/projects/{project_id}/tasks", json={"title": "T"}
    ).json()["id"]

    update = client_as(employee).patch(
        f"/orgs/{org_id}/projects/{project_id}/tasks/{task_id}", json={"status": "in_progress"}
    )
    assert update.status_code == 200

    delete = client_as(employee).delete(f"/orgs/{org_id}/projects/{project_id}/tasks/{task_id}")
    assert delete.status_code == 403


@pytest.mark.asyncio
async def test_delete_task_removes_it(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    org_id = await _make_org_with_admin(pool, alice)
    project_id = client_as(alice).post(f"/orgs/{org_id}/projects", json={"name": "P"}).json()["id"]
    task_id = client_as(alice).post(
        f"/orgs/{org_id}/projects/{project_id}/tasks", json={"title": "T"}
    ).json()["id"]

    resp = client_as(alice).delete(f"/orgs/{org_id}/projects/{project_id}/tasks/{task_id}")
    assert resp.status_code == 204

    tasks = client_as(alice).get(f"/orgs/{org_id}/projects/{project_id}/tasks").json()
    assert tasks == []


@pytest.mark.asyncio
async def test_update_nonexistent_task_404s(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    org_id = await _make_org_with_admin(pool, alice)
    project_id = client_as(alice).post(f"/orgs/{org_id}/projects", json={"name": "P"}).json()["id"]

    import uuid

    resp = client_as(alice).patch(
        f"/orgs/{org_id}/projects/{project_id}/tasks/{uuid.uuid4()}", json={"status": "done"}
    )
    assert resp.status_code == 404
