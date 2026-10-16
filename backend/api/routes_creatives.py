"""Copy/audience proposals use existing agents, F3 dispatch and commercial delivery rules."""
from __future__ import annotations

from copy import deepcopy
import asyncio
import json
from datetime import datetime, timezone

from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from campaia_core.agents import Proposal
from campaia_core.ai_gateway import AITask
from campaia_core.ai_simulator import SimulatedAIProvider
from campaia_core.permissions import Permission, Resource, authorize
from .campaign_brand import brand_agent_context, require_brand_assets
from .creative_proposals import (
    source_digest, require_editable, invalidate_review, serialize_proposal, EDITABLE_STATES,
)
from .deps import require_auth, require_idempotency_key, build_domain_principal
from .errors import ApiError
from .metered_execution import commercial_subscription, execute_metered, quote_action
from .models import CopyProposalInput, AudienceProposalInput, CopyProposalOutput, AudienceProposalOutput
from .routes_campaigns import _authorize, _get_campaign_or_404
from .unmetered_execution import execute_unmetered

_TASKS = {"copy": AITask.GENERATE_COPY, "audience": AITask.PROPOSE_AUDIENCE}


def _owned(request, permission):
    fixture, state, principal = _authorize(request, permission)
    kind = request.path_params["proposalKind"]
    if kind not in _TASKS:
        raise ApiError("NOT_FOUND", "Proposta indisponível.", status_code=404)
    record = _get_campaign_or_404(state, fixture.tenant_id, request.path_params["campaignId"], principal=principal)
    return fixture, state, principal, record, kind


def _capability(state, kind):
    return {
        "enabled": state.creative_proposals is not None and state.ai_provider.supports(_TASKS[kind]),
        "mode": "SIMULATED" if isinstance(state.ai_provider, SimulatedAIProvider) else "PROVIDER",
        "max_variants": 5 if kind == "copy" else None,
    }


def _require_billing_mode(state, tenant):
    if commercial_subscription(state, tenant) is None and state.env not in ("test", "dev-local"):
        raise ApiError("BILLING_ACCESS_REQUIRED", "A organização precisa de trial ou ciclo pago para gerar propostas.", status_code=409)


def _available(state, kind):
    if not _capability(state, kind)["enabled"]:
        raise ApiError("AI_CAPABILITY_UNAVAILABLE", "Esta geração está indisponível no momento.", status_code=503)


def _fresh(request, original, state):
    # Session/CSRF/roles may have changed during the provider call. No ID-token verification
    # or external network occurs inside the delivery transaction.
    current = require_auth(request)
    if (current.tenant_id, current.user_id, current.business_unit_id) != (
            original.tenant_id, original.user_id, original.business_unit_id):
        raise ApiError("AUTH_CONTEXT_CHANGED", "A sessão mudou durante a geração.", status_code=409)
    principal = build_domain_principal(request, state, current)
    record = _get_campaign_or_404(state, current.tenant_id, request.path_params["campaignId"], principal=principal)
    decision = authorize(principal, Permission.CAMPAIGN_EDIT,
        Resource(tenant_id=current.tenant_id, business_unit_id=record.business_unit_id),
        now=datetime.now(timezone.utc))
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)
    return record


def _inputs(record, kind, body):
    if body.channel not in record.planned_channels:
        raise ApiError("VALIDATION_FAILED", "Escolha um canal declarado para esta campanha.", status_code=422)
    branding = brand_agent_context(record)
    if kind == "copy":
        offer = body.offer.strip() or str(record.brief.get("product", "")).strip()
        brand_tone = branding.get("marca", {}).get("tone") or ""
        tone = body.tone.strip() or str(brand_tone).strip()
        if not offer or not tone:
            raise ApiError("AI_CONTEXT_MISSING", "Informe a oferta e o tom de voz para gerar os textos.", status_code=422)
        summary = {"offer": offer, "tone": tone, "channel": body.channel, "variants": body.variants}
        context = {**branding, "oferta": offer, "tom": tone, "canal": body.channel,
                   "quantidade_variacoes": body.variants}
    else:
        audience = body.audience.strip() or str(record.brief.get("audience", "")).strip()
        region = body.region.strip() or str(record.brief.get("region", "")).strip()
        if not audience or not region:
            raise ApiError("AI_CONTEXT_MISSING", "Informe o público e a região para gerar a proposta.", status_code=422)
        summary = {"audience": audience, "region": region, "channel": body.channel,
                   "exclusions": list(body.exclusions), "sensitive_declared": body.sensitive_declared}
        context = {**branding, "publico": audience, "regiao": region, "canal": body.channel,
                   "exclusoes_declaradas": list(body.exclusions), "sensivel_declarado": body.sensitive_declared}
    try:
        json.dumps(context, ensure_ascii=False, allow_nan=False).encode("utf-8")
        json.dumps(summary, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError):
        raise ApiError("AI_CONTEXT_MISSING", "O contexto precisa de conferência antes de gerar.", status_code=422) from None
    return summary, context



async def _proposal_body(request, model):
    limit = 256 * 1024
    if request.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise ApiError("VALIDATION_FAILED", "Envie os campos em JSON.", status_code=422)
    length = request.headers.get("Content-Length")
    if request.headers.get("Content-Encoding", "identity").lower() != "identity":
        raise ApiError("VALIDATION_FAILED", "Envie os campos em JSON sem compactação HTTP.", status_code=422)
    if length is not None and (not length.isascii() or not length.isdecimal() or int(length) > limit):
        raise ApiError("REQUEST_TOO_LARGE", "O pedido excede o tamanho permitido.", status_code=413)
    raw = bytearray()
    try:
        async with asyncio.timeout(15):
            async for chunk in request.stream():
                if len(raw) + len(chunk) > limit:
                    raise ApiError("REQUEST_TOO_LARGE", "O pedido excede o tamanho permitido.", status_code=413)
                raw.extend(chunk)
    except TimeoutError:
        raise ApiError("REQUEST_TIMEOUT", "O envio do pedido excedeu o tempo disponível.", status_code=408) from None
    try:
        return model.model_validate_json(bytes(raw))
    except ValidationError:
        raise ApiError("VALIDATION_FAILED", "Confira os campos do pedido de geração.", status_code=422) from None


def _validated_output(kind, proposal, body):
    if not isinstance(proposal, Proposal):
        if (str(proposal.status) in ("TIMEOUT", "PROVIDER_ERROR")
                and not getattr(proposal.provenance, "cost_complete", False)):
            raise ApiError("AI_OPERATION_PENDING", "Resultado externo incerto; reserva mantida para conferência.", status_code=503)
        raise ApiError("AI_OUTPUT_INVALID", "Não foi possível entregar uma proposta válida.", status_code=422)
    try:
        output = (CopyProposalOutput if kind == "copy" else AudienceProposalOutput).model_validate(proposal.output)
    except ValidationError:
        raise ApiError("AI_OUTPUT_INVALID", "A proposta não passou na validação de entrega.", status_code=422) from None
    if kind == "copy" and len(output.variacoes) != body.variants:
        raise ApiError("AI_OUTPUT_INVALID", "O lote não contém a quantidade de variações solicitada.", status_code=422)
    result = output.model_dump(mode="json")
    try:
        json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError):
        raise ApiError("AI_OUTPUT_INVALID", "A proposta não pode ser entregue em formato válido.", status_code=422) from None
    return result


async def list_creative_proposals(request):
    fixture, state, _principal, record, kind = _owned(request, Permission.CAMPAIGN_VIEW)
    result = (state.creative_proposals.page(fixture.tenant_id, record, kind, request.query_params.get("cursor"))
              if state.creative_proposals else {"items": [], "next_cursor": None})
    result["capability"] = _capability(state, kind)
    decision = authorize(_principal, Permission.CAMPAIGN_EDIT,
        Resource(tenant_id=fixture.tenant_id, business_unit_id=record.business_unit_id),
        now=datetime.now(timezone.utc))
    needs_billing = commercial_subscription(state, fixture.tenant_id) is None and state.env not in ("test", "dev-local")
    result["capability"]["billing_required"] = needs_billing
    result["capability"]["can_generate"] = bool(result["capability"]["enabled"] and decision.allowed
        and not needs_billing and record.plan is not None and record.campaign.state in EDITABLE_STATES)
    return JSONResponse(result, headers={"Cache-Control": "private, no-store"})


async def quote_creative_proposal(request):
    fixture, state, _principal, record, kind = _owned(request, Permission.CAMPAIGN_EDIT)
    _available(state, kind)
    _require_billing_mode(state, fixture.tenant_id)
    require_brand_assets(state, record)
    result = quote_action(state, fixture.tenant_id, kind)
    return JSONResponse({**result, "kind": kind, "max_variants": 5 if kind == "copy" else None},
                        headers={"Cache-Control": "private, no-store"})


async def generate_creative_proposal(request):
    fixture, state, _principal, record, kind = _owned(request, Permission.CAMPAIGN_EDIT)
    nonce = require_idempotency_key(request)
    _available(state, kind)
    _require_billing_mode(state, fixture.tenant_id)
    if not state.proposal_rate_limiter.allow(fixture.tenant_id, now=datetime.now(timezone.utc)):
        raise ApiError("RATE_LIMITED", "Aguarde antes de gerar mais propostas.", status_code=429)
    if not state.proposal_slots.acquire(blocking=False):
        raise ApiError("AI_BUSY", "Há outras propostas em geração. Tente novamente.", status_code=429)
    try:
        body = await _proposal_body(request, CopyProposalInput if kind == "copy" else AudienceProposalInput)
        identity = {"campaign_id": record.campaign_id, "kind": kind,
                    "request": body.model_dump(mode="json", exclude={"credit_confirmation"})}
        captured = {}
        def snapshot():
            current = _fresh(request, fixture, state)
            require_editable(current, body.expected_plan_version)
            require_brand_assets(state, current)
            return source_digest(current), current.plan_version

        def generate():
            # Capture a consistent, owned input under a short F3 transaction.
            with state.db.transaction():
                state.idempotency._table.lock_key("tenant:" + fixture.tenant_id)
                current = _fresh(request, fixture, state)
                require_editable(current, body.expected_plan_version)
                require_brand_assets(state, current)
                summary, context = _inputs(current, kind, body)
                captured.update(source=source_digest(current), summary=deepcopy(summary))
            # Claim/reservation and capture have committed; agent/provider owns no DB lock.
            proposal = state.agent_runner.run(kind, tenant_id=fixture.tenant_id, context=context)
            return proposal, _validated_output(kind, proposal, body)

        def deliver(generated):
            current = _fresh(request, fixture, state)
            require_editable(current, body.expected_plan_version)
            require_brand_assets(state, current)
            if source_digest(current) != captured["source"]:
                raise ApiError("AI_INPUT_CHANGED", "O contexto mudou durante a geração; entrega descartada.", status_code=409)
            proposal, output = generated
            invalidate_review(current)
            row = state.creative_proposals.append(fixture, current, kind, output, captured["summary"], proposal)
            state.audit.append(tenant_id=fixture.tenant_id, actor=fixture.user_id,
                action="CREATIVE_PROPOSAL_DELIVERED", target=row["id"],
                details={"campaign_id": current.campaign_id, "kind": kind,
                         "version": row["version"], "plan_version": current.plan_version})
            return serialize_proposal(row, current_source=source_digest(current))

        def execute():
            key = "creative:" + kind + ":" + record.campaign_id + ":" + nonce
            if commercial_subscription(state, fixture.tenant_id) is not None:
                confirmation = body.credit_confirmation.model_dump(mode="json") if body.credit_confirmation else None
                return execute_metered(state, fixture, "http:" + key, identity, confirmation, kind, generate, deliver)
            return execute_unmetered(state, fixture, key, record.campaign_id, snapshot, generate, deliver,
                                     namespace=kind, request_identity=identity)
        result = await run_in_threadpool(execute)
        return JSONResponse(result, status_code=201, headers={"Cache-Control": "private, no-store"})
    finally:
        state.proposal_slots.release()
