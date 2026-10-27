"""API8:2023 - Security Misconfiguration.

The vulnerable endpoint runs with `debug`-style verbose error handling:
an unhandled exception's details, including an internal secret that
should never leave the process, are serialized straight into the HTTP
response. The hardened endpoint validates input up front and returns a
generic error with nothing internal attached.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["api8-misconfiguration"])

# Simulates a secret that would be present in real internal state
# (a config value, a connection string fragment, a stack frame local) —
# never meant to reach a client, but does, because of the bug below.
INTERNAL_DEBUG_SECRET = "AEGIS{internal-debug-secret-leaked}"


@router.get("/vulnerable/items/{item_id}")
async def get_item_vulnerable(item_id: str, request: Request):
    try:
        numeric_id = int(item_id)  # raises ValueError on non-numeric input
        return {"id": numeric_id, "name": f"Item {numeric_id}"}
    except ValueError as exc:
        # BUG: verbose/debug-style error disclosure — internal state leaks
        # straight into the response body.
        return JSONResponse(
            status_code=500,
            content={
                "error": str(exc),
                "traceback_hint": f"int() conversion failed for input {item_id!r}",
                "internal_debug_secret": INTERNAL_DEBUG_SECRET,
                "request_path": str(request.url),
            },
        )


@router.get("/hardened/items/{item_id}")
async def get_item_hardened(item_id: str):
    if not item_id.isdigit():
        # FIXED: generic client-safe error, nothing internal attached.
        return JSONResponse(status_code=422, content={"detail": "item_id must be numeric"})
    return {"id": int(item_id), "name": f"Item {item_id}"}
