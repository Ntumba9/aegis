"""Vulnerable-vs-hardened regression test for API7 SSRF.
Requires the full lab stack (lab-api + lab-internal-mock on lab-net).
"""
import os

import httpx
import pytest

LAB_URL = os.environ.get("LAB_BASE_URL", "http://localhost:8100")
INTERNAL_URL = "http://lab-internal-mock:9000/latest/internal-secret"


@pytest.fixture(scope="module")
def alice_token():
    resp = httpx.post(f"{LAB_URL}/auth/login", json={"username": "alice", "password": "lab-password-alice"})
    resp.raise_for_status()
    return resp.json()["access_token"]


def test_vulnerable_preview_reaches_internal_service(alice_token):
    headers = {"Authorization": f"Bearer {alice_token}"}
    resp = httpx.post(
        f"{LAB_URL}/vulnerable/url-preview", headers=headers, json={"url": INTERNAL_URL}
    )
    assert resp.status_code == 200
    assert "secret" in resp.json()["body"]


def test_hardened_preview_rejects_internal_service(alice_token):
    headers = {"Authorization": f"Bearer {alice_token}"}
    resp = httpx.post(
        f"{LAB_URL}/hardened/url-preview", headers=headers, json={"url": INTERNAL_URL}
    )
    assert resp.status_code == 403
