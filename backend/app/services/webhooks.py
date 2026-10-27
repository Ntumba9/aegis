"""Signed webhook delivery with replay protection and bounded retries.

Signature: HMAC-SHA256 over `{timestamp}.{body}` using the org's signing
secret, sent as `X-Aegis-Signature: t={ts},v1={hex}`. Receivers must reject
any timestamp older than 5 minutes to prevent replay.
"""
import hashlib
import hmac
import time

import httpx

MAX_RETRIES = 5
RETRY_BACKOFF_SECONDS = [1, 5, 15, 60, 300]
REPLAY_WINDOW_SECONDS = 300


def sign_payload(secret: str, body: bytes, timestamp: int | None = None) -> str:
    ts = timestamp or int(time.time())
    signed = f"{ts}.{body.decode()}".encode()
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def verify_signature(secret: str, body: bytes, header: str) -> bool:
    try:
        parts = dict(p.split("=", 1) for p in header.split(","))
        ts = int(parts["t"])
        received_digest = parts["v1"]
    except (ValueError, KeyError):
        return False

    if abs(time.time() - ts) > REPLAY_WINDOW_SECONDS:
        return False  # stale or future-dated -> reject (replay protection)

    expected = hmac.new(secret.encode(), f"{ts}.{body.decode()}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_digest)


async def deliver(url: str, secret: str, payload: dict, max_retries: int = MAX_RETRIES) -> bool:
    """`max_retries=1` is used for interactive "send a test event" calls,
    where a caller waiting on an HTTP response can't sit through the full
    backoff schedule meant for a background delivery queue."""
    import json

    body = json.dumps(payload).encode()
    headers = {"X-Aegis-Signature": sign_payload(secret, body), "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=5.0) as client:
        for attempt in range(max_retries):
            try:
                resp = await client.post(url, content=body, headers=headers)
                if resp.status_code < 300:
                    return True
            except httpx.HTTPError:
                pass
            if attempt < max_retries - 1:
                import asyncio

                await asyncio.sleep(RETRY_BACKOFF_SECONDS[attempt])
    return False
