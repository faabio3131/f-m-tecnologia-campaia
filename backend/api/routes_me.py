from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

from campaia_core.permissions import ROLE_PERMISSIONS

from .deps import get_state, require_auth
from .helpers import json_response
from .models import MeResponse


async def get_me(request: Request) -> JSONResponse:
    principal = require_auth(request)
    permissions: set[str] = set()
    for role in principal.roles:
        permissions |= {p.value for p in ROLE_PERMISSIONS.get(role, frozenset())}

    return json_response(
        MeResponse(
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            business_unit_id=principal.business_unit_id,
            roles=sorted(r.value for r in principal.roles),
            permissions=sorted(permissions),
            mfa_enabled=principal.mfa_enabled,
        )
    )
