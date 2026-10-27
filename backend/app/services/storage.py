"""Thin wrapper around Supabase Storage for document uploads/downloads.
Isolated behind this module (rather than called directly from
app/api/documents.py) so tests can monkeypatch upload/get_signed_url/delete
without needing a real Supabase project or network access.
"""
from supabase import Client, create_client

from app.core.config import settings

BUCKET = "documents"

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _client


def upload(path: str, data: bytes, content_type: str) -> None:
    _get_client().storage.from_(BUCKET).upload(
        path, data, {"content-type": content_type, "upsert": "false"}
    )


def get_signed_url(path: str, expires_in: int = 3600) -> str:
    result = _get_client().storage.from_(BUCKET).create_signed_url(path, expires_in)
    return result.get("signedURL") or result.get("signed_url") or result["signedUrl"]


def delete(path: str) -> None:
    _get_client().storage.from_(BUCKET).remove([path])
