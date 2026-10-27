import os

import httpx
import pytest

LAB_URL = os.environ.get("LAB_BASE_URL", "http://localhost:8100")


@pytest.fixture(scope="module")
def alice_token():
    resp = httpx.post(f"{LAB_URL}/auth/login", json={"username": "alice", "password": "lab-password-alice"})
    resp.raise_for_status()
    return resp.json()["access_token"]


def test_vulnerable_export_has_no_upper_bound(alice_token):
    headers = {"Authorization": f"Bearer {alice_token}"}
    resp = httpx.get(f"{LAB_URL}/vulnerable/export", headers=headers, params={"limit": 1000})
    assert resp.status_code == 200
    assert resp.json()["count"] == 501  # the full seeded dataset, including the sensitive record


def test_hardened_export_caps_at_50(alice_token):
    headers = {"Authorization": f"Bearer {alice_token}"}
    resp = httpx.get(f"{LAB_URL}/hardened/export", headers=headers, params={"limit": 1000})
    assert resp.status_code == 200
    assert resp.json()["count"] == 50
    assert resp.json()["limit_applied"] == 50


def test_hardened_export_rate_limits_repeated_calls(alice_token):
    headers = {"Authorization": f"Bearer {alice_token}"}
    statuses = [
        httpx.get(f"{LAB_URL}/hardened/export", headers=headers).status_code for _ in range(8)
    ]
    assert 429 in statuses
