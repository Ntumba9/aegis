"""Supabase JWT verification and tenant/role-scoped auth dependencies.

Every protected route depends on `get_current_user`, which verifies the
Supabase-issued JWT signature and expiry locally (no network round-trip).
Org membership and role are then resolved server-side from the database —
never trusted from client-supplied headers or body fields.
"""
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=True)


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str | None


def decode_supabase_jwt(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    payload = decode_supabase_jwt(credentials.credentials)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing subject")
    return CurrentUser(id=UUID(sub), email=payload.get("email"))


class RequireRole:
    """Dependency factory enforcing a minimum org role for the active org.

    Resolves membership from the database (see app.services.memberships),
    never from a client-supplied org/role claim, which closes the classic
    API5 (Broken Function Level Authorization) and API1 (BOLA) gaps.
    """

    _RANK = {"employee": 0, "admin": 1, "owner": 2}

    def __init__(self, minimum: str):
        self.minimum = minimum

    async def __call__(
        self,
        org_id: UUID,
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        from app.services.memberships import get_role_for_user  # lazy import avoids cycle

        role = await get_role_for_user(org_id=org_id, user_id=user.id)
        if role is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        if self._RANK[role] < self._RANK[self.minimum]:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user



API_KEY_PREFIX = "aegis_"


@dataclass(frozen=True)
class ApiKeyPrincipal:
    """An authenticated org API key. Carries no user identity — access is
    scoped to the key's org and its scopes list. Resolved by SHA-256 hash;
    the plaintext key is never stored or logged."""

    key_id: UUID
    org_id: UUID
    scopes: tuple[str, ...]


async def authenticate_api_key(token: str) -> ApiKeyPrincipal | None:
    """Resolves a plaintext `aegis_...` key to its principal. Returns None
    for unknown and revoked keys alike, so callers cannot distinguish them.
    Stamps `last_used_at` on success — that is the only write a read-scoped
    key can ever cause."""
    import hashlib

    from app.db.session import get_pool

    digest = hashlib.sha256(token.encode()).hexdigest()
    pool = await get_pool()
    row = await pool.fetchrow(
        "select id, org_id, scopes from api_keys where key_hash = $1 and revoked_at is null",
        digest,
    )
    if row is None:
        return None
    await pool.execute("update api_keys set last_used_at = now() where id = $1", row["id"])
    return ApiKeyPrincipal(
        key_id=row["id"], org_id=row["org_id"], scopes=tuple(row["scopes"] or ())
    )


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser | ApiKeyPrincipal:
    """Like `get_current_user`, but also accepts org API keys
    (`Authorization: Bearer aegis_...`). Used by read-only endpoints via
    `RequireReadAccess`. Every other endpoint keeps `RequireRole`, which
    only accepts a user identity — an API key presented there fails JWT
    decoding and gets the same 401 as any invalid token."""
    token = credentials.credentials
    if token.startswith(API_KEY_PREFIX):
        principal = await authenticate_api_key(token)
        if principal is None:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key")
        return principal
    return get_current_user(credentials)


class RequireReadAccess:
    """Read-only org access for either credential type:

    - Org API key: must be active, belong to this org, and carry the
      "read" scope. No user identity is involved.
    - Supabase JWT: the same membership/role rule as `RequireRole(minimum)`.

    Existence-hiding matches `RequireRole`: a key belonging to another org
    and a non-member JWT both answer 404, while a valid credential that is
    merely underprivileged (missing scope / too-low role) answers 403.
    """

    def __init__(self, minimum: str = "employee"):
        self._require_role = RequireRole(minimum)

    async def __call__(
        self,
        org_id: UUID,
        principal: CurrentUser | ApiKeyPrincipal = Depends(get_current_principal),
    ) -> CurrentUser | ApiKeyPrincipal:
        if isinstance(principal, ApiKeyPrincipal):
            if principal.org_id != org_id:
                raise HTTPException(status_code=404, detail="Organization not found")
            if "read" not in principal.scopes:
                raise HTTPException(
                    status_code=403, detail="API key missing required scope: read"
                )
            return principal
        return await self._require_role(org_id=org_id, user=principal)
