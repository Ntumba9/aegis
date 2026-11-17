"""API6:2023 - Unrestricted Access to Sensitive Business Flows.

The vulnerable coupon-redemption endpoint can be called with the same
code over and over, crediting the wallet every time — a classic
"redeem this coupon as many times as you like" business-logic abuse.
The hardened endpoint enforces single-use-per-user via a unique
constraint on (username, code).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_lab_user
from app.db import get_pool

router = APIRouter(tags=["api6-business-flows"])

COUPON_VALUE = 10
FLAG_THRESHOLD = 100


class RedeemRequest(BaseModel):
    code: str


@router.post("/vulnerable/coupons/redeem")
async def redeem_vulnerable(body: RedeemRequest, user: dict = Depends(get_current_lab_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "insert into wallets (username, balance) values ($1, 0) on conflict do nothing",
                user["sub"],
            )
            # BUG: no check for a prior redemption of this exact code by this user.
            await conn.execute(
                "update wallets set balance = balance + $1 where username = $2",
                COUPON_VALUE,
                user["sub"],
            )
            # on conflict do nothing: the table's (username, code) primary key
            # would otherwise turn the replay into a 500 instead of the bug.
            await conn.execute(
                "insert into coupon_redemptions (username, code) values ($1, $2) "
                "on conflict do nothing",
                user["sub"],
                body.code,
            )
            row = await conn.fetchrow(
                "select balance from wallets where username = $1", user["sub"]
            )
    return {"balance": row["balance"]}


@router.post("/hardened/coupons/redeem")
async def redeem_hardened(body: RedeemRequest, user: dict = Depends(get_current_lab_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "insert into wallets (username, balance) values ($1, 0) on conflict do nothing",
                user["sub"],
            )
            existing = await conn.fetchrow(
                "select 1 from coupon_redemptions where username = $1 and code = $2",
                user["sub"],
                body.code,
            )
            if existing is not None:
                raise HTTPException(status_code=409, detail="Coupon already redeemed")
            await conn.execute(
                "update wallets set balance = balance + $1 where username = $2",
                COUPON_VALUE,
                user["sub"],
            )
            await conn.execute(
                "insert into coupon_redemptions (username, code) values ($1, $2)",
                user["sub"],
                body.code,
            )
            row = await conn.fetchrow(
                "select balance from wallets where username = $1", user["sub"]
            )
    return {"balance": row["balance"]}


@router.get("/vulnerable/wallet/flag")
@router.get("/hardened/wallet/flag")
async def wallet_flag(user: dict = Depends(get_current_lab_user)):
    pool = await get_pool()
    row = await pool.fetchrow("select balance from wallets where username = $1", user["sub"])
    balance = row["balance"] if row else 0
    if balance < FLAG_THRESHOLD:
        raise HTTPException(status_code=403, detail=f"Balance {balance} below {FLAG_THRESHOLD}")
    flag_row = await pool.fetchrow(
        "select flag from challenge_flags where challenge_id = 'api6-sensitive-flows-coupon-replay'"
    )
    return {"flag": flag_row["flag"] if flag_row else None}
