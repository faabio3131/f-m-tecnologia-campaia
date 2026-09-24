from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

from campaia_core.permissions import ROLE_PERMISSIONS

from .deps import get_state, require_auth
from .helpers import json_response
from .models import MeResponse
from .session import SESSION_COOKIE_NAME


async def get_me(request: Request) -> JSONResponse:
    principal = require_auth(request)
    permissions: set[str] = set()
    for role in principal.roles:
        permissions |= {p.value for p in ROLE_PERMISSIONS.get(role, frozenset())}

    state = get_state(request)
    csrf_token: str | None = None
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id is not None:
        # Achado de fm-security-review (24/09/2026, WP-02): sem isto, uma aba recarregada
        # ficava autenticada para leitura mas incapaz de fazer qualquer mutacao sem novo
        # login (o csrf_token so vinha no corpo da resposta de login). Continua None quando
        # nao ha sessao real (fixture de bearer de dev/teste, que nao tem CSRF).
        record = state.sessions.get(session_id)
        if record is not None:
            csrf_token = record.csrf_secret

    return json_response(
        MeResponse(
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            business_unit_id=principal.business_unit_id,
            roles=sorted(r.value for r in principal.roles),
            permissions=sorted(permissions),
            mfa_enabled=principal.mfa_enabled,
            csrf_token=csrf_token,
        )
    )
