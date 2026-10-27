import os
import uuid

import httpx
import pytest

LAB_URL = os.environ.get("LAB_BASE_URL", "http://localhost:8100")


@pytest.fixture(scope="module")
def dave_token():
    resp = httpx.post(f"{LAB_URL}/auth/login", json={"username": "dave", "password": "lab-password-dave"})
    resp.raise_for_status()
    return resp.json()["access_token"]


def test_vulnerable_coupon_can_be_replayed(dave_token):
    headers = {"Authorization": f"Bearer {dave_token}"}
    code = f"REPLAY-{uuid.uuid4().hex[:8]}"
    for _ in range(11):
        resp = httpx.post(f"{LAB_URL}/vulnerable/coupons/redeem", headers=headers, json={"code": code})
        assert resp.status_code == 200

    flag = httpx.get(f"{LAB_URL}/vulnerable/wallet/flag", headers=headers)
    assert flag.status_code == 200
    assert flag.json()["flag"]


def test_hardened_coupon_rejects_second_redemption(dave_token):
    headers = {"Authorization": f"Bearer {dave_token}"}
    code = f"ONEUSE-{uuid.uuid4().hex[:8]}"
    first = httpx.post(f"{LAB_URL}/hardened/coupons/redeem", headers=headers, json={"code": code})
    assert first.status_code == 200
    second = httpx.post(f"{LAB_URL}/hardened/coupons/redeem", headers=headers, json={"code": code})
    assert second.status_code == 409
