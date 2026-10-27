"""Instructor features: classrooms, student invitations, challenge
assignments, and completion/progress reporting.

Any authenticated user can create a classroom (and thereby becomes its
instructor) — there's no separate global "instructor" role. Authorization
below is instead scoped per-classroom: only `instructor_id` may manage it,
mirroring supabase/migrations/0005_challenge_platform_rls.sql's
`is_classroom_instructor`, re-implemented explicitly here because the
backend connects with a service-role-equivalent connection and bypasses RLS.
"""
import secrets
from uuid import UUID

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

# In-memory invite tokens -> classroom_id. Good enough for a single-process
# dev/demo deployment; a production deployment would persist these the
# same way app/api/orgs.py persists org invitations.
_invite_tokens: dict[str, UUID] = {}


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
    _invite_tokens[token] = classroom_id
    return {"invite_token": token}


@router.post("/invites/{token}/accept", response_model=StudentOut, status_code=201)
async def accept_invite(token: str, user: CurrentUser = Depends(get_current_user)):
    classroom_id = _invite_tokens.get(token)
    if classroom_id is None:
        raise HTTPException(status_code=404, detail="Invite not found or already used")
    pool = await get_pool()
    row = await pool.fetchrow(
        "insert into classroom_students (classroom_id, student_id) values ($1, $2) "
        "on conflict (classroom_id, student_id) do nothing "
        "returning classroom_id, student_id, joined_at",
        classroom_id,
        user.id,
    )
    del _invite_tokens[token]
    if row is None:
        row = await pool.fetchrow(
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
