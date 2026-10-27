"""API7 - SSRF challenge: vulnerable vs. hardened URL preview endpoints."""
import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_lab_user

router = APIRouter(tags=["api7-ssrf"])


class PreviewRequest(BaseModel):
    url: str


BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / cloud metadata range
    ipaddress.ip_network("::1/128"),
]

# The hardened handler's allowlist. Note it still does NOT include the
# internal mock service — only a real external destination would be
# allowlisted here in a production deployment.
ALLOWED_HOSTS = {"example.com", "httpbin.org"}


@router.post("/vulnerable/url-preview")
async def preview_vulnerable(body: PreviewRequest, user: dict = Depends(get_current_lab_user)):
    """VULNERABLE: fetches whatever URL is supplied, no destination
    validation, redirects followed automatically. This reaches
    lab-internal-mock, which should never be reachable from a user-facing
    feature."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=5.0) as client:
        try:
            resp = await client.get(body.url)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Fetch failed: {exc}") from exc
    return {"status_code": resp.status_code, "body": resp.text[:4000]}


def _is_blocked(hostname: str) -> bool:
    try:
        resolved = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(resolved)
    except (socket.gaierror, ValueError):
        return True  # fail closed: can't resolve/validate -> block
    return any(ip in net for net in BLOCKED_NETWORKS)


@router.post("/hardened/url-preview")
async def preview_hardened(body: PreviewRequest, user: dict = Depends(get_current_lab_user)):
    """HARDENED: allowlists the destination host, resolves and rejects
    private/link-local/loopback ranges, disables redirect-following, and
    enforces a short timeout and response size cap."""
    parsed = urlparse(body.url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only http/https allowed")
    if parsed.hostname not in ALLOWED_HOSTS:
        raise HTTPException(status_code=403, detail="Destination host not allowlisted")
    if _is_blocked(parsed.hostname):
        raise HTTPException(status_code=403, detail="Destination resolves to a blocked network")

    async with httpx.AsyncClient(follow_redirects=False, timeout=3.0) as client:
        try:
            resp = await client.get(body.url)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Fetch failed: {exc}") from exc
        if resp.is_redirect:
            raise HTTPException(status_code=403, detail="Redirects are not followed")
    return {"status_code": resp.status_code, "body": resp.text[:4000]}
