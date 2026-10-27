"""Secure document upload/download, backed by Supabase Storage.

Storage calls go through app/services/storage.py so tests can monkeypatch
them — this repo has no real Supabase project to upload to in CI, so the
integration tests cover the database side (ownership, listing, deletion)
with storage.upload/get_signed_url/delete mocked, not the actual Storage
API call itself.
"""
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.auth import CurrentUser, RequireRole
from app.db.session import get_pool
from app.schemas.documents import DocumentOut, DownloadUrlOut
from app.services import storage

router = APIRouter(prefix="/orgs/{org_id}/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25MB cap — unbounded uploads are exactly the
# API4 resource-consumption lesson the lab teaches, applied here for real.


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    org_id: UUID,
    file: UploadFile = File(...),
    project_id: UUID | None = None,
    user: CurrentUser = Depends(RequireRole("employee")),
):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 25MB upload limit")

    pool = await get_pool()
    if project_id is not None:
        project = await pool.fetchrow(
            "select id from projects where id = $1 and org_id = $2", project_id, org_id
        )
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

    storage_path = f"{org_id}/{uuid4()}-{file.filename}"
    content_type = file.content_type or "application/octet-stream"
    storage.upload(storage_path, data, content_type)

    row = await pool.fetchrow(
        "insert into documents (org_id, project_id, storage_path, filename, content_type, size_bytes, uploaded_by) "
        "values ($1, $2, $3, $4, $5, $6, $7) "
        "returning id, org_id, project_id, filename, content_type, size_bytes, created_at",
        org_id,
        project_id,
        storage_path,
        file.filename,
        content_type,
        len(data),
        user.id,
    )
    return dict(row)


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    org_id: UUID, project_id: UUID | None = None, user: CurrentUser = Depends(RequireRole("employee"))
):
    pool = await get_pool()
    if project_id is not None:
        rows = await pool.fetch(
            "select id, org_id, project_id, filename, content_type, size_bytes, created_at "
            "from documents where org_id = $1 and project_id = $2 order by created_at desc",
            org_id,
            project_id,
        )
    else:
        rows = await pool.fetch(
            "select id, org_id, project_id, filename, content_type, size_bytes, created_at "
            "from documents where org_id = $1 order by created_at desc",
            org_id,
        )
    return [dict(r) for r in rows]


@router.get("/{document_id}/download", response_model=DownloadUrlOut)
async def download_document(
    org_id: UUID, document_id: UUID, user: CurrentUser = Depends(RequireRole("employee"))
):
    pool = await get_pool()
    row = await pool.fetchrow(
        "select storage_path from documents where id = $1 and org_id = $2", document_id, org_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DownloadUrlOut(download_url=storage.get_signed_url(row["storage_path"]))


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    org_id: UUID, document_id: UUID, user: CurrentUser = Depends(RequireRole("admin"))
):
    pool = await get_pool()
    row = await pool.fetchrow(
        "select storage_path from documents where id = $1 and org_id = $2", document_id, org_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    storage.delete(row["storage_path"])
    await pool.execute("delete from documents where id = $1", document_id)
