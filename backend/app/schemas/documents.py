from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: UUID
    org_id: UUID
    project_id: UUID | None
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime


class DownloadUrlOut(BaseModel):
    download_url: str
