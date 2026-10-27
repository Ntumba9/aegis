"""Project & task endpoints. Tenant isolation is enforced twice: the
WHERE org_id = $1 clause here (defense in depth) and Postgres RLS on the
underlying tables (supabase/migrations/0002_core_schema.sql)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import CurrentUser, RequireRole, get_current_user
from app.db.session import get_pool
from app.schemas.common import Page
from app.schemas.projects import (
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)

router = APIRouter(prefix="/orgs/{org_id}/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    org_id: UUID,
    page: Page = Depends(),
    user: CurrentUser = Depends(RequireRole("employee")),
):
    pool = await get_pool()
    rows = await pool.fetch(
        "select id, org_id, name, description, created_at from projects "
        "where org_id = $1 order by created_at desc limit $2 offset $3",
        org_id,
        page.limit,
        page.offset,
    )
    return [dict(r) for r in rows]


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    org_id: UUID,
    body: ProjectCreate,
    user: CurrentUser = Depends(RequireRole("admin")),
):
    pool = await get_pool()
    row = await pool.fetchrow(
        "insert into projects (org_id, name, description, created_by) "
        "values ($1, $2, $3, $4) "
        "returning id, org_id, name, description, created_at",
        org_id,
        body.name,
        body.description,
        user.id,
    )
    return dict(row)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    org_id: UUID,
    project_id: UUID,
    user: CurrentUser = Depends(RequireRole("employee")),
):
    pool = await get_pool()
    row = await pool.fetchrow(
        "select id, org_id, name, description, created_at from projects "
        "where org_id = $1 and id = $2",
        org_id,
        project_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return dict(row)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    org_id: UUID,
    project_id: UUID,
    body: ProjectUpdate,
    user: CurrentUser = Depends(RequireRole("admin")),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    pool = await get_pool()
    existing = await pool.fetchrow(
        "select id from projects where org_id = $1 and id = $2", org_id, project_id
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="Project not found")

    set_clauses = []
    values: list = []
    for i, (field, value) in enumerate(updates.items(), start=1):
        set_clauses.append(f"{field} = ${i}")
        values.append(value)
    values.append(project_id)

    row = await pool.fetchrow(
        f"update projects set {', '.join(set_clauses)} where id = ${len(values)} "
        "returning id, org_id, name, description, created_at",
        *values,
    )
    return dict(row)


@router.post("/{project_id}/tasks", response_model=TaskOut, status_code=201)
async def create_task(
    org_id: UUID,
    project_id: UUID,
    body: TaskCreate,
    user: CurrentUser = Depends(RequireRole("employee")),
):
    pool = await get_pool()
    project = await pool.fetchrow(
        "select id from projects where org_id = $1 and id = $2", org_id, project_id
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    row = await pool.fetchrow(
        "insert into tasks (project_id, title, description, assignee_id, status, created_by) "
        "values ($1, $2, $3, $4, $5, $6) "
        "returning id, project_id, title, description, assignee_id, status, created_at",
        project_id,
        body.title,
        body.description,
        body.assignee_id,
        body.status,
        user.id,
    )
    return dict(row)


@router.get("/{project_id}/tasks", response_model=list[TaskOut])
async def list_tasks(
    org_id: UUID,
    project_id: UUID,
    page: Page = Depends(),
    user: CurrentUser = Depends(RequireRole("employee")),
):
    pool = await get_pool()
    rows = await pool.fetch(
        "select t.id, t.project_id, t.title, t.description, t.assignee_id, t.status, t.created_at "
        "from tasks t join projects p on p.id = t.project_id "
        "where p.org_id = $1 and t.project_id = $2 "
        "order by t.created_at desc limit $3 offset $4",
        org_id,
        project_id,
        page.limit,
        page.offset,
    )
    return [dict(r) for r in rows]


@router.patch("/{project_id}/tasks/{task_id}", response_model=TaskOut)
async def update_task(
    org_id: UUID,
    project_id: UUID,
    task_id: UUID,
    body: TaskUpdate,
    user: CurrentUser = Depends(RequireRole("employee")),
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    pool = await get_pool()
    existing = await pool.fetchrow(
        "select t.id from tasks t join projects p on p.id = t.project_id "
        "where p.org_id = $1 and t.project_id = $2 and t.id = $3",
        org_id,
        project_id,
        task_id,
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="Task not found")

    set_clauses = []
    values: list = []
    for i, (field, value) in enumerate(updates.items(), start=1):
        set_clauses.append(f"{field} = ${i}")
        values.append(value)
    values.append(task_id)

    row = await pool.fetchrow(
        f"update tasks set {', '.join(set_clauses)} where id = ${len(values)} "
        "returning id, project_id, title, description, assignee_id, status, created_at",
        *values,
    )
    return dict(row)


@router.delete("/{project_id}/tasks/{task_id}", status_code=204)
async def delete_task(
    org_id: UUID,
    project_id: UUID,
    task_id: UUID,
    user: CurrentUser = Depends(RequireRole("admin")),
):
    pool = await get_pool()
    result = await pool.execute(
        "delete from tasks t using projects p "
        "where t.id = $1 and t.project_id = p.id and p.org_id = $2 and t.project_id = $3",
        task_id,
        org_id,
        project_id,
    )
    # asyncpg's execute() on a USING-joined DELETE still returns "DELETE N".
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Task not found")
