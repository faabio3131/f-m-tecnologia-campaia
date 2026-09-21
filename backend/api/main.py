"""CAMPAIA BFF/API Starlette application.

Run with: uvicorn api.main:app --reload  (from /home/claude/campaia_verify)

Built on Starlette rather than FastAPI: FastAPI could not be installed in this sandbox
(pypi.org is blocked by the environment's network egress allowlist -- confirmed 403 via
both pip and uv). Starlette is the ASGI framework FastAPI wraps and was already available,
so this app mirrors the routing/response shape a FastAPI app would have.
"""

from __future__ import annotations

import os

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from campaia_core.errors import CampaiaError

from .csrf import CSRFMiddleware
from .errors import ApiError, from_domain_error
from .routes_approvals import create_approval, decide_approval, list_approvals
from .routes_auth import callback as auth_callback
from .routes_auth import login as auth_login
from .routes_auth import logout as auth_logout
from .routes_audit import list_audit_events
from .routes_autonomy import get_autonomy, put_autonomy
from .routes_brand import create_brand_profile, list_brand_profiles
from .routes_campaigns import (
    create_brief,
    get_campaign,
    get_insights,
    get_plan,
    kill_switch,
    list_campaigns,
    patch_budget,
    pause_campaign,
    publish_campaign,
    regenerate_plan,
    validate_campaign,
)
from .routes_connections import (
    connection_capabilities,
    list_connections,
    oauth_complete,
    oauth_start,
    revoke_connection,
)
from .routes_me import get_me
from .routes_session import get_memberships, switch_tenant
from .state import AppState
from .test_idp import test_idp_routes


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return exc.to_response()


async def domain_error_handler(request: Request, exc: CampaiaError) -> JSONResponse:
    return from_domain_error(exc).to_response()


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return ApiError("UNKNOWN", f"Unhandled server error: {exc}").to_response()


routes = [
    Route("/auth/login", auth_login, methods=["GET"]),
    Route("/auth/callback", auth_callback, methods=["GET"]),
    Route("/auth/logout", auth_logout, methods=["POST"]),

    Route("/me", get_me, methods=["GET"]),

    Route("/session/memberships", get_memberships, methods=["GET"]),
    Route("/session/switch-tenant", switch_tenant, methods=["POST"]),

    Route("/brand-profiles", list_brand_profiles, methods=["GET"]),
    Route("/brand-profiles", create_brand_profile, methods=["POST"]),

    Route("/connections", list_connections, methods=["GET"]),
    Route("/connections/oauth/start", oauth_start, methods=["POST"]),
    Route("/connections/oauth/complete", oauth_complete, methods=["POST"]),
    Route("/connections/{connectionId}", revoke_connection, methods=["DELETE"]),
    Route("/connections/{connectionId}/capabilities", connection_capabilities, methods=["GET"]),

    Route("/briefs", create_brief, methods=["POST"]),

    Route("/campaigns", list_campaigns, methods=["GET"]),
    Route("/campaigns/{campaignId}", get_campaign, methods=["GET"]),
    Route("/campaigns/{campaignId}/plan", get_plan, methods=["GET"]),
    Route("/campaigns/{campaignId}/plan/regenerate", regenerate_plan, methods=["POST"]),
    Route("/campaigns/{campaignId}/validate", validate_campaign, methods=["POST"]),
    Route("/campaigns/{campaignId}/publish", publish_campaign, methods=["POST"]),
    Route("/campaigns/{campaignId}/pause", pause_campaign, methods=["POST"]),
    Route("/campaigns/{campaignId}/budget", patch_budget, methods=["PATCH"]),
    Route("/campaigns/{campaignId}/insights", get_insights, methods=["GET"]),

    Route("/approvals", list_approvals, methods=["GET"]),
    Route("/approvals", create_approval, methods=["POST"]),
    Route("/approvals/{approvalId}/decision", decide_approval, methods=["POST"]),

    Route("/autonomy", get_autonomy, methods=["GET"]),
    Route("/autonomy", put_autonomy, methods=["PUT"]),

    Route("/kill-switch", kill_switch, methods=["POST"]),

    Route("/audit-events", list_audit_events, methods=["GET"]),
]

exception_handlers = {
    ApiError: api_error_handler,
    CampaiaError: domain_error_handler,
    Exception: unhandled_error_handler,
}


def _build_middleware() -> list[Middleware]:
    """CORS is opt-in, via the same CAMPAIA_WEB_ORIGIN env var routes_auth.py's
    _frontend_url reads (WP-03): a single-origin/reverse-proxied deployment (frontend and
    backend behind the same origin) never needs it -- the browser only enforces CORS across
    origins in the first place. When the Web frontend genuinely is a different origin (the
    README's own documented topology, e.g. https://app.campaia.app talking to
    https://api.campaia.app), the browser's own preflight (OPTIONS) blocks
    LogoutButton/TenantSwitcher's credentialed fetches unless the server explicitly allows
    that ONE origin -- never a wildcard, since allow_credentials=True (a wildcard
    Access-Control-Allow-Origin combined with credentials is refused by browsers anyway,
    and would be wrong here regardless: only the app's own real origin may read a
    cookie-authenticated response).

    CORSMiddleware must be OUTERMOST (first in this list) so it can short-circuit an
    OPTIONS preflight before CSRFMiddleware/routing ever see it.
    """
    middleware = [Middleware(CSRFMiddleware)]
    web_origin = os.environ.get("CAMPAIA_WEB_ORIGIN", "").strip()
    if web_origin:
        middleware.insert(
            0,
            Middleware(
                CORSMiddleware,
                allow_origins=[web_origin],
                allow_credentials=True,
                allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                allow_headers=["content-type", "x-csrf-token", "authorization", "idempotency-key", "x-step-up-token"],
            ),
        )
    return middleware


def create_app(db_path: str | None = None, *, enable_test_auth_fixtures: bool = False) -> Starlette:
    """``db_path=None`` (the default) is pure in-memory state, byte-for-byte identical to
    this app before persistence existed -- every pre-existing test relies on that. Passing
    a real path backs campaigns, approvals, connections, brand profiles, the audit log,
    idempotency records, and tenant autonomy settings with a SQLite file at that path (see
    api/db.py and api/state.py's AppState.__post_init__), so state survives a process
    restart when the same path is reused.

    ``enable_test_auth_fixtures=False`` (the default) means the fixture Bearer tokens
    (WP-01-era ``demo-owner-token`` etc.) are never seeded -- ``AppState`` starts with an
    empty ``tokens`` dict, so a bare ``create_app()`` (this is what the module-level ``app``
    below uses) can never authenticate a request via the old fixture mechanism. Only
    ``tests_api/test_helpers.py`` passes ``True`` (see its own ``CAMPAIA_ENV=test`` guard).
    See ``AppState.__post_init__`` for the fail-closed double-check.

    The test identity provider's own routes (``/test-idp/*``) are only added to this
    specific app instance's route table when ``enable_test_auth_fixtures=True`` -- the
    shared module-level ``routes`` list above is never mutated, so every other
    ``create_app()`` call (including the production ``app`` below) never exposes them,
    not even as a 404 that reveals they *could* exist.
    """
    app_routes = list(routes)
    if enable_test_auth_fixtures:
        app_routes = app_routes + test_idp_routes

    app = Starlette(
        routes=app_routes,
        exception_handlers=exception_handlers,
        middleware=_build_middleware(),
    )
    app.state.campaia = AppState(db_path=db_path, enable_test_auth_fixtures=enable_test_auth_fixtures)
    return app


#: Opt-in ONLY, for running this exact app over a real socket (uvicorn) against the test
#: identity provider -- e.g. cross-stack E2E (web/e2e-crossstack, WP-03), never CI's
#: backend-tests.yml (which imports create_app() directly, never this module-level `app`)
#: and never any deployed environment. Still gated by AppState.__post_init__'s own
#: independent CAMPAIA_ENV=test|local_dev check -- this env var alone is not enough,
#: exactly like enable_test_auth_fixtures=True passed directly never is either.
app = create_app(enable_test_auth_fixtures=os.environ.get("CAMPAIA_ENABLE_TEST_AUTH_FIXTURES") == "1")
