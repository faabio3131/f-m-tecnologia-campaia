"""Request-level dependencies: fake bearer auth, step-up, idempotency key extraction.

Invariant #1 from the spec: tenant_id is NEVER accepted from the client. It is derived
here, from the bearer token only, and nowhere else in the app reads a client-supplied
tenant_id.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from starlette.requests import Request

from campaia_core.permissions import Principal

from .errors import ApiError
from .state import AppState, TokenPrincipal

MIN_IDEMPOTENCY_KEY_LEN = 16
MAX_IDEMPOTENCY_KEY_LEN = 128


def get_state(request: Request) -> AppState:
    return request.app.state.campaia


def require_auth(request: Request) -> TokenPrincipal:
    """Resolve the bearer token to a fixture principal. 401 on anything else.

    The token is an opaque local-dev fixture string (e.g. "demo-owner-token"), looked up
    in an in-memory dict -- never parsed, never treated as a JWT/credential format.
    """
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        raise ApiError("UNAUTHENTICATED", "Missing or malformed Authorization header.")
    token = header[len("Bearer ") :].strip()
    if not token:
        raise ApiError("UNAUTHENTICATED", "Empty bearer token.")

    state = get_state(request)
    principal = state.tokens.get(token)
    if principal is None:
        raise ApiError("UNAUTHENTICATED", "Unknown or expired token.")
    return principal


def note_step_up_header(request: Request, fixture: TokenPrincipal) -> None:
    """If X-Step-Up-Token is present, record "stepped up now" into AppState.

    Must run BEFORE any campaia_core.permissions.authorize() call on this request, since
    authorize() reads Principal.step_up_at to decide STEP_UP_REQUIRED itself (see
    permissions.py REQUIRES_STEP_UP / STEP_UP_MAX_AGE). If this ran after authorize(), the
    very first request with a valid header would still be rejected because the domain
    check would see step_up_at=None. This function never rejects -- it only records;
    rejection for a *missing* header on a sensitive endpoint is the domain's own
    STEP_UP_REQUIRED coming out of authorize(), so the sandbox's "any non-empty value is
    valid" rule and the real STEP_UP_MAX_AGE recency window are both genuinely enforced by
    campaia_core, not re-implemented here.
    """
    value = request.headers.get("x-step-up-token", "").strip()
    if value:
        state = get_state(request)
        state.record_step_up(fixture.tenant_id, fixture.user_id, at=datetime.now(timezone.utc))


def require_step_up(request: Request, fixture: TokenPrincipal) -> None:
    """Back-compat explicit check, for permissions that are gated at the HTTP layer only
    (not every sensitive endpoint's permission is in campaia_core.permissions.
    REQUIRES_STEP_UP -- e.g. OAuth start has no dedicated Permission of its own beyond
    CONNECTION_MANAGE, which IS covered, so this mostly acts as a defence-in-depth
    re-check). Must be called AFTER note_step_up_header/authorize.
    """
    value = request.headers.get("x-step-up-token", "").strip()
    if not value:
        raise ApiError(
            "STEP_UP_REQUIRED",
            "This operation requires a recent step-up re-authentication "
            "(X-Step-Up-Token header).",
        )


def require_idempotency_key(request: Request) -> str:
    key = request.headers.get("idempotency-key", "").strip()
    if not key:
        raise ApiError(
            "VALIDATION_FAILED",
            "This operation requires an Idempotency-Key header.",
            details={"header": "Idempotency-Key"},
        )
    if not (MIN_IDEMPOTENCY_KEY_LEN <= len(key) <= MAX_IDEMPOTENCY_KEY_LEN):
        raise ApiError(
            "VALIDATION_FAILED",
            f"Idempotency-Key must be {MIN_IDEMPOTENCY_KEY_LEN}-"
            f"{MAX_IDEMPOTENCY_KEY_LEN} characters.",
            details={"header": "Idempotency-Key", "length": len(key)},
        )
    return key


def build_domain_principal(state: AppState, fixture: TokenPrincipal) -> Principal:
    """Build the real campaia_core.permissions.Principal, including step_up_at.

    This makes the RBAC/ABAC checks in permissions.authorize (MFA, step-up recency,
    value ceilings) genuinely load-bearing rather than re-implemented at the HTTP layer.
    """
    step_up_at = state.last_step_up(fixture.tenant_id, fixture.user_id)
    return fixture.to_domain_principal(step_up_at=step_up_at)


def reject_client_tenant_id(body: dict) -> None:
    """Defence in depth: if a client-supplied body somehow carries tenant_id, refuse it
    rather than silently ignoring it. Pydantic-free version: `models.py` schemas simply
    do not declare a tenant_id field at all, so this only fires for raw/extra dict usage.
    """
    if "tenant_id" in body:
        raise ApiError(
            "VALIDATION_FAILED",
            "tenant_id is derived from the authenticated principal and must not be "
            "supplied by the client.",
            details={"field": "tenant_id"},
        )
