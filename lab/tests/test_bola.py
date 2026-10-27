"""Vulnerable-vs-hardened regression test for API1 BOLA.
Requires the lab stack running: docker compose up -d lab-db lab-api
    pytest lab/tests/test_bola.py
"""
import os

import httpx
import pytest

LAB_URL = os.environ.get("LAB_BASE_URL", "http://localhost:8100")


def _login(username: str, password: str) -> str:
    resp = httpx.post(f"{LAB_URL}/auth/login", json={"username": username, "password": password})
    resp.raise_for_status()
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def bob_token():
    return _login("bob", "lab-password-bob")


def test_vulnerable_endpoint_leaks_other_users_project(bob_token):
    headers = {"Authorization": f"Bearer {bob_token}"}
    # Bob (user_id=2) requests Alice's project (id=1) through the vulnerable route.
    resp = httpx.get(f"{LAB_URL}/vulnerable/projects/1", headers=headers)
    assert resp.status_code == 200
    assert "owner_id" in resp.json()
    assert resp.json()["owner_id"] == 1  # Alice's data, served to Bob: the bug


def test_hardened_endpoint_blocks_cross_user_access(bob_token):
    headers = {"Authorization": f"Bearer {bob_token}"}
    resp = httpx.get(f"{LAB_URL}/hardened/projects/1", headers=headers)
    assert resp.status_code == 403
