"""API-layer integration test for /orgs. Mainly covers GET /orgs/mine,
which was missing entirely until this change — every other collection
endpoint in this codebase (/teams/mine, /classrooms/mine) had one."""
import pytest

from tests.integration.conftest import create_auth_user
from tests.integration.helpers import client_as

pytestmark = pytest.mark.usefixtures("clean_db")


@pytest.mark.asyncio
async def test_my_orgs_lists_only_orgs_you_belong_to(clean_db):
    pool = clean_db
    alice = await create_auth_user(pool)
    bob = await create_auth_user(pool)

    created = client_as(alice).post("/orgs", json={"name": "Alice Corp"})
    assert created.status_code == 201

    alice_orgs = client_as(alice).get("/orgs/mine").json()
    assert len(alice_orgs) == 1
    assert alice_orgs[0]["name"] == "Alice Corp"

    bob_orgs = client_as(bob).get("/orgs/mine").json()
    assert bob_orgs == []
