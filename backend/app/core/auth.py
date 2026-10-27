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
