"""Property-based API regression testing with Schemathesis.

`schemathesis` has been in requirements.txt since Milestone 1 (listed in
the original tech stack as the tool for "API security regression tests")
but was never actually wired up anywhere — this closes that gap.

It generates inputs from the app's own OpenAPI schema and asserts no
request ever produces a 500: a 401/403 (missing/invalid auth) or 422
(validation) is a correct, expected response and not a failure here —
only an unhandled server error counts. Runs against the real test
database (via the same `bind_app_db_pool` fixture every other
integration test uses) so unauthenticated routes that do hit the
database (e.g. /challenges, /leaderboard/users) get real answers instead
of failing on a missing connection.
"""
import schemathesis
from hypothesis import HealthCheck, settings

from app.main import app
from tests.integration.helpers import SyncAppClient

# FastAPI emits OpenAPI 3.1; Schemathesis 3.x only accepts it when opted in.
schemathesis.experimental.OPEN_API_3_1.enable()

schema = schemathesis.openapi.from_asgi("/openapi.json", app)


@schema.parametrize()
@settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_no_unhandled_server_errors(case):
    # Send through the shared app-loop client (not case.call_asgi(), which
    # uses a sync TestClient on a fresh loop per request and would corrupt
    # the app's asyncpg pool for every test that runs after this one).
    kwargs = case.as_requests_kwargs(base_url="http://testserver")
    kwargs.pop("timeout", None)
    # Header values that are not ASCII cannot be sent over real HTTP and
    # httpx refuses to encode them, so drop those generated headers.
    kwargs["headers"] = {
        k: v for k, v in (kwargs.get("headers") or {}).items() if str(v).isascii() and str(k).isascii()
    }
    response = SyncAppClient(raise_app_exceptions=False).request(**kwargs)
    assert response.status_code < 500, (
        f"{case.method} {case.path} returned {response.status_code} "
        f"(an unhandled server error) for generated input {case.path_parameters}, "
        f"{case.query}, body={case.body!r}: {response.text[:500]}"
    )
