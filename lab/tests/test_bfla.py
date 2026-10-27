import os

import httpx
import pytest

LAB_URL = os.environ.get("LAB_BASE_URL", "http://localhost:8100")


@pytest.fixture(scope="module")
def bob_token():
    resp = httpx.post(f"{LAB_URL}/auth/login", json={"username": "bob", "password": "lab-password-bob"})
    resp.raise_for_status()
    return resp.json()["access_token"]


def test_vulnerable_broadcast_allows_non_admin(bob_token):
    headers = {"Authorization": f"Bearer {bob_token}"}
    resp = httpx.post(f"{LAB_URL}/vulnerable/admin/broadcast", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["flag"]


def test_hardened_broadcast_blocks_non_admin(bob_token):
    headers = {"Authorization": f"Bearer {bob_token}"}
    resp = httpx.post(f"{LAB_URL}/hardened/admin/broadcast", headers=headers)
    assert resp.status_code == 403
