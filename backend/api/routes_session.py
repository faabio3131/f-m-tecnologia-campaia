"""WP-03: GET /session/memberships and POST /session/switch-tenant.

Both require a real Web session cookie (api/deps.py's require_web_session) -- neither is
reachable via the fixture Bearer-token path, which has no session to enumerate or switch.
`tenant_id` in the switch request body is the one deliberate exception to the "tenant_id is
never client-supplied" rule enforced elsewhere (api/helpers.py parse_body): here it is the
explicit switch target, never trusted on its own -- AppState.switch_tenant (api/state.py)
only ever honours it when it names one of the session's own server-recorded memberships.
"""

from __future__ import annotations

import json

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from .deps import get_state, require_web_session
from .errors import ApiError
from .helpers import json_response
from .models import MembershipResponse, SessionMembershipsResponse, SwitchTenantRequest
from .routes_auth import _set_session_cookies


def _memberships_response(session_id: str, record) -> SessionMembershipsResponse:  # noqa: ANN001
    active_tenant_id = record.principal.tenant_id
    return SessionMembershipsResponse(
        memberships=[
            MembershipResponse(
                tenant_id=m.tenant_id,
                business_unit_id=m.business_unit_id,
                roles=list(m.roles),
                is_active=(m.tenant_id == active_tenant_id),
            )
            for m in record.memberships
        ]
    )


async def get_memberships(request: Request) -> JSONResponse:
    session_id, record = require_web_session(request)
    return json_response(_memberships_response(session_id, record))


async def switch_tenant(request: Request) -> JSONResponse:
    session_id, record = require_web_session(request)

    raw = await request.body()
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise ApiError("VALIDATION_FAILED", f"Invalid JSON body: {exc}") from exc
    if not isinstance(payload, dict):
        raise ApiError("VALIDATION_FAILED", "Request body must be a JSON object.")
    try:
        body = SwitchTenantRequest.model_validate(payload)
    except ValidationError as exc:
        raise ApiError(
            "VALIDATION_FAILED",
            "Request body failed validation.",
            details={"errors": exc.errors(include_url=False, include_context=False)},
        ) from exc

    state = get_state(request)
    result = state.switch_tenant(session_id, body.tenant_id)
    if result is None:
        raise ApiError(
            "PERMISSION_DENIED",
            "Not a member of the requested tenant, or the current session is no longer valid.",
            details={"tenant_id": body.tenant_id},
        )
    new_session_id, new_csrf_token = result
    new_record = state.get_session(new_session_id)
    assert new_record is not None  # just created above -- cannot have expired yet

    response = json_response(_memberships_response(new_session_id, new_record))
    _set_session_cookies(response, session_id=new_session_id, csrf_token=new_csrf_token)
    return response
