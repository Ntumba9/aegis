"""Shared helpers for API-layer integration tests (as opposed to the
direct-SQL RLS tests in test_rls_tenant_isolation.py).

These exercise the real FastAPI app end-to-end — routing, Pydantic
validation, the app's own authorization checks — against the same test
Postgres instance as the RLS tests, via `app.db.session.get_pool()`
pointed at it by the `bind_app_db_pool` fixture in conftest.py.

The app runs on its own dedicated event loop (a background thread) so the
asyncpg pool it uses always lives on the loop that serves requests. A sync
TestClient inside an async test cannot do this: it spins up a fresh loop
per request, which cannot reuse a pool created on another loop.
"""
import asyncio
import threading
from uuid import UUID

import httpx

from app.core.auth import CurrentUser, get_current_principal, get_current_user
from app.main import app as fastapi_app

_app_loop = asyncio.new_event_loop()
threading.Thread(target=_app_loop.run_forever, daemon=True, name="app-loop").start()


def run_in_app_loop(coro):
    """Runs a coroutine on the app's loop and blocks for its result."""
    return asyncio.run_coroutine_threadsafe(coro, _app_loop).result()


class SyncAppClient:
    """Minimal sync client (get/post/patch/put/delete) over the ASGI app,
    returning httpx.Response objects like TestClient did.

    `raise_app_exceptions=False` makes an unhandled app exception come back
    as the 500 response a real client would see, instead of re-raising it
    into the test (used by the fuzz test, which asserts on status codes)."""

    def __init__(self, raise_app_exceptions: bool = True):
        self.raise_app_exceptions = raise_app_exceptions

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        async def _go() -> httpx.Response:
            transport = httpx.ASGITransport(
                app=fastapi_app, raise_app_exceptions=self.raise_app_exceptions
            )
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
                return await c.request(method, url, **kwargs)

        return run_in_app_loop(_go())

    def get(self, url: str, **kw) -> httpx.Response:
        return self.request("GET", url, **kw)

    def post(self, url: str, **kw) -> httpx.Response:
        return self.request("POST", url, **kw)

    def patch(self, url: str, **kw) -> httpx.Response:
        return self.request("PATCH", url, **kw)

    def put(self, url: str, **kw) -> httpx.Response:
        return self.request("PUT", url, **kw)

    def delete(self, url: str, **kw) -> httpx.Response:
        return self.request("DELETE", url, **kw)


def client_as(user_id: UUID) -> SyncAppClient:
    """Returns a client whose `get_current_user` dependency is overridden to
    this user — standing in for a real Supabase JWT without needing to mint
    one. Overrides are global on the app object, so tests using this must
    run sequentially (they already do, under pytest)."""

    def _override() -> CurrentUser:
        return CurrentUser(id=user_id, email=None)

    fastapi_app.dependency_overrides[get_current_user] = _override
    # Endpoints accepting either identity depend on get_current_principal;
    # override it too so client_as keeps working for them.
    fastapi_app.dependency_overrides[get_current_principal] = _override
    return SyncAppClient()
