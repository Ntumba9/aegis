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

schema = schemathesis.openapi.from_asgi("/openapi.json", app)


@schema.parametrize()
@settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_no_unhandled_server_errors(case):
    response = case.call_asgi()
    assert response.status_code < 500, (
        f"{case.method} {case.path} returned {response.status_code} "
        f"(an unhandled server error) for generated input {case.path_parameters}, "
        f"{case.query}, body={case.body!r}: {response.text[:500]}"
    )
