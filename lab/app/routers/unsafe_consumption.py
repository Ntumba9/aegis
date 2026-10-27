"""API10:2023 - Unsafe Consumption of APIs.

The vulnerable pricing endpoint calls a "third-party" discount service
(lab-internal-mock) and applies whatever `discount_percent` it returns
with zero validation — including values far outside a sane [0, 100]
range, which an attacker can drive by passing their own
`discount_percent` straight through. The hardened endpoint clamps the
third party's response to a safe range before ever using it.
"""
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_lab_user
from app.db import get_pool

router = APIRouter(tags=["api10-unsafe-consumption"])

INTERNAL_MOCK_URL = os.environ.get("LAB_INTERNAL_MOCK_URL", "http://lab-internal-mock:9000")
BASE_PRICE = 100.0


class QuoteRequest(BaseModel):
    discount_percent_requested: float = 0


@router.post("/vulnerable/pricing/quote")
async def pricing_quote_vulnerable(body: QuoteRequest, user: dict = Depends(get_current_lab_user)):
    async with httpx.AsyncClient(timeout=3.0) as client:
        resp = await client.get(
            f"{INTERNAL_MOCK_URL}/latest/pricing",
            params={"discount_percent": body.discount_percent_requested},
        )
    upstream = resp.json()
    discount = upstream["discount_percent"]  # BUG: trusted with no bounds check
    final_price = BASE_PRICE - (BASE_PRICE * discount / 100)

    result = {"base_price": BASE_PRICE, "discount_percent": discount, "final_price": final_price}
    if final_price <= 0:
        pool = await get_pool()
        row = await pool.fetchrow(
            "select flag from challenge_flags where challenge_id = 'api10-unsafe-consumption-pricing'"
        )
        result["flag"] = row["flag"] if row else None
    return result


@router.post("/hardened/pricing/quote")
async def pricing_quote_hardened(body: QuoteRequest, user: dict = Depends(get_current_lab_user)):
    async with httpx.AsyncClient(timeout=3.0) as client:
        resp = await client.get(
            f"{INTERNAL_MOCK_URL}/latest/pricing",
            params={"discount_percent": body.discount_percent_requested},
        )
    upstream = resp.json()
    # FIXED: never trust the upstream response blindly — validate and clamp it.
    raw_discount = upstream.get("discount_percent", 0)
    if not isinstance(raw_discount, (int, float)):
        raise HTTPException(status_code=502, detail="Upstream returned a non-numeric discount")
    discount = max(0.0, min(80.0, float(raw_discount)))
    final_price = BASE_PRICE - (BASE_PRICE * discount / 100)
    return {"base_price": BASE_PRICE, "discount_percent": discount, "final_price": final_price}
