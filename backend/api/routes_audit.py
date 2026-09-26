from __future__ import annotations

from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

from campaia_core.permissions import Permission, Resource, authorize

from .deps import build_domain_principal, get_state, require_auth
from .errors import ApiError
from .helpers import json_response, serialize_audit_event
from .models import AuditEventListResponse

# ACHADO 21 (Fase 3, item 3 -- mineracao tecnica da PR#6, 26/09/2026): pagina fixa, nao
# um query param -- o contrato nunca declarou um parametro `limit`, so `cursor`/
# `next_cursor` opacos (estilo Stripe), que ele ja prometia desde antes desta correcao.
_PAGE_SIZE = 50


async def list_audit_events(request: Request) -> JSONResponse:
    fixture = require_auth(request)
    state = get_state(request)
    principal = build_domain_principal(state, fixture)
    resource = Resource(tenant_id=fixture.tenant_id, business_unit_id=fixture.business_unit_id)
    decision = authorize(principal, Permission.AUDIT_VIEW, resource, now=datetime.now(timezone.utc))
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)

    events = state.audit.list_for_tenant(fixture.tenant_id)
    # ACHADO 21: `audit_event_id` (new_id("audit"), api/repositories.py) vem de um unico
    # contador monotonico compartilhado por todo tipo de entidade neste processo -- e
    # unico e totalmente ordenado exatamente como a ordem de criacao, um desempate
    # estavel para `timestamp`, que nao tem essa garantia sob appends rapidos e
    # consecutivos (dois eventos no mesmo microssegundo, ja possivel hoje -- ver testes).
    events = sorted(events, key=lambda e: (e.timestamp, e.audit_event_id))

    # AuditEvent.target is a generic "whatever entity this action was about" field --
    # for campaign-scoped actions (CAMPAIGN_CREATE, PLAN_REGENERATE, CAMPAIGN_PUBLISH,
    # CAMPAIGN_PAUSE, BUDGET_CHANGE, CAMPAIGN_VALIDATE, campaign-scope KILL_SWITCH) it IS
    # the campaign_id, which is the best available mapping given there is no dedicated
    # campaign_id column on AuditEvent today (documented simplification, achado 15).
    campaign_id_filter = request.query_params.get("campaign_id")
    if campaign_id_filter:
        events = [e for e in events if e.target == campaign_id_filter]

    # ACHADO 21 (Fase 3, reproduzido por execucao real: um cursor desconhecido era
    # silenciosamente ignorado, devolvendo a pagina 1 inteira em vez de falhar --
    # substitui o stub honesto anterior, que sempre devolvia next_cursor: null e nunca
    # paginava de fato, achado 3/15 original). Avaliada a implementacao historica da
    # PR#6 (backend/api/routes_audit.py, commit 6536b5e la, "Etapa A9") e adaptada aqui
    # sem copia cega -- mesma logica, reconstruida sobre o CURRENT (mesmos nomes de
    # campo, mesma convencao de erro ApiError ja usada neste modulo).
    #
    # `cursor` e opaco ao cliente -- e o proprio id do ultimo evento ja devolvido,
    # exatamente como o contrato ja prometia. Um cursor desconhecido/obsoleto falha
    # fechado (VALIDATION_FAILED) em vez de silenciosamente resetar para a pagina 1 --
    # a mesma convencao fail-closed ja aplicada neste backend para qualquer entrada do
    # cliente que nao pode ser verificada no servidor.
    start = 0
    cursor = request.query_params.get("cursor")
    if cursor:
        ids = [e.audit_event_id for e in events]
        try:
            start = ids.index(cursor) + 1
        except ValueError:
            raise ApiError("VALIDATION_FAILED", "Unknown or expired cursor.")

    page = events[start : start + _PAGE_SIZE]
    has_more = start + _PAGE_SIZE < len(events)
    next_cursor = page[-1].audit_event_id if has_more else None

    envelope = AuditEventListResponse(
        items=[serialize_audit_event(e) for e in page], next_cursor=next_cursor
    )
    return json_response(envelope)
