"""Servidor ASGI real, SOMENTE para E2E (Playwright) -- nunca importado por
`api/main.py` nem usado fora deste script.

Constroi o `AppState` real (`api.state.AppState`) atraves dos MESMOS parametros de
construcao publicos que qualquer chamador legitimo usa (`env`, `allowed_origins`,
`id_token_verifier`) -- nenhum endpoint de bypass, nenhuma rota nova. O protocolo de
sessao/CSRF/cookie exercitado pelo E2E e o codigo real de `api/routes_auth.py`,
`api/deps.py`, `api/session.py`.

Uso (nunca em produção/staging/preview):
    CAMPAIA_E2E_ALLOWED_ORIGIN=http://127.0.0.1:4173 \
    CAMPAIA_E2E_PORT=8000 \
    python3 -m tests_support.e2e_server
"""

from __future__ import annotations

import os

import uvicorn
from starlette.applications import Starlette

from api.main import create_app
from api.state import AppState
from tests_support.e2e_identity import DeterministicTestIdTokenVerifier


def build_e2e_app() -> Starlette:
    allowed_origin = os.environ.get("CAMPAIA_E2E_ALLOWED_ORIGIN")
    if not allowed_origin:
        raise RuntimeError(
            "CAMPAIA_E2E_ALLOWED_ORIGIN e obrigatoria para o harness de E2E -- "
            "nunca inferida nem default para '*' (sem wildcard, mesma regra do "
            "backend real de producao)."
        )

    app = create_app(env="test")
    state: AppState = app.state.campaia
    state.id_token_verifier = DeterministicTestIdTokenVerifier()
    state.allowed_origins = frozenset({allowed_origin})
    return app


app = build_e2e_app()


if __name__ == "__main__":
    port = int(os.environ.get("CAMPAIA_E2E_PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
