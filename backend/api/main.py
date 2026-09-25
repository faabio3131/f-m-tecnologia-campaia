"""CAMPAIA BFF/API Starlette application.

Run with: uvicorn api.main:app --reload  (from /home/claude/campaia_verify)

Built on Starlette rather than FastAPI: FastAPI could not be installed in this sandbox
(pypi.org is blocked by the environment's network egress allowlist -- confirmed 403 via
both pip and uv). Starlette is the ASGI framework FastAPI wraps and was already available,
so this app mirrors the routing/response shape a FastAPI app would have.
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from campaia_core.errors import CampaiaError

from .errors import ApiError, from_domain_error
from .routes_approvals import create_approval, decide_approval, list_approvals
from .routes_audit import list_audit_events
from .routes_auth import get_session, list_memberships, login, logout, switch_membership
from .routes_autonomy import get_autonomy, put_autonomy
from .routes_billing import asaas_webhook, create_charge, get_subscription, put_subscription
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
    oauth_start,
    revoke_connection,
)
from .routes_me import get_me
from .state import AppState


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return exc.to_response()


async def domain_error_handler(request: Request, exc: CampaiaError) -> JSONResponse:
    return from_domain_error(exc).to_response()


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return ApiError("UNKNOWN", f"Unhandled server error: {exc}").to_response()


routes = [
    # Item 1.3/WP-02 (24/09/2026): sessao real. Sem require_auth -- e o proprio endpoint
    # que estabelece/encerra a sessao que require_auth depois consome. GET devolve o
    # csrf_token da sessao atual (recuperacao apos reload, achado de fm-security-review).
    Route("/auth/session", login, methods=["POST"]),
    Route("/auth/session", get_session, methods=["GET"]),
    Route("/auth/session", logout, methods=["DELETE"]),
    Route("/auth/session/switch", switch_membership, methods=["POST"]),

    Route("/me", get_me, methods=["GET"]),
    Route("/me/memberships", list_memberships, methods=["GET"]),

    Route("/brand-profiles", list_brand_profiles, methods=["GET"]),
    Route("/brand-profiles", create_brand_profile, methods=["POST"]),

    Route("/connections", list_connections, methods=["GET"]),
    Route("/connections/oauth/start", oauth_start, methods=["POST"]),
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

    # Motor de cobranca propria do CampaIA (B11 / ADR-0020).
    Route("/billing/subscription", get_subscription, methods=["GET"]),
    Route("/billing/subscription", put_subscription, methods=["PUT"]),
    Route("/billing/charges", create_charge, methods=["POST"]),
    # Unico endpoint deste app sem Bearer token de usuario -- quem chama e o Asaas, nao o
    # app; a autenticidade vem do token estatico verificado por AsaasWebhookReceiver.
    Route("/webhooks/asaas", asaas_webhook, methods=["POST"]),
]

exception_handlers = {
    ApiError: api_error_handler,
    CampaiaError: domain_error_handler,
    Exception: unhandled_error_handler,
}


def create_app(db_path: str | None = None, env: str | None = None) -> Starlette:
    """``db_path=None`` (the default) is pure in-memory state, byte-for-byte identical to
    this app before persistence existed -- every pre-existing test relies on that. Passing
    a real path backs campaigns, approvals, connections, brand profiles, the audit log,
    idempotency records, and tenant autonomy settings with a SQLite file at that path (see
    api/db.py and api/state.py's AppState.__post_init__), so state survives a process
    restart when the same path is reused.

    ``env=None`` (the default) lets `AppState` read `CAMPAIA_ENV` itself, defaulting to
    the fail-closed "production" value (item 1.3/WP-02: no dev auth fixture). Test/local
    dev call sites pass ``env="test"``/``"dev-local"`` explicitly.
    """
    app = Starlette(routes=routes, exception_handlers=exception_handlers)
    kwargs = {"db_path": db_path}
    if env is not None:
        kwargs["env"] = env
    app.state.campaia = AppState(**kwargs)
    return app


app = create_app()
