"""GET /health -- Fase 3, item 5 da missao de reconciliacao/takeover (Health /
Observability, 26/09/2026, achado 23): a auditoria real desta sessao (grep completo em
`backend/api/main.py` e `campaia_core/`) confirmou `NAO ENCONTRADO` -- nenhum endpoint de
health/liveness/readiness existia no CURRENT antes desta correcao, apesar de
`docs/nova-fm/02-PADROES-DE-CONSTRUCAO-NOVA-FM.md` ja exigir um que nao minta (linha 960:
"Evitar health check que retorna sucesso mesmo quando dependencia critica esta
indisponivel").

Uma implementacao historica equivalente foi encontrada em
`feat/campaia-v1-complete-saas` (commit `84f9645`, "feat(api): add GET /health liveness
endpoint") e AVALIADA -- nao copiada as cegas -- antes de ser adaptada aqui: a logica
(consultar `Database.ping()` quando persistencia estiver configurada, sempre honesto
quando nao estiver) e a mesma, mas o codigo foi reescrito contra os nomes e imports reais
do CURRENT (`.deps.get_state`, `AppState.db`), nao colado do historico.

Deliberadamente nao autenticado e fora de `contracts/bff-openapi.yaml`, seguindo o mesmo
precedente ja existente neste projeto para endpoints de infraestrutura sem contrato
client-facing (`/test-idp/*` e igualmente real porem fora do contrato BFF).

Modo puro em memoria (`AppState.db is None`, o padrao -- nenhum `db_path` configurado) nao
tem nenhuma dependencia externa real para falhar, entao sempre reporta saudavel; com
persistencia configurada, uma falha real de `Database.ping()` (uma query SQL de fato, nao
apenas a existencia do objeto de conexao) produz um 503 honesto, nunca um 200 fabricado.
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
