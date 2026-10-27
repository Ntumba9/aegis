import os

import httpx
import pytest

LAB_URL = os.environ.get("LAB_BASE_URL", "http://localhost:8100")
DAVE_ID = 4


@pytest.fixture(scope="module")
def dave_token():
    resp = httpx.post(f"{LAB_URL}/auth/login", json={"username": "dave", "password": "lab-password-dave"})
    resp.raise_for_status()
    return resp.json()["access_token"]


def test_vulnerable_patch_allows_role_escalation(dave_token):
    headers = {"Authorization": f"Bearer {dave_token}"}
    patch = httpx.patch(f"{LAB_URL}/vulnerable/users/{DAVE_ID}", headers=headers, json={"role": "admin"})
    assert patch.status_code == 200
    assert patch.json()["role"] == "admin"

    flag = httpx.get(f"{LAB_URL}/vulnerable/admin/flag", headers=headers)
    assert flag.status_code == 200
    assert flag.json()["flag"]

    # revert for test idempotency
    httpx.patch(f"{LAB_URL}/vulnerable/users/{DAVE_ID}", headers=headers, json={"role": "user"})


def test_hardened_patch_ignores_role_field(dave_token):
    headers = {"Authorization": f"Bearer {dave_token}"}
    patch = httpx.patch(
        f"{LAB_URL}/hardened/users/{DAVE_ID}", headers=headers, json={"role": "admin", "display_name": "Dave"}
    )
    assert patch.status_code == 200
    assert patch.json()["role"] == "user"  # unchanged: role is not in the allowlist

    flag = httpx.get(f"{LAB_URL}/hardened/admin/flag", headers=headers)
    assert flag.status_code == 403
