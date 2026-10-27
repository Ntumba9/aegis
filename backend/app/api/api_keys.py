"""API key lifecycle. Keys are shown in plaintext exactly once (at creation)
and stored only as a SHA-256 hash thereafter — never logged, never
retrievable. Rotation issues a new key and revokes the old one atomically."""
import hashlib
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import CurrentUser, RequireRole
from app.db.session import get_pool
from app.schemas.api_keys import ApiKeyCreate, ApiKeyCreated, ApiKeyOut

router = APIRouter(prefix="/orgs/{org_id}/api-keys", tags=["api-keys"])


def _generate_key() -> tuple[str, str]:
    plaintext = f"aegis_{secrets.token_urlsafe(32)}"
    digest = hashlib.sha256(plaintext.encode()).hexdigest()
    return plaintext, digest


@router.post("", response_model=ApiKeyCreated, status_code=201)
async def create_key(
    org_id: UUID, body: ApiKeyCreate, user: CurrentUser = Depends(RequireRole("admin"))
):
    plaintext, digest = _generate_key()
    pool = await get_pool()
    row = await pool.fetchrow(
        "insert into api_keys (org_id, name, key_hash, scopes, created_by) "
        "values ($1, $2, $3, $4, $5) "
        "returning id, name, scopes, created_at",
        org_id,
        body.name,
        digest,
        body.scopes,
        user.id,
    )
    return ApiKeyCreated(plaintext_key=plaintext, **dict(row))


@router.get("", response_model=list[ApiKeyOut])
async def list_keys(org_id: UUID, user: CurrentUser = Depends(RequireRole("admin"))):
    pool = await get_pool()
    rows = await pool.fetch(
        "select id, name, scopes, last_used_at, revoked_at, created_at "
        "from api_keys where org_id = $1 order by created_at desc",
        org_id,
    )
    return [dict(r) for r in rows]


@router.post("/{key_id}/rotate", response_model=ApiKeyCreated)
async def rotate_key(
    org_id: UUID, key_id: UUID, user: CurrentUser = Depends(RequireRole("admin"))
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchrow(
                "select name, scopes from api_keys where id = $1 and org_id = $2 and revoked_at is null",
                key_id,
                org_id,
            )
            if existing is None:
                raise HTTPException(status_code=404, detail="API key not found")
            await conn.execute(
                "update api_keys set revoked_at = now() where id = $1", key_id
            )
            plaintext, digest = _generate_key()
            row = await conn.fetchrow(
                "insert into api_keys (org_id, name, key_hash, scopes, created_by) "
                "values ($1, $2, $3, $4, $5) "
                "returning id, name, scopes, created_at",
                org_id,
                existing["name"],
                digest,
                existing["scopes"],
                user.id,
            )
    return ApiKeyCreated(plaintext_key=plaintext, **dict(row))


@router.delete("/{key_id}", status_code=204)
async def revoke_key(
    org_id: UUID, key_id: UUID, user: CurrentUser = Depends(RequireRole("admin"))
):
    pool = await get_pool()
    result = await pool.execute(
        "update api_keys set revoked_at = now() "
        "where id = $1 and org_id = $2 and revoked_at is null",
        key_id,
        org_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="API key not found")
