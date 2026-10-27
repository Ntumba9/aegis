import os

import httpx

LAB_URL = os.environ.get("LAB_BASE_URL", "http://localhost:8100")


def test_v1_export_requires_no_authentication():
    resp = httpx.get(f"{LAB_URL}/v1/internal/export")
    assert resp.status_code == 200
    assert resp.json()["flag"]


def test_v2_export_requires_authentication():
    # FastAPI's HTTPBearer(auto_error=True) rejects a missing Authorization
    # header with 403 before the route handler even runs.
    resp = httpx.get(f"{LAB_URL}/v2/internal/export")
    assert resp.status_code == 403


def test_v2_export_requires_admin_role():
    login = httpx.post(f"{LAB_URL}/auth/login", json={"username": "bob", "password": "lab-password-bob"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = httpx.get(f"{LAB_URL}/v2/internal/export", headers=headers)
    assert resp.status_code == 403
