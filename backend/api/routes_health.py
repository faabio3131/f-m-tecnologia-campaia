"""GET /health -- Missão de fechamento integral (Etapa A17, 22/09/2026): the CURRENT
audit (Etapa A3) found no observability of any kind in this backend, not even a liveness
endpoint. Deliberately unauthenticated and outside contracts/bff-openapi.yaml, matching
this project's existing precedent for infra-only, non-business-contract endpoints
(/test-idp/* is likewise real but undocumented in the client-facing contract).

Per docs/nova-fm/02-PADROES-DE-CONSTRUCAO-NOVA-FM.md §46: a health check must not report
success while a critical dependency is down, so this genuinely queries the database (via
Database.ping()) when persistence is configured, rather than always returning 200. Pure
in-memory mode (the default -- see AppState.db_path) has no external dependency to fail,
so it always reports healthy.
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

from .deps import get_state


async def health(request: Request) -> JSONResponse:
    state = get_state(request)
    if state.db is not None and not state.db.ping():
        return JSONResponse({"status": "unavailable", "database": "unreachable"}, status_code=503)
    return JSONResponse({"status": "ok"})
