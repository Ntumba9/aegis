"""Requires the full lab stack: lab-api + lab-internal-mock on lab-net."""
import os

import httpx
import pytest

LAB_URL = os.environ.get("LAB_BASE_URL", "http://localhost:8100")


@pytest.fixture(scope="module")
def alice_token():
    resp = httpx.post(f"{LAB_URL}/auth/login", json={"username": "alice", "password": "lab-password-alice"})
    resp.raise_for_status()
    return resp.json()["access_token"]


def test_vulnerable_quote_trusts_oversized_discount(alice_token):
    headers = {"Authorization": f"Bearer {alice_token}"}
    resp = httpx.post(
        f"{LAB_URL}/vulnerable/pricing/quote",
        headers=headers,
        json={"discount_percent_requested": 150},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["final_price"] <= 0
    assert body["flag"]


def test_hardened_quote_clamps_discount(alice_token):
    headers = {"Authorization": f"Bearer {alice_token}"}
    resp = httpx.post(
        f"{LAB_URL}/hardened/pricing/quote",
        headers=headers,
        json={"discount_percent_requested": 150},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["discount_percent"] <= 80
    assert body["final_price"] > 0
