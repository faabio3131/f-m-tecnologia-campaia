from __future__ import annotations

from datetime import date, datetime, timezone
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
    PublishRequest,
)
from .repositories import ExternalResourceState


def _authorize(request: Request, permission: Permission, *, amount: Decimal | None = None):
    fixture = require_auth(request)
    state = get_state(request)
    note_step_up_header(request, fixture)
    principal = build_domain_principal(state, fixture)
    resource = Resource(tenant_id=fixture.tenant_id, business_unit_id=fixture.business_unit_id)
    decision = authorize(principal, permission, resource, now=datetime.now(timezone.utc), amount=amount)
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)
    return fixture, state, principal


def _get_campaign_or_404(state, tenant_id: str, campaign_id: str):
    record = state.campaigns.get(tenant_id, campaign_id)
    if record is None:
        raise ApiError("NOT_FOUND", "Campaign not found.")
    return record


# --------------------------------------------------------------------------- briefs


async def create_brief(request: Request) -> JSONResponse:
    fixture, state, _principal = _authorize(request, Permission.CAMPAIGN_CREATE)
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, BriefCreate)

    if body.connection_id is not None:
        conn = state.connections.get(fixture.tenant_id, body.connection_id)
        if conn is None:
            raise ApiError("NOT_FOUND", "connection_id does not reference a known connection.")

    def _do_create():
        record = state.campaigns.create(
            fixture.tenant_id,
            brief=body.model_dump(mode="json"),
            business_unit_id=body.business_unit_id or fixture.business_unit_id,
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
        return serialize_campaign(record).model_dump(mode="json")

    result, _replay = state.idempotency.execute(
        fixture.tenant_id, f"http:create_brief:{idem_key}", _do_create
    )
    # Contract: 202 Accepted -- strategy generation happens asynchronously (achado 4).
    return JSONResponse(result, status_code=202)


# --------------------------------------------------------------------------- campaigns


async def list_campaigns(request: Request) -> JSONResponse:
    fixture, state, _principal = _authorize(request, Permission.CAMPAIGN_VIEW)
    records = state.campaigns.list_for_tenant(fixture.tenant_id)

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
    fixture, state, _principal = _authorize(request, Permission.CAMPAIGN_VIEW)
    record = _get_campaign_or_404(state, fixture.tenant_id, request.path_params["campaignId"])
    return json_response(serialize_campaign(record))


# --------------------------------------------------------------------------- plan


def _run_strategist(state, fixture, record) -> dict:
    """Wire to agents.AgentRunner + the SimulatedAIProvider. Never a real provider."""
    context = {
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
    # AgentFailure
    raise ApiError(
        "VALIDATION_FAILED",
        f"Plan generation failed: {result.reason}",
        details={"missing_context": list(result.missing_context)},
    )


async def get_plan(request: Request) -> JSONResponse:
    fixture, state, _principal = _authorize(request, Permission.CAMPAIGN_VIEW)
    record = _get_campaign_or_404(state, fixture.tenant_id, request.path_params["campaignId"])
    return json_response(
        PlanResponse(campaign_id=record.campaign_id, plan_version=record.plan_version, plan=record.plan)
    )


async def regenerate_plan(request: Request) -> JSONResponse:
    fixture, state, _principal = _authorize(request, Permission.CAMPAIGN_EDIT)
    idem_key = require_idempotency_key(request)
    record = _get_campaign_or_404(state, fixture.tenant_id, request.path_params["campaignId"])

    def _do_regenerate():
        plan = _run_strategist(state, fixture, record)
        record.plan = plan
        record.plan_version += 1

        if record.campaign.state is CampaignState.DRAFT:
            record.campaign.transition_to(CampaignState.STRATEGY_READY, reason="plan:regenerated")

        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="PLAN_REGENERATE",
            target=record.campaign_id,
            details={"plan_version": record.plan_version},
        )
        return PlanResponse(
            campaign_id=record.campaign_id, plan_version=record.plan_version, plan=record.plan
        ).model_dump(mode="json")

    result, _replay = state.idempotency.execute(
        fixture.tenant_id, f"http:regenerate_plan:{idem_key}", _do_regenerate
    )
    # Contract: 202 Accepted -- plan (re)generation is treated as async (achado 4).
    return JSONResponse(result, status_code=202)


# --------------------------------------------------------------------------- validate


async def validate_campaign(request: Request) -> JSONResponse:
    fixture, state, _principal = _authorize(request, Permission.CAMPAIGN_EDIT)
    record = _get_campaign_or_404(state, fixture.tenant_id, request.path_params["campaignId"])

    if record.campaign.state in (CampaignState.DRAFT,):
        # Advance the local state machine through the pre-validation states so /validate
        # reflects "this campaign is ready to be judged", mirroring the campaign lifecycle
        # documented in states.py (DRAFT -> STRATEGY_READY -> ASSETS_READY -> VALIDATED).
        record.campaign.transition_to(CampaignState.STRATEGY_READY, reason="validate:auto")
    if record.campaign.state is CampaignState.STRATEGY_READY:
        record.campaign.transition_to(CampaignState.ASSETS_READY, reason="validate:auto")

    # Missão de fechamento integral (Etapa A13, 22/09/2026): this used to query the
    # registry by the literal provider key "SIMULATOR" -- a ConnectionMode value, never a
    # real Provider one (achado real, found while fixing the same registry's other real
    # caller, routes_connections.connection_capabilities, which queries by the actual
    # provider). capability_key (f"PUBLISH:{ch}") already fully differentiates by channel,
    # so this never changed which channels validated as supported -- but it meant this
    # call site and connection_capabilities' could never share the same seeded entries.
    # Aligning both onto one convention (provider = the real ads provider name) closes
    # that inconsistency at its root rather than seeding two parallel copies of the same
    # data under two different keys.
    channel_support = {
        ch: state.capabilities.is_supported(ch, f"PUBLISH:{ch}", country="BR", api_version="sim-1")
        for ch in record.planned_channels
    }

    engine = PolicyEngine()
    req = PolicyRequest(
        tenant_id=fixture.tenant_id,
        campaign_id=record.campaign_id,
        plan_version=record.plan_version,
        action=ActionKind.FIRST_PUBLISH,
        autonomy=record.autonomy,
        budget=record.budget,
        # Validate against the daily cap, not the total budget: PolicyEngine checks
        # requested_amount against both available_total and available_today (budget.py),
        # and the amount that will actually be committed on day one of publishing is
        # bounded by the daily cap, not the full campaign lifetime budget.
        requested_amount=Decimal(str(record.brief.get("daily_cap", "0"))),
        channel_support=channel_support,
        brand_restrictions=tuple(),
        plan_text=str(record.plan.get("output", "")) if record.plan else "",
    )
    decision = engine.evaluate(req, now=datetime.now(timezone.utc))
    record.last_policy_decision = decision

    if decision.outcome.value == "APPROVABLE" and record.campaign.state is CampaignState.ASSETS_READY:
        record.campaign.transition_to(CampaignState.VALIDATED, reason="validate:approvable")

    state.audit.append(
        tenant_id=fixture.tenant_id,
        actor=fixture.user_id,
        action="CAMPAIGN_VALIDATE",
        target=record.campaign_id,
        policy_decision_id=decision.policy_decision_id,
    )
    return json_response(serialize_policy_decision(decision))


# --------------------------------------------------------------------------- publish


async def publish_campaign(request: Request) -> JSONResponse:
    fixture, state, principal = _authorize(request, Permission.CAMPAIGN_PUBLISH)
    require_step_up(request, fixture)
    idem_key = require_idempotency_key(request)
    record = _get_campaign_or_404(state, fixture.tenant_id, request.path_params["campaignId"])
    body = await parse_body(request, PublishRequest)

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
    if approval.requires_dual_approval:
        from campaia_core.permissions import dual_approval_complete

        if not dual_approval_complete(frozenset(approval.decided_by)):
            raise ApiError("APPROVAL_REQUIRED", "Dual approval is required and not yet complete.")

    # Idempotency check happens BEFORE any state-machine mutation: on replay, the
    # campaign has already moved past APPROVED (e.g. to ACTIVE) from the first call, so
    # the "must be APPROVED" gate below must never run again for a replayed key -- only
    # for a genuinely new attempt. This is what makes repeating the same Idempotency-Key
    # return the original result instead of re-executing (invariant #3 in the task spec).
    existing = state.idempotency.get(fixture.tenant_id, f"http:publish:{idem_key}")
    if existing is not None:
        return json_response(serialize_campaign(record), status_code=202)

    # Walk the state machine forward to APPROVED using the already-recorded, already-
    # decided approval -- mirroring what a full approvals UI would have already driven.
    # PublicationSaga.run() itself only accepts campaigns in APPROVED (it transitions
    # APPROVED -> PUBLISHING under its own guard), so this has to land exactly there.
    try:
        if record.campaign.state is CampaignState.VALIDATED:
            record.campaign.transition_to(CampaignState.AWAITING_APPROVAL, reason="publish:auto")
        if record.campaign.state is CampaignState.AWAITING_APPROVAL:
            record.campaign.transition_to(CampaignState.APPROVED, reason="publish:auto")
    except InvalidStateTransition as exc:
        raise from_domain_error(exc)

    if record.campaign.state is not CampaignState.APPROVED:
        raise ApiError(
            "INVALID_STATE",
            f"Campaign must be APPROVED to publish; current state is "
            f"{record.campaign.state.value}.",
        )

    external_account_id = body.external_account_id or (
        state.connections.get(fixture.tenant_id, record.connection_id).external_account_id
        if record.connection_id
        else "sandbox-account"
    )

    connector = ProviderSimulator()
    saga = PublicationSaga(
        tenant_id=fixture.tenant_id,
        connector=connector,
        budget=record.budget,
        idempotency=state.idempotency,
        compensation_policy=CompensationPolicy.PAUSE_ALL,
    )

    def _do_publish():
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
                # Split the DAILY cap across channels, not the lifetime total: the Saga
                # reserves this amount immediately (budget.py.reserve checks it against
                # both available_total AND available_today), so using the total budget
                # here would nearly always blow the daily cap and fail every channel.
                budget_per_channel=(
                    record.budget.limits.daily_cap / max(len(record.planned_channels), 1)
                ),
            )
        except (CampaiaError, ConnectorError) as exc:
            raise from_domain_error(exc)
        return outcome

    # Idempotency at the HTTP boundary: repeating the same Idempotency-Key returns the
    # original saga outcome instead of re-running the saga (which itself is also
    # idempotent per-channel via campaia_core.infra.IdempotencyStore).
    try:
        outcome, _replay = state.idempotency.execute(fixture.tenant_id, f"http:publish:{idem_key}", _do_publish)
    except ApiError:
        raise
    except (CampaiaError, ConnectorError) as exc:
        raise from_domain_error(exc)

    now = datetime.now(timezone.utc)
    for step in outcome.steps:
        if step.external_resource_id:
            # sync_status: CONFIRMED once the channel is in outcome.confirmed_channels,
            # else PENDING. There is no per-channel DIVERGENT detection anywhere in the
            # domain layer yet, so DIVERGENT is never produced here (documented gap).
            sync_status = "CONFIRMED" if step.channel in outcome.confirmed_channels else "PENDING"
            record.external_resources[step.channel] = ExternalResourceState(
                channel=step.channel,
                external_resource_id=step.external_resource_id,
                sync_status=sync_status,
                # No per-channel reconciliation timestamp exists in the domain layer --
                # reusing the moment this channel's resource id was recorded as its own
                # last_synced_at (documented simplification, see repositories.CampaignRecord).
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
        details={"saga_id": outcome.saga_id, "confirmed": outcome.confirmed_channels, "failed": outcome.failed_channels},
    )
    return json_response(serialize_campaign(record), status_code=202)


# --------------------------------------------------------------------------- pause


async def pause_campaign(request: Request) -> JSONResponse:
    fixture, state, _principal = _authorize(request, Permission.CAMPAIGN_EDIT)
    idem_key = require_idempotency_key(request)
    record = _get_campaign_or_404(state, fixture.tenant_id, request.path_params["campaignId"])

    def _do_pause():
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
        return serialize_campaign(record).model_dump(mode="json")

    try:
        result, _replay = state.idempotency.execute(fixture.tenant_id, idem_key, _do_pause)
    except ApiError:
        raise
    except CampaiaError as exc:
        raise from_domain_error(exc)

    state.audit.append(
        tenant_id=fixture.tenant_id, actor=fixture.user_id, action="CAMPAIGN_PAUSE", target=record.campaign_id
    )
    # Contract: 202 Accepted (achado 4).
    return JSONResponse(result, status_code=202)


# --------------------------------------------------------------------------- budget


async def patch_budget(request: Request) -> JSONResponse:
    fixture, state, _principal = _authorize(request, Permission.BUDGET_CHANGE)
    require_step_up(request, fixture)
    idem_key = require_idempotency_key(request)
    record = _get_campaign_or_404(state, fixture.tenant_id, request.path_params["campaignId"])
    body = await parse_body(request, BudgetPatchRequest)

    approval = state.approvals.get(fixture.tenant_id, body.approval_id)
    if approval is None or approval.campaign_id != record.campaign_id or approval.kind != "BUDGET_CHANGE":
        raise ApiError("APPROVAL_REQUIRED", "approval_id not found for this budget change.")
    if approval.status != "APPROVED":
        raise ApiError("APPROVAL_REQUIRED", "Approval has not been granted.")

    # Idempotency check happens BEFORE the mutation for the same reason as publish_campaign:
    # on replay, validate_change/limits-replace must not run a second time.
    existing = state.idempotency.get(fixture.tenant_id, f"http:patch_budget:{idem_key}")
    if existing is not None:
        return json_response(serialize_campaign(record), status_code=202)

    ok, change_pct, reason = record.budget.validate_change(body.new_daily_cap)
    if not ok:
        raise ApiError("BUDGET_LIMIT", reason, details={"change_pct": str(change_pct)})

    def _do_patch():
        # BudgetEngine has no direct "set daily_cap" mutator (limits is frozen) -- replace
        # the BudgetLimits with a new one carrying the same total/currency/policy, only
        # daily_cap changed. This preserves spent_total/spent_today/reservations on the
        # engine instance.
        from dataclasses import replace

        record.budget.limits = replace(record.budget.limits, daily_cap=Decimal(str(body.new_daily_cap)))

        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="BUDGET_CHANGE",
            target=record.campaign_id,
            details={"new_daily_cap": str(body.new_daily_cap), "change_pct": str(change_pct)},
        )
        return True

    state.idempotency.execute(fixture.tenant_id, f"http:patch_budget:{idem_key}", _do_patch)
    # Contract: 202 Accepted (achado 4).
    return json_response(serialize_campaign(record), status_code=202)


# --------------------------------------------------------------------------- kill switch


def _try_pause(record, reason: str, affected: list[str]) -> None:
    try:
        record.campaign.apply_kill_switch(reason=reason or "kill-switch")
        affected.append(record.campaign_id)
    except InvalidStateTransition:
        pass  # not in a pausable state; kill switch only ever reduces effect, never raises


async def kill_switch(request: Request) -> JSONResponse:
    fixture, state, _principal = _authorize(request, Permission.KILL_SWITCH)
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
            record = _get_campaign_or_404(state, fixture.tenant_id, body.target_id)
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
            # Deliberate, documented exception to tenant isolation: GLOBAL kill-switch is
            # the one operation in this system that must cross every tenant by definition
            # (achado 13). It still only ever pauses (reduces effect), never widens it, and
            # every affected campaign is recorded in ITS OWN tenant's audit log below
            # (achado 17 fix -- see audit loop after this branch).
            for record in state.campaigns._items.values():
                _try_pause(record, body.reason, affected)
                if record.campaign_id in affected:
                    affected_tenants[record.campaign_id] = record.tenant_id

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
    fixture, state, _principal = _authorize(request, Permission.CAMPAIGN_VIEW)
    record = _get_campaign_or_404(state, fixture.tenant_id, request.path_params["campaignId"])

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
