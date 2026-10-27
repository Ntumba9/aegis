"""Request logging + security-event capture.

Every request is written to `request_logs` (used by the "API requests"
metric on the Blue Team dashboard). A response with status 401, 403, or
429 additionally gets a row in `security_events` — this is the single
place that notices "someone failed to authenticate", "someone was denied
by an authorization check", or "someone hit a rate limit", so individual
route handlers don't each need their own audit-logging call for the
common cases.
"""
import json
import time
from uuid import UUID

from fastapi import Request
from jose import jwt
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.db.session import get_pool

_STATUS_TO_EVENT = {
    401: ("auth_failure", "warning"),
    403: ("authorization_denied", "warning"),
    429: ("rate_limit_exceeded", "warning"),
}


def _try_extract_actor_id(request: Request) -> UUID | None:
    """Best-effort: pull the subject out of the bearer token even if it's
    expired/invalid, purely for attribution on a security event — this is
    never used as an authorization decision."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header[7:]
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_exp": False, "verify_aud": False},
        )
        return UUID(payload["sub"]) if "sub" in payload else None
    except Exception:
        return None


class SecurityLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        latency_ms = int((time.monotonic() - start) * 1000)

        org_id_raw = request.path_params.get("org_id")
        org_id = None
        if org_id_raw:
            try:
                org_id = UUID(str(org_id_raw))
            except ValueError:
                org_id = None

        try:
            pool = await get_pool()
            await pool.execute(
                "insert into request_logs (org_id, method, path, status_code, latency_ms) "
                "values ($1, $2, $3, $4, $5)",
                org_id,
                request.method,
                request.url.path,
                response.status_code,
                latency_ms,
            )

            event = _STATUS_TO_EVENT.get(response.status_code)
            if event is not None:
                event_type, severity = event
                actor_id = _try_extract_actor_id(request)
                await pool.execute(
                    "insert into security_events (org_id, actor_id, event_type, severity, metadata) "
                    "values ($1, $2, $3, $4, $5)",
                    org_id,
                    actor_id,
                    event_type,
                    severity,
                    json.dumps({"method": request.method, "path": request.url.path}),
                )
        except Exception:
            # Logging must never break the actual request/response cycle —
            # e.g. if the DB pool isn't configured yet (unit tests without
            # DATABASE_URL), silently skip rather than 500 every request.
            pass

        return response
