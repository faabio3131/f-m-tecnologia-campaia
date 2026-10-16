from __future__ import annotations

from datetime import date, datetime, timezone
from copy import deepcopy
from hashlib import sha256
import json
from decimal import Decimal

from starlette.requests import Request
from starlette.responses import JSONResponse

from campaia_core.autonomy import ActionKind
from campaia_core.budget import BudgetLimitExceeded
from campaia_core.connectors import ConnectorError
from campaia_core.errors import CampaiaError, InvalidStateTransition
from campaia_core.permissions import Permission, Resource, authorize
from campaia_core.policy import PolicyEngine, PolicyRequest
from campaia_core.saga import CompensationPolicy, PublicationSaga
from campaia_core.simulator import ProviderSimulator
from campaia_core.states import CampaignState, TransitionContext

from .deps import (
    build_domain_principal,
    get_state,
    note_step_up_header,
    require_auth,
    require_idempotency_key,
    require_step_up,
)
from .errors import ApiError, from_domain_error
from .helpers import (
    json_response,
    list_response,
    parse_body,
    serialize_campaign,
    serialize_policy_decision,
)
from .models import (
    BriefCreate,
    BudgetPatchRequest,
    CampaignListResponse,
    InsightSeriesResponse,
    KillSwitchRequest,
    PlanResponse,
    PlanRegenerateRequest,
    PublishRequest,
)
from .repositories import ExternalResourceState
from .unmetered_execution import execute_unmetered
from .metered_execution import commercial_subscription, execute_metered, quote_action
from .commercial_limits import enforce_campaign_capacity
from .creative_proposals import current_proposal_text
from .campaign_brand import (freeze_selected_brand, brand_agent_context, brand_guidance,
    brand_assets_ready, require_brand_assets)


def _authorize(request: Request, permission: Permission, *, amount: Decimal | None = None):
    fixture = require_auth(request)
    state = get_state(request)
    note_step_up_header(request, fixture)
    principal = build_domain_principal(request, state, fixture)
    resource = Resource(tenant_id=fixture.tenant_id, business_unit_id=fixture.business_unit_id)
    decision = authorize(principal, permission, resource, now=datetime.now(timezone.utc), amount=amount)
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)
    return fixture, state, principal


def _get_campaign_or_404(state, tenant_id: str, campaign_id: str, *, principal=None):
    record = state.campaigns.get(tenant_id, campaign_id)
    if record is None:
        raise ApiError("NOT_FOUND", "Campaign not found.")
    # Escopo de unidade de negocio (achado da revisao de seguranca de 24/09/2026, item
    # 1.9): `_authorize` acima so verifica a unidade do PROPRIO CHAMADOR contra ele mesmo
    # (tautologia -- nunca nega), porque na hora em que ele roda ainda nao sabe qual
    # campanha sera acessada. Este e o unico ponto, ja com o registro real em maos, onde a
    # unidade de negocio DA CAMPANHA pode ser comparada contra as unidades do principal --
    # mesma semantica de `authorize()` (NOT_FOUND, nunca PERMISSION_DENIED, para nao
    # revelar que a campanha existe em outra unidade).
    if (
        principal is not None
        and principal.business_unit_ids is not None
        and record.business_unit_id is not None
        and record.business_unit_id not in principal.business_unit_ids
    ):
        raise ApiError("NOT_FOUND", "Campaign not found.")
    return record


# --------------------------------------------------------------------------- briefs


async def create_brief(request: Request) -> JSONResponse:
    fixture, state, principal = _authorize(request, Permission.CAMPAIGN_CREATE)
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, BriefCreate)

    if body.connection_id is not None:
        conn = state.connections.get(fixture.tenant_id, body.connection_id)
        if conn is None:
            raise ApiError("NOT_FOUND", "connection_id does not reference a known connection.")

    # Achado da revisao de seguranca de 24/09/2026 (item 1.9): sem isto, o corpo da
    # requisicao podia atribuir a campanha a QUALQUER unidade de negocio do tenant, nao so
    # as do proprio criador -- o que tornava o escopo de unidade sem sentido (a campanha
    # nasceria fora do alcance de quem a criou, mas dentro do alcance de outra pessoa
    # daquela unidade, sem nenhum controle de quem pode atribuir o que). Um principal sem
    # restricao (business_unit_ids is None, ex. OWNER) continua podendo escolher
    # livremente; um principal restrito so pode criar dentro das proprias unidades.
    business_unit_id = body.business_unit_id or fixture.business_unit_id
    if (
        principal.business_unit_ids is not None
        and business_unit_id is not None
        and business_unit_id not in principal.business_unit_ids
    ):
        raise ApiError(
            "VALIDATION_FAILED",
            "business_unit_id nao pertence as unidades de negocio do usuario.",
        )

    fields = body.model_dump(mode="json")
    context = sha256(json.dumps([fixture.user_id, business_unit_id, fields], sort_keys=True).encode()).hexdigest()

    def _do_create():
        frozen_brand = freeze_selected_brand(state, fixture.tenant_id, body.brand_selection)
        brief = {**fields, **({"brand_snapshot_v1": frozen_brand} if frozen_brand else {})}
        record = state.campaigns.create(
            fixture.tenant_id,
            brief=brief,
            business_unit_id=business_unit_id,
            created_by=fixture.user_id,
        )
        record.planned_channels = tuple(body.channels)
        record.connection_id = body.connection_id

        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="CAMPAIGN_CREATE",
            target=record.campaign_id,
        )
        response = serialize_campaign(record).model_dump(mode="json")
        return {"context": context, "response": response}

    result, _replay = state.idempotency.execute(
        fixture.tenant_id, f"http:create_brief:{idem_key}", _do_create
    )
    if "context" in result and "response" in result:
        if result["context"] != context:
            raise ApiError("IDEMPOTENCY_CONFLICT", "A chave identifica outro briefing ou contexto.", status_code=409)
        response = result["response"]
    else:
        # Compatibility with already-issued legacy responses; no new effect on replay.
        response = result
        legacy = dict(response.get("brief", {}))
        expected = dict(fields)
        if "brand_selection" not in legacy and expected["brand_selection"] is None:
            expected.pop("brand_selection")
        if legacy != expected:
            raise ApiError("IDEMPOTENCY_CONFLICT", "A chave identifica outro briefing.", status_code=409)
    owned = _get_campaign_or_404(state, fixture.tenant_id, response["id"], principal=principal)
    if owned.created_by != fixture.user_id or owned.business_unit_id != business_unit_id:
        raise ApiError("IDEMPOTENCY_CONFLICT", "O contexto do briefing mudou.", status_code=409)
    return JSONResponse(response, status_code=202)


# --------------------------------------------------------------------------- campaigns


async def list_campaigns(request: Request) -> JSONResponse:
    fixture, state, principal = _authorize(request, Permission.CAMPAIGN_VIEW)
    records = state.campaigns.list_for_tenant(fixture.tenant_id)
    # Mesmo escopo de unidade de negocio aplicado em _get_campaign_or_404 -- sem isto, a
    # listagem devolveria campanhas de QUALQUER unidade do tenant para um principal
    # restrito, mesmo que ele nunca conseguisse abrir uma individualmente.
    if principal.business_unit_ids is not None:
        records = [
            r
            for r in records
            if r.business_unit_id is None or r.business_unit_id in principal.business_unit_ids
        ]

    state_filter = request.query_params.get("state")
    if state_filter:
        records = [r for r in records if r.campaign.state.value == state_filter]

    # `cursor` (contract query param) is accepted but there is no real pagination layer
    # in this repository yet (CampaignRepository.list_for_tenant returns everything in
    # memory) -- we always return next_cursor: null rather than fabricate pagination that
    # does not exist (achado 3). The `cursor` value itself is currently ignored.
    envelope = CampaignListResponse(
        items=[serialize_campaign(r) for r in records], next_cursor=None
    )
    return json_response(envelope)


async def get_campaign(request: Request) -> JSONResponse:
    fixture, state, principal = _authorize(request, Permission.CAMPAIGN_VIEW)
    record = _get_campaign_or_404(
        state, fixture.tenant_id, request.path_params["campaignId"], principal=principal
    )
    return json_response(serialize_campaign(record))


# --------------------------------------------------------------------------- plan


def _run_strategist(state, fixture, record) -> dict:
    """Use the configured AgentRunner/provider; preserve structured provenance."""
    require_brand_assets(state, record)
    context = {
        **brand_agent_context(record),
        "objetivo": record.brief.get("objective", ""),
        "orcamento": str(record.brief.get("total_budget", "")),
        "publico": record.brief.get("audience", ""),
        "regiao": record.brief.get("region", "BR"),
    }
    result = state.agent_runner.run("strategist", tenant_id=fixture.tenant_id, context=context)
    if hasattr(result, "output"):  # Proposal
        return {
            "proposal_id": result.proposal_id,
            "output": result.output,
            "provider": result.provenance.provider,
            "model": result.provenance.model,
        }
    # An external timeout/provider error may already have incurred provider cost.
    # Commercial replays must reconcile instead of redispatching that operation.
    if (str(result.status) in {"TIMEOUT", "PROVIDER_ERROR"}
            and not getattr(result.provenance, "cost_complete", False)):
        raise ApiError('AI_OPERATION_PENDING', 'Execução externa incerta; reserva mantida para reconciliação.', status_code=503)
    # AgentFailure with a known no-delivery outcome.
    raise ApiError(
        "VALIDATION_FAILED",
        f"Plan generation failed: {result.reason}",
        details={"missing_context": list(result.missing_context)},
    )


async def get_plan(request: Request) -> JSONResponse:
    fixture, state, principal = _authorize(request, Permission.CAMPAIGN_VIEW)
    record = _get_campaign_or_404(
        state, fixture.tenant_id, request.path_params["campaignId"], principal=principal
    )
    return json_response(
        PlanResponse(campaign_id=record.campaign_id, plan_version=record.plan_version, plan=record.plan)
    )


async def quote_strategy(request: Request) -> JSONResponse:
    fixture, state, principal = _authorize(request, Permission.CAMPAIGN_EDIT)
    _get_campaign_or_404(state, fixture.tenant_id, request.path_params["campaignId"], principal=principal)
    return JSONResponse(quote_action(state, fixture.tenant_id, 'strategy'))


async def regenerate_plan(request: Request) -> JSONResponse:
    fixture, state, principal = _authorize(request, Permission.CAMPAIGN_EDIT)
    idem_key = require_idempotency_key(request)
    campaign_id = request.path_params["campaignId"]

    # Resource authorization always precedes cache/replay, including across units.
    scoped_record = _get_campaign_or_404(state, fixture.tenant_id, campaign_id, principal=principal)
    if commercial_subscription(state, fixture.tenant_id) is not None:
        body = await parse_body(request, PlanRegenerateRequest)
        confirmation = (body.credit_confirmation.model_dump(mode='json')
                        if body.credit_confirmation else None)
        brief_snapshot = deepcopy(dict(scoped_record.brief))
        version_snapshot = scoped_record.plan_version
        def generate():
            plan = _run_strategist(state, fixture, scoped_record)
            # Reuse the deterministic policy authority. Approval/publication remains
            # a separate operation; this check does not authorize publication.
            decision = PolicyEngine().evaluate(PolicyRequest(
                tenant_id=fixture.tenant_id, campaign_id=campaign_id,
                plan_version=version_snapshot + 1, action=ActionKind.FIRST_PUBLISH,
                autonomy=scoped_record.autonomy, budget=scoped_record.budget,
                plan_text=str(plan.get('output', '')),
                brand_guidance=brand_guidance(scoped_record),
                brand_assets_ready=brand_assets_ready(state, scoped_record)), now=datetime.now(timezone.utc))
            if decision.outcome.value == 'BLOCKED':
                raise ApiError('POLICY_VIOLATION', 'Entrega bloqueada pela política, sem consumo comercial.', status_code=422)
            return plan
        def deliver(plan):
            record = _get_campaign_or_404(state, fixture.tenant_id, campaign_id, principal=principal)
            if dict(record.brief) != brief_snapshot or record.plan_version != version_snapshot:
                raise ApiError('AI_INPUT_CHANGED', 'A campanha mudou durante a geração; entrega descartada sem débito.', status_code=409)
            require_brand_assets(state, record)
            record.plan = plan
            record.plan_version += 1
            if record.campaign.state is CampaignState.DRAFT:
                record.campaign.transition_to(CampaignState.STRATEGY_READY, reason='plan:regenerated')
            state.audit.append(tenant_id=fixture.tenant_id, actor=fixture.user_id,
                               action='PLAN_REGENERATE', target=campaign_id,
                               details={'plan_version': record.plan_version})
            return PlanResponse(campaign_id=campaign_id, plan_version=record.plan_version,
                                plan=record.plan).model_dump(mode='json')
        key = f'http:metered-strategy:{campaign_id}:{idem_key}'
        result = execute_metered(state, fixture, key, {'campaign_id': campaign_id},
                                 confirmation, 'strategy', generate, deliver)
        return JSONResponse(result, status_code=202)

    def snapshot():
        record = _get_campaign_or_404(state, fixture.tenant_id, campaign_id, principal=principal)
        return sha256(json.dumps(dict(record.brief), sort_keys=True, default=str).encode()).hexdigest(), record.plan_version

    def generate_legacy():
        record = _get_campaign_or_404(state, fixture.tenant_id, campaign_id, principal=principal)
        return _run_strategist(state, fixture, record)

    def deliver_legacy(plan):
        record = _get_campaign_or_404(state, fixture.tenant_id, campaign_id, principal=principal)
        require_brand_assets(state, record)
        record.plan = plan
        record.plan_version += 1
        if record.campaign.state is CampaignState.DRAFT:
            record.campaign.transition_to(CampaignState.STRATEGY_READY, reason="plan:regenerated")
        state.audit.append(tenant_id=fixture.tenant_id, actor=fixture.user_id,
            action="PLAN_REGENERATE", target=record.campaign_id, details={"plan_version": record.plan_version})
        return PlanResponse(campaign_id=record.campaign_id, plan_version=record.plan_version,
                            plan=record.plan).model_dump(mode="json")

    result = execute_unmetered(state, fixture, idem_key, campaign_id,
                               snapshot, generate_legacy, deliver_legacy)
    return JSONResponse(result, status_code=202)


# --------------------------------------------------------------------------- validate


async def validate_campaign(request: Request) -> JSONResponse:
    fixture, state, principal = _authorize(request, Permission.CAMPAIGN_EDIT)
    idem_key = require_idempotency_key(request)
    campaign_id = request.path_params["campaignId"]
    key = f"http:validate_campaign:{idem_key}"
    _get_campaign_or_404(state, fixture.tenant_id, campaign_id, principal=principal)

    existing = state.idempotency.get(fixture.tenant_id, key)
    if existing is not None:
        if existing.result.get("campaign_id") != campaign_id:
            raise ApiError("IDEMPOTENCY_CONFLICT", "A chave identifica outra validação.", status_code=409)
        return JSONResponse(existing.result)

    def _do_validate():
        record = _get_campaign_or_404(
            state, fixture.tenant_id, campaign_id, principal=principal
        )

        if record.campaign.state is CampaignState.DRAFT:
            record.campaign.transition_to(
                CampaignState.STRATEGY_READY, reason="validate:auto"
            )
        if record.campaign.state is CampaignState.STRATEGY_READY:
            record.campaign.transition_to(
                CampaignState.ASSETS_READY, reason="validate:auto"
            )

        channel_support = {
            ch: state.capabilities.is_supported(
                "SIMULATOR",
                f"PUBLISH:{ch}",
                country="BR",
                api_version="sim-1",
            )
            for ch in record.planned_channels
        }
        proposal_text, sensitive_proposal = current_proposal_text(state, record)
        engine = PolicyEngine()
        req = PolicyRequest(
            tenant_id=fixture.tenant_id,
            campaign_id=record.campaign_id,
            plan_version=record.plan_version,
            action=ActionKind.FIRST_PUBLISH,
            autonomy=record.autonomy,
            budget=record.budget,
            requested_amount=Decimal(str(record.brief.get("daily_cap", "0"))),
            channel_support=channel_support,
            brand_restrictions=tuple(),
            brand_guidance=brand_guidance(record),
            brand_assets_ready=brand_assets_ready(state, record),
            plan_text=(str(record.plan.get("output", "")) if record.plan else "") + proposal_text,
            sensitive_audience=sensitive_proposal,
        )
        decision = engine.evaluate(req, now=datetime.now(timezone.utc))
        record.last_policy_decision = decision

        if (
            decision.outcome.value == "APPROVABLE"
            and record.campaign.state is CampaignState.ASSETS_READY
        ):
            record.campaign.transition_to(
                CampaignState.VALIDATED, reason="validate:approvable"
            )

        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="CAMPAIGN_VALIDATE",
            target=record.campaign_id,
            policy_decision_id=decision.policy_decision_id,
        )
        return serialize_policy_decision(decision).model_dump(mode="json")

    result, _replay = state.idempotency.execute(
        fixture.tenant_id, key, _do_validate
    )
    return JSONResponse(result)


# --------------------------------------------------------------------------- publish


async def publish_campaign(request: Request) -> JSONResponse:
    fixture, state, principal = _authorize(request, Permission.CAMPAIGN_PUBLISH)
    require_step_up(request, fixture)
    idem_key = require_idempotency_key(request)
    campaign_id = request.path_params["campaignId"]
    body = await parse_body(request, PublishRequest)
    key = f"http:publish:{idem_key}"
    _get_campaign_or_404(state, fixture.tenant_id, campaign_id, principal=principal)

    # Fast replay path: never revalida estado mutado por uma chamada anterior.
    existing = state.idempotency.get(fixture.tenant_id, key)
    if existing is not None:
        if existing.result.get("id") != campaign_id:
            raise ApiError("IDEMPOTENCY_CONFLICT", "A chave identifica outra publicação.", status_code=409)
        return JSONResponse(existing.result, status_code=202)

    def _do_publish():
        # F3: rele recurso/approval dentro da unidade transacional. Antes de 01/10/2026,
        # VALIDATED -> AWAITING_APPROVAL -> APPROVED era persistido ANTES de
        # idempotency.execute(); uma falha posterior na Saga deixava estado parcial.
        record = _get_campaign_or_404(
            state, fixture.tenant_id, campaign_id, principal=principal
        )
        selected_image = None
        # Image choice must be explicit and pinned to immutable delivery evidence.
        # The publisher remains a simulator; this is NOT proof of a channel media upload.
        if state.db is not None:
            from .creative_image_review import CreativeImageReviewStore, decision_applies
            from campaia_core.creative_assets import CreativeIdentity
            images = []
            for _id, _tenant, image in state.db.table("creative_assets").rows_for_tenant(fixture.tenant_id):
                scope = image["identity"]
                if (scope["campaign_id"] == record.campaign_id
                        and scope["business_unit_id"] == record.business_unit_id
                        and scope["campaign_version"] == record.plan_version
                        and image["state"] not in ("DELETED", "FAILED")):
                    images.append(image)
            if images and not body.selected_creative_id:
                raise ApiError("IMAGE_SELECTION_REQUIRED",
                    "Selecione explicitamente a imagem revisada para publicar.", status_code=409)
            if body.selected_creative_id:
                matching = [image for image in images
                            if image["identity"]["creative_id"] == body.selected_creative_id]
                if len(matching) != 1:
                    raise ApiError("IMAGE_SELECTION_INVALID",
                        "Imagem não pertence à versão e unidade da campanha.", status_code=409)
                selected_image = matching[0]
            for image in images:
                if image["state"] != "STORED":
                    raise ApiError("IMAGE_REVIEW_REQUIRED",
                        "Existe imagem gerada pendente nesta campanha.", status_code=409)
            if selected_image is not None:
                scope = selected_image["identity"]
                review = CreativeImageReviewStore(state).get(CreativeIdentity(**scope))
                if not decision_applies(selected_image, review):
                    raise ApiError("IMAGE_REVIEW_REQUIRED",
                        "A imagem selecionada exige aprovação humana válida.",
                        status_code=409)
        require_brand_assets(state, record)
        enforce_campaign_capacity(state, fixture.tenant_id, record)
        decision = record.last_policy_decision
        if decision is None or decision.policy_decision_id != body.policy_decision_id:
            raise ApiError(
                "APPROVAL_REQUIRED",
                "policy_decision_id does not match the campaign's current policy decision. "
                "Call /validate again.",
            )

        approval = state.approvals.get(fixture.tenant_id, body.approval_id)
        if approval is None or approval.campaign_id != record.campaign_id:
            raise ApiError("APPROVAL_REQUIRED", "approval_id not found for this campaign.")
        if approval.status != "APPROVED":
            raise ApiError("APPROVAL_REQUIRED", "Approval has not been granted.")
        if approval.kind != "PUBLISH" or approval.plan_version != record.plan_version:
            raise ApiError("APPROVAL_REQUIRED", "A aprovação não autoriza publicar esta versão. Solicite uma nova revisão.")
        if approval.requires_dual_approval or decision.requires_dual_approval:
            from campaia_core.permissions import dual_approval_complete

            if not dual_approval_complete(frozenset(approval.decided_by)):
                raise ApiError(
                    "APPROVAL_REQUIRED", "Dual approval is required and not yet complete."
                )

        try:
            if record.campaign.state is CampaignState.VALIDATED:
                record.campaign.transition_to(
                    CampaignState.AWAITING_APPROVAL, reason="publish:auto"
                )
            if record.campaign.state is CampaignState.AWAITING_APPROVAL:
                record.campaign.transition_to(
                    CampaignState.APPROVED, reason="publish:auto"
                )
        except InvalidStateTransition as exc:
            raise from_domain_error(exc)

        if record.campaign.state is not CampaignState.APPROVED:
            raise ApiError(
                "INVALID_STATE",
                f"Campaign must be APPROVED to publish; current state is "
                f"{record.campaign.state.value}.",
            )

        connection = (
            state.connections.get(fixture.tenant_id, record.connection_id)
            if record.connection_id
            else None
        )
        external_account_id = body.external_account_id or (
            connection.external_account_id if connection is not None else "sandbox-account"
        )

        connector = ProviderSimulator()
        saga = PublicationSaga(
            tenant_id=fixture.tenant_id,
            connector=connector,
            budget=record.budget,
            idempotency=state.idempotency,
            compensation_policy=CompensationPolicy.PAUSE_ALL,
        )

        try:
            outcome = saga.run(
                record.campaign,
                channels=record.planned_channels,
                decision=decision,
                approval_id=body.approval_id,
                plan_version=record.plan_version,
                now=datetime.now(timezone.utc),
                external_account_id=external_account_id,
                command_id=idem_key,
                budget_per_channel=(
                    record.budget.limits.daily_cap
                    / max(len(record.planned_channels), 1)
                ),
            )
        except (CampaiaError, ConnectorError) as exc:
            raise from_domain_error(exc)

        approval.status = "APPLIED"

        now = datetime.now(timezone.utc)
        for step in outcome.steps:
            if step.external_resource_id:
                sync_status = (
                    "CONFIRMED"
                    if step.channel in outcome.confirmed_channels
                    else "PENDING"
                )
                record.external_resources[step.channel] = ExternalResourceState(
                    channel=step.channel,
                    external_resource_id=step.external_resource_id,
                    sync_status=sync_status,
                    last_synced_at=now,
                )
        if outcome.confirmed_channels:
            record.last_synced_at = now

        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="CAMPAIGN_PUBLISH",
            target=record.campaign_id,
            policy_decision_id=decision.policy_decision_id,
            details={
                "saga_id": outcome.saga_id,
                "confirmed": outcome.confirmed_channels,
                "failed": outcome.failed_channels,
                "selected_creative": ({
                    "creative_id": selected_image["identity"]["creative_id"],
                    "sha256": selected_image["manifest"]["sha256"],
                    "storage_generation": selected_image["storage_generation"],
                    "campaign_version": record.plan_version,
                } if selected_image is not None else None),
            },
        )
        return serialize_campaign(record).model_dump(mode="json")

    try:
        result, _replay = state.idempotency.execute(
            fixture.tenant_id, key, _do_publish
        )
    except ApiError:
        raise
    except (CampaiaError, ConnectorError) as exc:
        raise from_domain_error(exc)

    return JSONResponse(result, status_code=202)


# --------------------------------------------------------------------------- pause


async def pause_campaign(request: Request) -> JSONResponse:
    fixture, state, principal = _authorize(request, Permission.CAMPAIGN_EDIT)
    idem_key = require_idempotency_key(request)
    campaign_id = request.path_params["campaignId"]

    def _do_pause():
        record = _get_campaign_or_404(
            state, fixture.tenant_id, campaign_id, principal=principal
        )
        try:
            record.campaign.transition_to(CampaignState.PAUSED, reason=f"pause:{idem_key}")
        except InvalidStateTransition as exc:
            raise from_domain_error(exc)

        connector = ProviderSimulator()
        for channel in record.planned_channels:
            from campaia_core.connectors import PublishCommand

            connector.pause(
                PublishCommand(
                    tenant_id=fixture.tenant_id,
                    campaign_id=record.campaign_id,
                    channel=channel,
                    external_account_id="sandbox-account",
                    idempotency_key=f"{idem_key}:{channel}",
                    policy_decision_id=f"pause:{idem_key}",
                    plan_version=record.plan_version,
                )
            )
        # ACHADO 26 (Fase 4, item A, 26/09/2026, REPRODUZIDO por execucao real ao escrever
        # o teste de replay de resume_campaign abaixo): o audit.append precisa estar DENTRO
        # do fecho protegido por `idempotency.execute()`, nao depois -- antes desta correcao,
        # ele rodava incondicionalmente a cada chamada HTTP, inclusive em replays legitimos
        # da MESMA Idempotency-Key, duplicando o evento CAMPAIGN_PAUSE na trilha de
        # auditoria sem nenhuma mutacao real correspondente. Confirmado por execucao real:
        # duas chamadas com a mesma chave -> dois eventos CAMPAIGN_PAUSE, antes da correcao.
        state.audit.append(
            tenant_id=fixture.tenant_id, actor=fixture.user_id, action="CAMPAIGN_PAUSE", target=record.campaign_id
        )
        return serialize_campaign(record).model_dump(mode="json")

    try:
        # SECURITY FIX (Fase C4, 27/09/2026 -- auditoria independente): chave crua, sem
        # namespace de operacao -- a MESMA Idempotency-Key usada aqui e em outra
        # mutacao (ex.: resume_campaign, patch_budget) colidiria no mesmo store
        # (tenant_id, chave), fazendo uma operacao devolver o resultado cacheado da
        # outra por engano. Todo outro endpoint mutante ja usa `http:<operacao>:<chave>`
        # -- este e resume_campaign/revoke_connection eram as 3 exececoes reais.
        result, _replay = state.idempotency.execute(
            fixture.tenant_id, f"http:pause_campaign:{idem_key}", _do_pause
        )
    except ApiError:
        raise
    except CampaiaError as exc:
        raise from_domain_error(exc)

    # Contract: 202 Accepted (achado 4).
    return JSONResponse(result, status_code=202)


# --------------------------------------------------------------------------- resume


async def resume_campaign(request: Request) -> JSONResponse:
    """Fase 4, item A da missao de reconciliacao/takeover (26/09/2026): a maquina de
    estados (campaia_core/states.py) ja modelava e testava PAUSED -> ACTIVE, com sua
    propria guarda (`_guard_resume`) -- FATO CONFIRMADO por leitura real do dominio antes
    de qualquer codigo ser escrito. So faltava exposicao via API; nenhuma mudanca de
    semantica de dominio foi necessaria.

    Exige `Permission.CAMPAIGN_PUBLISH` + step-up (mesmo nivel de cautela de
    `publish_campaign`, nao o de `pause_campaign`/`CAMPAIGN_EDIT`) porque retomar volta a
    gerar gasto externo real -- o mesmo risco que publicar pela primeira vez. NAO exige um
    novo `approval_id`: a guarda de dominio para esta transicao especifica
    (`_guard_resume`) so verifica `kill_switch_active`, nao aprovacao humana -- diferente de
    APPROVED -> PUBLISHING (`_guard_publishing`), que exige uma. Inventar aqui uma exigencia
    de aprovacao que o dominio nao modela seria o erro oposto (mais rigoroso que o dominio
    autoriza), entao a rota segue exatamente o que a guarda real exige, nada mais.

    Deliberadamente NAO chama nenhum metodo de conector para "reativar" o recurso externo:
    `AdsConnector` (campaia_core/connectors.py) so declara `publish`/`pause` -- nao existe
    `resume`/`unpause` no protocolo. A propria chamada `connector.pause(...)` que
    `pause_campaign` faz hoje e simbolica (um `ProviderSimulator()` novo e descartado a
    cada chamada, sem nenhuma leitura posterior de `.paused` em lugar nenhum do codigo --
    confirmado por grep real), entao nao ha nenhum efeito real a espelhar aqui. Definir o
    que uma "retomada" deveria significar para um adaptador real (nova chamada de API do
    provider? republicar? outra coisa?) e uma decisao de protocolo de conector/produto
    ainda pendente, fora do escopo desta exposicao -- nao inventada aqui.
    """
    fixture, state, principal = _authorize(request, Permission.CAMPAIGN_PUBLISH)
    require_step_up(request, fixture)
    idem_key = require_idempotency_key(request)
    campaign_id = request.path_params["campaignId"]

    def _do_resume():
        record = _get_campaign_or_404(
            state, fixture.tenant_id, campaign_id, principal=principal
        )
        enforce_campaign_capacity(state, fixture.tenant_id, record)
        try:
            # TransitionContext() default (kill_switch_active=False) -- mesmo padrao ja
            # usado por publish_campaign/validate_campaign para transition_to() nesta API:
            # nenhum sinal persistente de "kill switch ligado" existe hoje para alimentar
            # este campo (o kill switch real e uma ACAO pontual, `apply_kill_switch`, nao um
            # estado consultavel depois -- ver `kill_switch()`/`_try_pause()` acima).
            record.campaign.transition_to(
                CampaignState.ACTIVE,
                reason=f"resume:{idem_key}",
            )
        except InvalidStateTransition as exc:
            raise from_domain_error(exc)
        # ACHADO 26 (Fase 4, item A, 26/09/2026, REPRODUZIDO por execucao real ao escrever
        # o teste de replay abaixo): o audit.append tem que estar DENTRO deste fecho, senao
        # roda de novo a cada replay legitimo da mesma Idempotency-Key e duplica o evento
        # CAMPAIGN_RESUME sem nenhuma mutacao real correspondente -- mesma classe de bug
        # encontrada e corrigida em pause_campaign nesta mesma sessao.
        state.audit.append(
            tenant_id=fixture.tenant_id, actor=fixture.user_id, action="CAMPAIGN_RESUME", target=record.campaign_id
        )
        return serialize_campaign(record).model_dump(mode="json")

    try:
        # SECURITY FIX (Fase C4, 27/09/2026) -- ver mesma nota em pause_campaign acima.
        result, _replay = state.idempotency.execute(
            fixture.tenant_id, f"http:resume_campaign:{idem_key}", _do_resume
        )
    except ApiError:
        raise
    except CampaiaError as exc:
        raise from_domain_error(exc)

    # Contract: 202 Accepted, mesmo shape de pause_campaign.
    return JSONResponse(result, status_code=202)


# --------------------------------------------------------------------------- budget


async def patch_budget(request: Request) -> JSONResponse:
    fixture, state, principal = _authorize(request, Permission.BUDGET_CHANGE)
    require_step_up(request, fixture)
    idem_key = require_idempotency_key(request)
    campaign_id = request.path_params["campaignId"]
    body = await parse_body(request, BudgetPatchRequest)
    key = f"http:patch_budget:{idem_key}"

    existing = state.idempotency.get(fixture.tenant_id, key)
    if existing is not None:
        return JSONResponse(existing.result, status_code=202)

    def _do_patch():
        from dataclasses import replace

        record = _get_campaign_or_404(
            state, fixture.tenant_id, campaign_id, principal=principal
        )
        approval = state.approvals.get(fixture.tenant_id, body.approval_id)
        if (
            approval is None
            or approval.campaign_id != record.campaign_id
            or approval.kind != "BUDGET_CHANGE"
        ):
            raise ApiError(
                "APPROVAL_REQUIRED",
                "approval_id not found for this budget change.",
            )
        if approval.status != "APPROVED":
            raise ApiError("APPROVAL_REQUIRED", "Approval has not been granted.")

        ok, change_pct, reason = record.budget.validate_change(body.new_daily_cap)
        if not ok:
            raise ApiError(
                "BUDGET_LIMIT",
                reason,
                details={"change_pct": str(change_pct)},
            )

        record.budget.limits = replace(
            record.budget.limits,
            daily_cap=Decimal(str(body.new_daily_cap)),
        )
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="BUDGET_CHANGE",
            target=record.campaign_id,
            details={
                "new_daily_cap": str(body.new_daily_cap),
                "change_pct": str(change_pct),
            },
        )
        approval.status = "APPLIED"
        return serialize_campaign(record).model_dump(mode="json")

    result, _replay = state.idempotency.execute(
        fixture.tenant_id, key, _do_patch
    )
    return JSONResponse(result, status_code=202)


# --------------------------------------------------------------------------- kill switch


def _try_pause(record, reason: str, affected: list[str]) -> None:
    try:
        record.campaign.apply_kill_switch(reason=reason or "kill-switch")
        affected.append(record.campaign_id)
    except InvalidStateTransition:
        pass  # not in a pausable state; kill switch only ever reduces effect, never raises


async def kill_switch(request: Request) -> JSONResponse:
    fixture, state, principal = _authorize(request, Permission.KILL_SWITCH)
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, KillSwitchRequest)

    # Contract enum is uppercase: CAMPAIGN, ACCOUNT, TENANT, PLATFORM, GLOBAL (achado 13).
    # The previous implementation compared against lowercase strings and always failed to
    # match, silently making every kill-switch call a no-op that fell through the branches
    # -- this was the case-sensitivity bug called out in achado 13.
    valid_scopes = {"CAMPAIGN", "ACCOUNT", "TENANT", "PLATFORM", "GLOBAL"}
    if body.scope not in valid_scopes:
        raise ApiError("VALIDATION_FAILED", f"scope must be one of {sorted(valid_scopes)}.")

    def _do_kill_switch():
        affected: list[str] = []
        # Tracks which tenant each affected campaign actually belongs to, so the audit
        # trail below can record the event in EVERY affected tenant's own log -- not just
        # the caller's. Found by independent verification after the P-14 fix pass: the
        # first version of this handler recorded a single KILL_SWITCH audit event scoped
        # to fixture.tenant_id only, so a GLOBAL kill-switch that paused another tenant's
        # campaign left that tenant with no audit trail of it at all -- a real gap for a
        # safety-critical control the contract explicitly says must always be audited
        # ("Ainda assim gera evento e auditoria"). Documented in EVIDENCIA_P14_20260828.md
        # as achado 17.
        affected_tenants: dict[str, str] = {}  # campaign_id -> tenant_id

        if body.scope == "CAMPAIGN":
            if not body.target_id:
                raise ApiError("VALIDATION_FAILED", "target_id is required when scope=CAMPAIGN.")
            record = _get_campaign_or_404(
                state, fixture.tenant_id, body.target_id, principal=principal
            )
            try:
                record.campaign.apply_kill_switch(reason=body.reason or "kill-switch")
            except InvalidStateTransition as exc:
                raise from_domain_error(exc)
            affected.append(record.campaign_id)
            affected_tenants[record.campaign_id] = record.tenant_id

        elif body.scope == "ACCOUNT":
            # No dedicated "account" concept exists in the current repositories beyond a
            # Connection. Interpreting target_id as a connection_id and pausing every
            # campaign in this tenant published through that connection is the most
            # reasonable mapping given today's model -- documented simplification (achado 13).
            if not body.target_id:
                raise ApiError("VALIDATION_FAILED", "target_id is required when scope=ACCOUNT.")
            for record in state.campaigns.list_for_tenant(fixture.tenant_id):
                if record.connection_id == body.target_id:
                    _try_pause(record, body.reason, affected)
                    if record.campaign_id in affected:
                        affected_tenants[record.campaign_id] = record.tenant_id

        elif body.scope == "TENANT":
            for record in state.campaigns.list_for_tenant(fixture.tenant_id):
                _try_pause(record, body.reason, affected)
                if record.campaign_id in affected:
                    affected_tenants[record.campaign_id] = record.tenant_id

        elif body.scope == "PLATFORM":
            # "Platform" reads as "channel" in this domain (Channel enum: GOOGLE_ADS,
            # META_FACEBOOK, META_INSTAGRAM, WHATSAPP) -- target_id is interpreted as a
            # channel name, and every campaign in the tenant planning that channel is
            # paused, regardless of which connection/account it uses. Documented
            # simplification: there is no separate "platform" entity in this domain
            # beyond channel (achado 13).
            if not body.target_id:
                raise ApiError("VALIDATION_FAILED", "target_id (channel) is required when scope=PLATFORM.")
            for record in state.campaigns.list_for_tenant(fixture.tenant_id):
                if body.target_id in record.planned_channels:
                    _try_pause(record, body.reason, affected)
                    if record.campaign_id in affected:
                        affected_tenants[record.campaign_id] = record.tenant_id

        elif body.scope == "GLOBAL":
            # SECURITY FIX (Fase C1, 27/09/2026 -- auditoria independente): a versao
            # anterior tratava GLOBAL como "excecao deliberada ao isolamento de tenant",
            # mas a unica autorizacao verificada era Permission.KILL_SWITCH, concedida a
            # OWNER/FINANCE/APPROVER *dentro do proprio tenant*. Isso permitia que
            # QUALQUER tenant pausasse campanhas de QUALQUER outro tenant so por ter
            # KILL_SWITCH no seu proprio escopo -- confirmado por teste real
            # (test_kill_switch_global_scope_crosses_tenants, tests_api/test_smoke_endpoints.py)
            # que provava a falha como se fosse comportamento correto. Nao existe hoje
            # nenhum conceito de PLATFORM_ADMIN (autoridade de plataforma, distinta da
            # autoridade comum de tenant) em campaia_core.permissions -- ate essa
            # autoridade existir de verdade, GLOBAL fica fail-closed: nunca executa,
            # nunca afeta nenhuma campanha, de nenhum tenant, incluindo o do proprio
            # chamador.
            raise ApiError(
                "PERMISSION_DENIED",
                "scope=GLOBAL exige autoridade de plataforma (PLATFORM_ADMIN), que ainda "
                "nao existe neste sistema. Nenhuma campanha foi afetada.",
            )

        # Always record the event in the CALLER's own tenant, even when nothing was
        # affected there directly (e.g. a GLOBAL call from a tenant with no campaigns of
        # its own) -- this is who triggered the kill-switch and must be traceable.
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="KILL_SWITCH",
            target=body.target_id or body.scope,
            details={"scope": body.scope, "reason": body.reason, "affected": affected},
        )
        # Additionally record the same event in every OTHER tenant that had a campaign
        # affected (relevant for ACCOUNT/PLATFORM in theory and GLOBAL in practice, since
        # those are the only scopes that can touch a tenant other than the caller's).
        other_tenants_affected = {
            tid for cid, tid in affected_tenants.items() if tid != fixture.tenant_id
        }
        for other_tenant_id in other_tenants_affected:
            campaigns_in_that_tenant = [
                cid for cid, tid in affected_tenants.items() if tid == other_tenant_id
            ]
            state.audit.append(
                tenant_id=other_tenant_id,
                actor=fixture.user_id,
                action="KILL_SWITCH",
                target=body.target_id or body.scope,
                details={
                    "scope": body.scope,
                    "reason": body.reason,
                    "affected": campaigns_in_that_tenant,
                    "triggered_by_tenant": fixture.tenant_id,
                },
            )
        return {"scope": body.scope, "affected_campaign_ids": affected}

    result, _replay = state.idempotency.execute(
        fixture.tenant_id, f"http:kill_switch:{idem_key}", _do_kill_switch
    )
    # Contract: 202 Accepted (achado 4).
    return JSONResponse(result, status_code=202)


# --------------------------------------------------------------------------- insights


async def get_insights(request: Request) -> JSONResponse:
    """Honest placeholder: there is no analytics layer in campaia_core yet.

    Returns an empty points list rather than fabricating numbers. This is a genuine known
    gap, not a simulated success. The `from`/`to` query params are validated (parseable
    ISO dates) per the contract, even though the empty result never actually uses them
    yet (achado 14) -- validating them now means client integration against these params
    can start before the analytics layer exists.
    """
    fixture, state, principal = _authorize(request, Permission.CAMPAIGN_VIEW)
    record = _get_campaign_or_404(
        state, fixture.tenant_id, request.path_params["campaignId"], principal=principal
    )

    from_raw = request.query_params.get("from")
    to_raw = request.query_params.get("to")
    for label, raw in (("from", from_raw), ("to", to_raw)):
        if raw is not None:
            try:
                date.fromisoformat(raw)
            except ValueError:
                raise ApiError("VALIDATION_FAILED", f"Query param '{label}' must be an ISO date (YYYY-MM-DD).")

    return json_response(
        InsightSeriesResponse(
            campaign_id=record.campaign_id,
            points=[],
            last_synced_at=record.last_synced_at,
            note="No analytics layer implemented yet in campaia_core; this is an honest "
            "placeholder, not fabricated data.",
        )
    )
