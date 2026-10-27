"""Shared helpers for API-layer integration tests (as opposed to the
direct-SQL RLS tests in test_rls_tenant_isolation.py).

These exercise the real FastAPI app end-to-end — routing, Pydantic
validation, the app's own authorization checks — against the same test
Postgres instance as the RLS tests, via `app.db.session.get_pool()`
pointed at it by the `bind_app_db_pool` fixture below.
"""
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, get_current_user
from app.main import app as fastapi_app


def client_as(user_id: UUID) -> TestClient:
    """Returns a TestClient whose `get_current_user` dependency is
    overridden to this user — standing in for a real Supabase JWT without
    needing to mint one. Overrides are global on the app object, so tests
    using this must run sequentially (they already do, under pytest)."""

    def _override() -> CurrentUser:
        return CurrentUser(id=user_id, email=None)

    fastapi_app.dependency_overrides[get_current_user] = _override
    return TestClient(fastapi_app)
