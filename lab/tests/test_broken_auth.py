"""API2 regression test. Requires: docker compose up -d lab-db lab-api
and lab/scripts/seed.py (erin's session sess-000001 must already exist)."""
import os

import httpx

LAB_URL = os.environ.get("LAB_BASE_URL", "http://localhost:8100")


def test_vulnerable_session_readable_without_authorization():
    # No Authorization header at all — just guessing erin's predictable token.
    resp = httpx.get(f"{LAB_URL}/vulnerable/sessions/sess-000001")
    assert resp.status_code == 200
    assert resp.json()["username"] == "erin"


def test_vulnerable_flag_reachable_via_guessed_session():
    resp = httpx.get(f"{LAB_URL}/vulnerable/sessions/sess-000001/flag")
    assert resp.status_code == 200
    assert resp.json()["flag"]


def test_hardened_session_tokens_are_not_sequential():
    r1 = httpx.post(
        f"{LAB_URL}/hardened/sessions/login", json={"username": "bob", "password": "lab-password-bob"}
    )
    r2 = httpx.post(
        f"{LAB_URL}/hardened/sessions/login", json={"username": "bob", "password": "lab-password-bob"}
    )
    t1, t2 = r1.json()["session_token"], r2.json()["session_token"]
    assert t1 != t2
    assert not t1.startswith("sess-")
    assert len(t1) > 20


def test_hardened_session_requires_matching_bearer():
    login = httpx.post(
        f"{LAB_URL}/hardened/sessions/login", json={"username": "bob", "password": "lab-password-bob"}
    )
    token = login.json()["session_token"]
    # No Authorization header -> rejected outright (FastAPI's HTTPBearer
    # auto_error=True returns 403 for a missing header, 401 for an invalid one).
    resp = httpx.get(f"{LAB_URL}/hardened/sessions/{token}")
    assert resp.status_code == 403
