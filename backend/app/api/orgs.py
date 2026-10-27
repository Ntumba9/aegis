import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import CurrentUser, RequireRole, get_current_user
from app.db.session import get_pool
from app.schemas.orgs import InviteCreate, InviteOut, MemberOut, OrgCreate, OrgOut

router = APIRouter(prefix="/orgs", tags=["organizations"])


@router.post("", response_model=OrgOut, status_code=201)
async def create_org(body: OrgCreate, user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            org = await conn.fetchrow(
                "insert into organizations (name) values ($1) returning id, name, created_at",
                body.name,
            )
            await conn.execute(
                "insert into memberships (org_id, user_id, role) values ($1, $2, 'owner')",
                org["id"],
                user.id,
            )
    return dict(org)


@router.get("/mine", response_model=list[OrgOut])
async def my_orgs(user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    rows = await pool.fetch(
        "select o.id, o.name, o.created_at from organizations o "
        "join memberships m on m.org_id = o.id where m.user_id = $1",
        user.id,
    )
    return [dict(r) for r in rows]


@router.get("/{org_id}/members", response_model=list[MemberOut])
async def list_members(org_id: UUID, user: CurrentUser = Depends(RequireRole("employee"))):
    pool = await get_pool()
    rows = await pool.fetch(
        "select user_id, org_id, role, created_at from memberships where org_id = $1",
        org_id,
    )
    return [dict(r) for r in rows]


@router.post("/{org_id}/invites", response_model=InviteOut, status_code=201)
async def create_invite(
    org_id: UUID, body: InviteCreate, user: CurrentUser = Depends(RequireRole("admin"))
):
    pool = await get_pool()
    token = secrets.token_urlsafe(32)
    row = await pool.fetchrow(
        "insert into invitations (org_id, email, role, token, status, created_by) "
        "values ($1, $2, $3, $4, 'pending', $5) "
        "returning id, org_id, email, role, status, created_at",
        org_id,
        body.email,
        body.role,
        token,
        user.id,
    )
    # Email delivery is out of scope here; the token would be sent via a
    # transactional email provider in a production deployment.
    return dict(row)


@router.post("/invites/{token}/accept", status_code=204)
async def accept_invite(token: str, user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            invite = await conn.fetchrow(
                "select id, org_id, role, status from invitations where token = $1", token
            )
            if invite is None or invite["status"] != "pending":
                raise HTTPException(status_code=404, detail="Invite not found or already used")
            await conn.execute(
                "insert into memberships (org_id, user_id, role) values ($1, $2, $3) "
                "on conflict (org_id, user_id) do nothing",
                invite["org_id"],
                user.id,
                invite["role"],
            )
            await conn.execute(
                "update invitations set status = 'accepted' where id = $1", invite["id"]
            )
