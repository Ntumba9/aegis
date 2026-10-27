"""API2:2023 - Broken Authentication.

The vulnerable flow issues predictable, sequential session tokens
(`sess-000001`, `sess-000002`, ...) and lets ANYONE who holds a token
string read the session it belongs to — no bearer check, no ownership
check, just "do you know the token". Since the tokens are sequential,
an attacker who logs in once can simply decrement the counter to read
sessions that were issued before them, including an administrator's.

The hardened flow issues a 128-bit random token and requires the caller
to present their own valid Authorization bearer matching the session's
owner before returning anything.
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import SYNTHETIC_USERS, get_current_lab_user, issue_token
from app.db import get_pool

router = APIRouter(tags=["api2-broken-auth"])


class LabLoginRequest(BaseModel):
    username: str
    password: str


@router.post("/vulnerable/sessions/login")
async def vulnerable_login(body: LabLoginRequest):
    user = SYNTHETIC_USERS.get(body.username)
    if user is None or user["password"] != body.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    pool = await get_pool()
    next_id = await pool.fetchval("select nextval('lab_sessions_vuln_seq')")
    token = f"sess-{next_id:06d}"  # PREDICTABLE: sequential, guessable
    await pool.execute(
        "insert into lab_sessions (token, username, mode) values ($1, $2, 'vulnerable')",
        token,
        body.username,
    )
    return {"session_token": token}


@router.get("/vulnerable/sessions/{token}")
async def vulnerable_read_session(token: str):
    """BUG: no Authorization header required at all — the token alone,
    which is trivially guessable, is treated as sufficient proof of
    identity to read ANY session's contents."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "select username from lab_sessions where token = $1 and mode = 'vulnerable'", token
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"username": row["username"], "token": token}


@router.get("/vulnerable/sessions/{token}/flag")
async def vulnerable_session_flag(token: str):
    """Reveals the flag tied to whoever owns `token` — demonstrating the
    impact: reading an admin's predictable session nets you their flag,
    no credentials of your own required."""
    pool = await get_pool()
    session = await pool.fetchrow(
        "select username from lab_sessions where token = $1 and mode = 'vulnerable'", token
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["username"] != "erin":
        raise HTTPException(status_code=400, detail="This session has no flag attached")
    flag_row = await pool.fetchrow(
        "select flag from challenge_flags where challenge_id = 'api2-broken-auth-predictable-session'"
    )
    return {"flag": flag_row["flag"] if flag_row else None}


@router.post("/hardened/sessions/login")
async def hardened_login(body: LabLoginRequest):
    user = SYNTHETIC_USERS.get(body.username)
    if user is None or user["password"] != body.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    pool = await get_pool()
    token = secrets.token_urlsafe(32)  # high-entropy, not guessable
    await pool.execute(
        "insert into lab_sessions (token, username, mode) values ($1, $2, 'hardened')",
        token,
        body.username,
    )
    return {"session_token": token, "bearer": issue_token(body.username)}


@router.get("/hardened/sessions/{token}")
async def hardened_read_session(token: str, user: dict = Depends(get_current_lab_user)):
    """FIXED: requires a valid bearer AND that the bearer's identity
    matches the session's owner — knowing the token string is no longer
    sufficient on its own."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "select username from lab_sessions where token = $1 and mode = 'hardened'", token
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if row["username"] != user["sub"]:
        raise HTTPException(status_code=403, detail="This session does not belong to you")
    return {"username": row["username"], "token": token}
