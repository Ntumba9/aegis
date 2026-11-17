"""Instructor features: classrooms, student invitations, challenge
assignments, and completion/progress reporting.

Any authenticated user can create a classroom (and thereby becomes its
instructor) — there's no separate global "instructor" role. Authorization
below is instead scoped per-classroom: only `instructor_id` may manage it,
mirroring supabase/migrations/0005_challenge_platform_rls.sql's
`is_classroom_instructor`, re-implemented explicitly here because the
backend connects with a service-role-equivalent connection and bypasses RLS.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import CurrentUser, get_current_user
from app.db.session import get_pool
from app.schemas.classrooms import (
    AssignmentCreate,
    AssignmentOut,
    ClassroomCreate,
    ClassroomOut,
    StudentOut,
    StudentProgressOut,
)

router = APIRouter(prefix="/classrooms", tags=["classrooms"])

# Invite tokens live in the classroom_invites table (migration 0008): only a
# SHA-256 of the token is stored, tokens expire, and each can be used once.
INVITE_TTL = timedelta(hours=72)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def consume_invite(conn: asyncpg.Connection, token: str, user_id: UUID) -> UUID | None:
    """Atomically marks an unused, unexpired invite as used and returns its
    classroom id, or None if the token is unknown, expired or already used.
    A single UPDATE ... WHERE used_at IS NULL, so two concurrent accepts of
    the same token cannot both succeed."""
    row = await conn.fetchrow(
        "update classroom_invites set used_at = now(), used_by = $2 "
        "where token_hash = $1 and used_at is null and expires_at > now() "
        "returning classroom_id",
        _hash_token(token),
        user_id,
    )
    return row["classroom_id"] if row else None


async def _require_instructor(pool, classroom_id: UUID, user_id: UUID) -> None:
    row = await pool.fetchrow(
        "select 1 from classrooms where id = $1 and instructor_id = $2", classroom_id, user_id
    )
    if row is None:
        raise HTTPException(status_code=403, detail="Not the instructor of this classroom")


@router.post("", response_model=ClassroomOut, status_code=201)
async def create_classroom(body: ClassroomCreate, user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    row = await pool.fetchrow(
        "insert into classrooms (name, instructor_id) values ($1, $2) "
        "returning id, name, instructor_id, created_at",
        body.name,
        user.id,
    )
    return dict(row)


@router.get("/mine", response_model=list[ClassroomOut])
async def my_classrooms(user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    rows = await pool.fetch(
        "select id, name, instructor_id, created_at from classrooms where instructor_id = $1",
        user.id,
    )
    return [dict(r) for r in rows]


@router.post("/{classroom_id}/invites", status_code=201)
async def create_invite(classroom_id: UUID, user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    await _require_instructor(pool, classroom_id, user.id)
    token = secrets.token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + INVITE_TTL
    await pool.execute(
        "insert into classroom_invites (classroom_id, token_hash, created_by, expires_at) "
        "values ($1, $2, $3, $4)",
        classroom_id,
        _hash_token(token),
        user.id,
        expires_at,
    )
    return {"invite_token": token, "expires_at": expires_at.isoformat()}


@router.post("/invites/{token}/accept", response_model=StudentOut, status_code=201)
async def accept_invite(token: str, user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        # One transaction: if joining the classroom fails, the token is not burned.
        async with conn.transaction():
            classroom_id = await consume_invite(conn, token, user.id)
            if classroom_id is None:
                raise HTTPException(
                    status_code=404, detail="Invite not found, expired, or already used"
                )
            row = await conn.fetchrow(
                "insert into classroom_students (classroom_id, student_id) values ($1, $2) "
                "on conflict (classroom_id, student_id) do nothing "
                "returning classroom_id, student_id, joined_at",
                classroom_id,
                user.id,
            )
            if row is None:
                row = await conn.fetchrow(
                    "select classroom_id, student_id, joined_at from classroom_students "
                    "where classroom_id = $1 and student_id = $2",
                    classroom_id,
                    user.id,
                )
    return dict(row)


@router.get("/{classroom_id}/students", response_model=list[StudentOut])
async def list_students(classroom_id: UUID, user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    await _require_instructor(pool, classroom_id, user.id)
    rows = await pool.fetch(
        "select classroom_id, student_id, joined_at from classroom_students where classroom_id = $1",
        classroom_id,
    )
    return [dict(r) for r in rows]


@router.post("/{classroom_id}/assignments", response_model=AssignmentOut, status_code=201)
async def create_assignment(
    classroom_id: UUID, body: AssignmentCreate, user: CurrentUser = Depends(get_current_user)
):
    pool = await get_pool()
    await _require_instructor(pool, classroom_id, user.id)
    row = await pool.fetchrow(
        "insert into classroom_assignments (classroom_id, challenge_id, due_at) values ($1, $2, $3) "
        "returning id, classroom_id, challenge_id, due_at, created_at",
        classroom_id,
        body.challenge_id,
        body.due_at,
    )
    return dict(row)


@router.get("/{classroom_id}/assignments", response_model=list[AssignmentOut])
async def list_assignments(classroom_id: UUID, user: CurrentUser = Depends(get_current_user)):
    pool = await get_pool()
    row = await pool.fetchrow(
        "select 1 from classrooms where id = $1 and instructor_id = $2", classroom_id, user.id
    )
    if row is None:
        student_row = await pool.fetchrow(
            "select 1 from classroom_students where classroom_id = $1 and student_id = $2",
            classroom_id,
            user.id,
        )
        if student_row is None:
            raise HTTPException(status_code=403, detail="Not a member of this classroom")
    rows = await pool.fetch(
        "select id, classroom_id, challenge_id, due_at, created_at from classroom_assignments "
        "where classroom_id = $1 order by created_at desc",
        classroom_id,
    )
    return [dict(r) for r in rows]


@router.get("/{classroom_id}/progress", response_model=list[StudentProgressOut])
async def classroom_progress(classroom_id: UUID, user: CurrentUser = Depends(get_current_user)):
    """Completion report: every student's progress on every assigned
    challenge. Instructor-only — this is the privacy boundary: a student
    can see their own progress via /challenges/progress/me, not everyone
    else's."""
    pool = await get_pool()
    await _require_instructor(pool, classroom_id, user.id)
    rows = await pool.fetch(
        """
        select cs.student_id, ca.challenge_id,
               coalesce(up.status, 'not_started') as status,
               coalesce(up.points_awarded, 0) as points_awarded,
               up.completed_at
        from classroom_students cs
        cross join classroom_assignments ca
        left join user_progress up on up.user_id = cs.student_id and up.challenge_id = ca.challenge_id
        where cs.classroom_id = $1 and ca.classroom_id = $1
        order by cs.student_id, ca.challenge_id
        """,
        classroom_id,
    )
    return [dict(r) for r in rows]
