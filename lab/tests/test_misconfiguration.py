import os

import httpx

LAB_URL = os.environ.get("LAB_BASE_URL", "http://localhost:8100")


def test_vulnerable_endpoint_leaks_internal_secret_on_bad_input():
    resp = httpx.get(f"{LAB_URL}/vulnerable/items/not-a-number")
    assert resp.status_code == 500
    assert "internal_debug_secret" in resp.json()
    assert resp.json()["internal_debug_secret"].startswith("AEGIS{")


def test_hardened_endpoint_returns_generic_error():
    resp = httpx.get(f"{LAB_URL}/hardened/items/not-a-number")
    assert resp.status_code == 422
    assert "internal_debug_secret" not in resp.json()
