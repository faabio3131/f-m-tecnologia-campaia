"""Superficie HTTP do motor de cobranca propria do CampaIA (B11 / ADR-0020).

Uma assinatura por tenant, catalogo configurado, lifecycle, cobranca por competencia e
webhook Asaas. Condicoes comerciais sao dados externos; nao ha catalogo padrao.

O webhook (`POST /webhooks/asaas`) e o UNICO endpoint deste arquivo sem autenticacao de
usuario: quem chama e o Asaas, nao o app. A autenticidade vem da verificacao de token do
proprio `AsaasWebhookReceiver` (`asaas-access-token`), nunca de um Bearer token de usuario.
"""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import asdict, replace
from contextlib import nullcontext
from hashlib import sha256
import json
from decimal import Decimal
from uuid import uuid4

from campaia_core.credit_ledger import ExtraCreditConsent
from campaia_core.billing_cycles import PaidCycleSchedule, period_index, COMMERCIAL_TIMEZONE
from .billing_closure import record_closed_lifecycle, closure_quote, final_charge, close_without_invoice, require_final_usage_resolved, result_key as closure_result_key
from .billing_void import withdrawal_quote, withdrawal_state, withdrawal_observed_at, withdraw_unpaid_renewal, verified_void, intent_key as void_intent_key
from .billing_facts import record_settled_fact
from .billing_guarantee import guarantee_quote, request_guarantee
from .billing_receipts import has_reversal_signal, observe_payment, require_no_payment_review, has_payment_review, payment_access_is_blocked
from .billing_checkout import checkout_quote
from .billing_dispatch import execute_invoice, obligation_key
from .billing_credits import grant_current_cycle, grant_paid_cycle, usage_payload, cycle_snapshot

from starlette.requests import Request
from starlette.responses import JSONResponse

from campaia_core.asaas_gateway import map_asaas_status
from campaia_core.asaas_webhook import AsaasPaymentEvent, parse_asaas_payment_event
from campaia_core.billing_settlement import charge_command, charge_subscription, dispatch_frozen_charge, try_settle_from_status
from campaia_core.fiscal_handoff import build_campaia_fiscal_handoff
from campaia_core.payment_gateway import GatewayChargeStatus, PaymentGatewayError
from campaia_core.payment_urls import safe_asaas_invoice_url
from campaia_core.permissions import Permission, Resource, authorize
from campaia_core.plan_catalog import PlanCatalogError, get_plan, load_plan_catalog
from campaia_core.subscription import (
    ChargePurpose,
    ChargeLineItem,
    ChargeStatus,
    PlanChangeKind,
    activate_commercial_payment,
    undo_commercial_plan_change,
    PlanChangeBillingMode,
    PlanDefinition,
    ReactivationBillingMode,
    Subscription,
    SubscriptionStatus,
    activate_from_settled_payment,
    cancel_subscription,
    compute_cycle_charge,
    entitlement_access_is_active,
    mark_past_due,
    next_dunning_reminder_at,
    past_due_is_in_grace,
    refresh_trial_status,
    request_plan_change,
    request_reactivation,
    start_trial,
)

from .deps import (
    build_domain_principal,
    get_state,
    note_step_up_header,
    require_auth,
    require_idempotency_key,
)
from .errors import ApiError
from .helpers import parse_body
from .models import (
    ApiModel,
    BillingCreditConsentRequest,
    BillingWithdrawalRequest,
    BillingCancellationRequest,
    BillingChargeCreate,
    BillingClosureRequest,
    BillingCheckoutResponse,
    BillingChargeResponse,
    BillingChargeHistoryItem,
    BillingChargeHistoryResponse,
    BillingEntitlementsResponse,
    BillingPlanChangeRequest,
    BillingPlanResponse,
    BillingSubscriptionResponse,
    BillingSubscriptionUpsert,
)
from .state import AppState


def _authorize_billing(request: Request, permission: Permission):
    fixture = require_auth(request)
    note_step_up_header(request, fixture)
    state = get_state(request)
    principal = build_domain_principal(request, state, fixture)
    resource = Resource(tenant_id=fixture.tenant_id)
    decision = authorize(principal, permission, resource, now=datetime.now(timezone.utc))
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)
    return fixture, state


def _serialize_plan(plan: PlanDefinition) -> BillingPlanResponse:
    return BillingPlanResponse(
        fingerprint=_plan_fingerprint(plan),
        plan_id=plan.plan_id,
        name=plan.name,
        currency=plan.currency,
        monthly_price=str(plan.monthly_price),
        included_credits=str(plan.included_credits),
        extra_credit_unit_price=str(plan.extra_credit_unit_price),
        trial_days=plan.trial_days,
        credit_policy=({**asdict(plan.credit_policy), "action_weights": dict(plan.credit_policy.action_weights)}
                       if plan.credit_policy else None),
        cancellation_mode=plan.cancellation_mode,
        reactivation_mode=plan.reactivation_mode,
        reactivation_billing_mode=plan.reactivation_billing_mode,
        plan_changes=[{
            "target_plan_id": rule.target_plan_id,
            "kind": rule.kind.value,
            "activation": rule.activation.value,
            "billing_mode": rule.billing_mode.value if rule.billing_mode else None,
        } for rule in plan.plan_changes],
    )


def _plan_fingerprint(plan: PlanDefinition) -> str:
    # Includes entitlements/lifecycle rules too: changing anything the customer is
    # selecting requires a fresh review. No secret or tenant identifier is included.
    return sha256(json.dumps(asdict(plan), sort_keys=True, default=str).encode()).hexdigest()


async def list_billing_plans(request: Request) -> JSONResponse:
    _authorize_billing(request, Permission.BILLING_VIEW)
    try:
        catalog = load_plan_catalog()
    except (PlanCatalogError, OSError, ValueError) as exc:
        raise ApiError(
            "BILLING_CATALOG_UNAVAILABLE",
            "Catálogo de planos indisponível neste ambiente.",
            status_code=503,
        ) from exc
    return JSONResponse({"items": [
        _serialize_plan(plan).model_dump(mode="json") for plan in catalog.values()
    ]})


def _serialize_subscription(sub: Subscription, *, state=None) -> dict:
    current = refresh_trial_status(sub)
    entitlements = current.plan.entitlements
    entitlement_payload = None
    if entitlements is not None:
        entitlement_payload = BillingEntitlementsResponse(
            max_users=(current.plan.credit_policy.trial_max_users
                       if current.status is SubscriptionStatus.TRIAL and current.plan.credit_policy
                       else current.plan.effective_max_users),
            max_active_campaigns=(current.plan.credit_policy.trial_max_active_campaigns
                                  if current.status is SubscriptionStatus.TRIAL and current.plan.credit_policy
                                  else entitlements.max_active_campaigns),
            channels=list(entitlements.channels),
            ai_capabilities=list(entitlements.ai_capabilities),
            resources=list(entitlements.resources),
        )

    period = None
    schedule = current.paid_cycle_schedule
    if schedule is not None and schedule.anchor_at is not None:
        index = schedule.current_paid_index(datetime.now(timezone.utc))
        period = schedule.bounds(index if index is not None else schedule.paid_through_index)
    pending_entitlements = None
    if current.pending_plan and current.pending_plan.entitlements:
        e = current.pending_plan.entitlements
        pending_entitlements = BillingEntitlementsResponse(max_users=current.pending_plan.effective_max_users,
            max_active_campaigns=e.max_active_campaigns, channels=list(e.channels),
            ai_capabilities=list(e.ai_capabilities), resources=list(e.resources))
    return BillingSubscriptionResponse(
        commercial_terms=_serialize_plan(current.plan),
        tenant_id=current.tenant_id,
        customer_ref=current.customer_ref,
        customer_document=current.customer_document,
        plan_id=current.plan.plan_id,
        plan_name=current.plan.name,
        status=current.status.value,
        trial_started_at=current.trial_started_at,
        trial_ends_at=current.trial_ends_at,
        activated_at=current.activated_at,
        pending_plan_id=(current.pending_plan.plan_id if current.pending_plan else None),
        pending_plan_name=(current.pending_plan.name if current.pending_plan else None),
        pending_plan_change_kind=(
            current.pending_plan_change_kind.value
            if current.pending_plan_change_kind is not None
            else None
        ),
        pending_plan_change_billing_mode=(
            current.pending_plan_change_billing_mode.value
            if current.pending_plan_change_billing_mode is not None
            else None
        ),
        cancel_at_period_end=current.cancel_at_period_end,
        pending_plan_effective_at=current.pending_plan_effective_at,
        paid_period_starts_at=period[0] if period else None,
        paid_period_ends_at=period[1] if period else None,
        pending_plan_entitlements=pending_entitlements,
        canceled_at=current.canceled_at,
        reactivation_requested_at=current.reactivation_requested_at,
        past_due_at=current.past_due_at,
        grace_period_ends_at=current.grace_period_ends_at,
        past_due_in_grace=past_due_is_in_grace(current),
        past_due_access_mode=(
            current.plan.dunning_policy.access_mode.value
            if current.plan.dunning_policy is not None
            else None
        ),
        dunning_reminders_sent=current.dunning_reminders_sent,
        next_dunning_reminder_at=next_dunning_reminder_at(current),
        payment_review_required=has_payment_review(state, sub.tenant_id) if state is not None else False,
        entitlement_access_active=(entitlement_access_is_active(current) and (state is None or not
            payment_access_is_blocked(state, current, at=datetime.now(timezone.utc)))),
        entitlements=entitlement_payload,
    ).model_dump(mode="json")


def _require_subscription(state: AppState, tenant_id: str) -> Subscription:
    with state.db.transaction() if state.db is not None else nullcontext():
        if state.db is not None:
            state.idempotency._table.lock_key(f"tenant:{tenant_id}")
        subscription = state.subscriptions.get(tenant_id)
        if subscription is None:
            raise ApiError("NOT_FOUND", "Nenhuma assinatura configurada para este tenant.")
        refreshed = refresh_trial_status(subscription, now=datetime.now(timezone.utc))
        if refreshed != subscription:
            state.subscriptions[tenant_id] = refreshed
            action = ("BILLING_TRIAL_EXPIRED" if subscription.status is SubscriptionStatus.TRIAL
                      and refreshed.status is SubscriptionStatus.EXPIRED else "BILLING_SUBSCRIPTION_REFRESHED")
            state.audit.append(tenant_id=tenant_id, actor="system", actor_kind="SYSTEM",
                               action=action, target=refreshed.plan.plan_id)
        record_closed_lifecycle(state, refreshed)
        return refreshed


async def put_subscription(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_MANAGE)
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, BillingSubscriptionUpsert)
    if body.initial_only and body.expected_plan_fingerprint is None:
        raise ApiError("VALIDATION_FAILED", "Revise as condições do plano antes de confirmar.")

    def _do_upsert() -> dict:
        try:
            catalog = load_plan_catalog()
            plan = get_plan(body.plan_id, catalog)
        except (PlanCatalogError, OSError, ValueError) as exc:
            raise ApiError(
                "BILLING_CATALOG_UNAVAILABLE", "Catálogo de planos indisponível neste ambiente.", status_code=503
            ) from exc

        existing = state.subscriptions.get(fixture.tenant_id)
        if existing is not None and body.initial_only:
            raise ApiError("BILLING_SUBSCRIPTION_ALREADY_EXISTS",
                           "Já existe uma assinatura. Recarregue a página para consultá-la.", status_code=409)
        if (body.expected_plan_fingerprint is not None
                and body.expected_plan_fingerprint != _plan_fingerprint(plan)):
            raise ApiError("BILLING_PLAN_CHANGED",
                           "As condições do plano mudaram. Recarregue a página e revise a seleção.", status_code=409)
        if existing is not None and existing.plan.plan_id != plan.plan_id:
            raise ApiError(
                "BILLING_PLAN_CHANGE_REQUIRES_EXPLICIT_FLOW",
                "Troca de plano deve usar POST /billing/subscription/change-plan.",
                status_code=409,
            )

        try:
            if existing is None:
                subscription = Subscription(
                    tenant_id=fixture.tenant_id,
                    customer_ref=fixture.tenant_id,
                    customer_document=body.customer_document,
                    plan=plan,
                    status=SubscriptionStatus.PENDING_PAYMENT,
                    paid_cycle_schedule=(PaidCycleSchedule(uuid4().hex) if plan.credit_policy else None),
                )
            else:
                subscription = Subscription(
                    tenant_id=existing.tenant_id,
                    customer_ref=existing.customer_ref,
                    customer_document=body.customer_document,
                    plan=existing.plan,
                    status=existing.status,
                    trial_started_at=existing.trial_started_at,
                    trial_ends_at=existing.trial_ends_at,
                    activated_at=existing.activated_at,
                    pending_plan=existing.pending_plan,
                    pending_plan_change_kind=existing.pending_plan_change_kind,
                    pending_plan_change_billing_mode=existing.pending_plan_change_billing_mode,
                    canceled_at=existing.canceled_at,
                    reactivation_requested_at=existing.reactivation_requested_at,
                    past_due_at=existing.past_due_at,
                    grace_period_ends_at=existing.grace_period_ends_at,
                    dunning_reminders_sent=existing.dunning_reminders_sent,
                    last_dunning_at=existing.last_dunning_at,
                    paid_cycle_schedule=existing.paid_cycle_schedule,
                    extra_credit_consent=existing.extra_credit_consent,
                    cancel_at_period_end=existing.cancel_at_period_end,
                    pending_plan_effective_at=existing.pending_plan_effective_at,
                )

            if body.start_trial:
                subscription = start_trial(
                    subscription,
                    now=datetime.now(timezone.utc),
                )
        except ValueError as exc:
            raise ApiError("VALIDATION_FAILED", str(exc)) from exc

        grant_current_cycle(state, subscription, at=datetime.now(timezone.utc))
        state.subscriptions[fixture.tenant_id] = subscription
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="BILLING_SUBSCRIPTION_UPSERT",
            target=body.plan_id,
            details={
                "status": subscription.status.value,
                "trial_requested": body.start_trial,
                "initial_only": body.initial_only,
                "plan_fingerprint": _plan_fingerprint(subscription.plan),
            },
        )
        return _serialize_subscription(subscription, state=state)

    result, _replay = state.idempotency.execute(
        fixture.tenant_id, f"http:billing_subscription_upsert:{idem_key}", _do_upsert
    )
    return JSONResponse(result, status_code=200)


async def change_subscription_plan(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_MANAGE)
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, BillingPlanChangeRequest)

    def _do_change() -> dict:
        subscription = _require_subscription(state, fixture.tenant_id)
        try:
            catalog = load_plan_catalog()
            target = get_plan(body.target_plan_id, catalog)
            if subscription.plan.credit_policy is not None:
                if body.expected_plan_fingerprint != _plan_fingerprint(target):
                    raise ValueError("Revise as condições do plano alvo antes de confirmar.")
                rule = next((r for r in subscription.plan.plan_changes if r.target_plan_id == target.plan_id), None)
                if rule is not None and rule.kind is PlanChangeKind.DOWNGRADE:
                    from .commercial_limits import ACTIVE_CAMPAIGN_STATES
                    users = state.organizations.active_membership_count(fixture.tenant_id)
                    reserved = state.organizations.pending_invitation_count(fixture.tenant_id)
                    campaigns = sum(r.campaign.state in ACTIVE_CAMPAIGN_STATES
                                    for r in state.campaigns.list_for_tenant(fixture.tenant_id))
                    if (target.effective_max_users is None or target.entitlements is None
                            or target.entitlements.max_active_campaigns is None
                            or users + reserved > target.effective_max_users
                            or campaigns > target.entitlements.max_active_campaigns):
                        raise ValueError("Reduza usuários/convites e campanhas antes de confirmar o downgrade.")
            updated = request_plan_change(subscription, target, now=datetime.now(timezone.utc))
        except PlanCatalogError as exc:
            raise ApiError("BILLING_CATALOG_UNAVAILABLE", str(exc), status_code=503) from exc
        except ValueError as exc:
            raise ApiError("BILLING_PLAN_CHANGE_REJECTED", str(exc), status_code=409) from exc
        state.subscriptions[fixture.tenant_id] = updated
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="BILLING_PLAN_CHANGE_REQUESTED",
            target=body.target_plan_id,
            details={"kind": updated.pending_plan_change_kind.value},
        )
        return _serialize_subscription(updated, state=state)

    result, _ = state.idempotency.execute(
        fixture.tenant_id, f"http:billing_plan_change:{idem_key}", _do_change
    )
    return JSONResponse(result, status_code=200)


async def undo_billing_plan_change(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_MANAGE)
    key = require_idempotency_key(request)
    def _undo():
        subscription = _require_subscription(state, fixture.tenant_id)
        try:
            if subscription.pending_plan_effective_at is not None:
                schedule = subscription.paid_cycle_schedule
                index = period_index(schedule.anchor_at, subscription.pending_plan_effective_at)
                obligation = schedule.obligation_id(fixture.tenant_id, index)
                if (state.idempotency.get(fixture.tenant_id, obligation_key(obligation)) is not None
                        or schedule.paid_through_index >= index or any(
                        charge.billing_id == obligation for _key, charge in state.charges.items_for_tenant(fixture.tenant_id))):
                    raise ValueError("Obrigação já fechada; desistência exige conciliação financeira.")
            updated = undo_commercial_plan_change(subscription)
        except ValueError as exc:
            raise ApiError("BILLING_PLAN_CHANGE_REJECTED", str(exc), status_code=409) from exc
        state.subscriptions[fixture.tenant_id] = updated
        state.audit.append(tenant_id=fixture.tenant_id, actor=fixture.user_id,
                           action="BILLING_PLAN_CHANGE_WITHDRAWN", target=updated.plan.plan_id)
        return _serialize_subscription(updated, state=state)
    result, _ = state.idempotency.execute(fixture.tenant_id, 'http:billing-undo-plan:' + key, _undo)
    return JSONResponse(result)


async def cancel_billing_subscription(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_MANAGE)
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, BillingCancellationRequest) if await request.body() else BillingCancellationRequest()

    def _do_cancel() -> dict:
        subscription = _require_subscription(state, fixture.tenant_id)
        try:
            updated = cancel_subscription(subscription, now=datetime.now(timezone.utc), immediate=body.immediate)
        except ValueError as exc:
            raise ApiError("BILLING_CANCEL_REJECTED", str(exc), status_code=409) from exc
        state.subscriptions[fixture.tenant_id] = updated
        record_closed_lifecycle(state, updated)
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action=("BILLING_RENEWAL_CANCELED" if updated.cancel_at_period_end is not None
                    and updated.status is not SubscriptionStatus.CANCELED else "BILLING_SUBSCRIPTION_CANCELED"),
            target=updated.plan.plan_id,
            details={"cancel_at_period_end": updated.cancel_at_period_end.isoformat() if updated.cancel_at_period_end else None,
                     "immediate": body.immediate},
        )
        return _serialize_subscription(updated, state=state)

    result, _ = state.idempotency.execute(
        fixture.tenant_id, f"http:billing_cancel:{idem_key}", _do_cancel
    )
    return JSONResponse(result, status_code=200)


async def reactivate_billing_subscription(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_MANAGE)
    idem_key = require_idempotency_key(request)

    def _do_reactivate() -> dict:
        subscription = _require_subscription(state, fixture.tenant_id)
        try:
            if subscription.plan.credit_policy is not None and subscription.status in {SubscriptionStatus.CANCELED, SubscriptionStatus.EXPIRED}:
                if any((charge.gateway_status == "OVERDUE" or charge.commercial_lifecycle_id is not None)
                       and charge.status is not ChargeStatus.SETTLED
                       and not verified_void(state, fixture.tenant_id, charge.billing_id)
                       for _key, charge in state.charges.items_for_tenant(fixture.tenant_id)):
                    raise ValueError("Existe obrigação anterior aberta não conciliada; resolva ou comprove sua retirada antes de nova contratação.")
            schedule = subscription.paid_cycle_schedule
            if subscription.plan.credit_policy is not None and schedule is not None:
                pending_id = schedule.obligation_id(fixture.tenant_id, schedule.paid_through_index + 1)
                if (state.idempotency.get(fixture.tenant_id, 'billing-dispatch:' + pending_id) is not None
                        and not any(charge.billing_id == pending_id for _gid, charge in state.charges.items_for_tenant(fixture.tenant_id))):
                    raise ValueError("Emissão anterior incerta; concilie a mesma solicitação antes de nova contratação.")
            require_no_payment_review(state, fixture.tenant_id)
            require_final_usage_resolved(state, subscription, actor=fixture.user_id)
            updated = request_reactivation(subscription, now=datetime.now(timezone.utc), lifecycle_id=uuid4().hex)
        except ValueError as exc:
            raise ApiError("BILLING_REACTIVATION_REJECTED", str(exc), status_code=409) from exc
        state.subscriptions[fixture.tenant_id] = updated
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="BILLING_REACTIVATION_REQUESTED",
            target=updated.plan.plan_id,
        )
        return _serialize_subscription(updated, state=state)

    result, _ = state.idempotency.execute(
        fixture.tenant_id, f"http:billing_reactivate:{idem_key}", _do_reactivate
    )
    return JSONResponse(result, status_code=200)


async def get_subscription(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_VIEW)
    subscription = _require_subscription(state, fixture.tenant_id)
    return JSONResponse(_serialize_subscription(subscription, state=state))


async def get_billing_usage(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_VIEW)
    subscription = _require_subscription(state, fixture.tenant_id)
    return JSONResponse(usage_payload(state, subscription))


async def set_credit_consent(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_MANAGE)
    key = require_idempotency_key(request)
    body = await parse_body(request, BillingCreditConsentRequest)

    def _do_consent():
        subscription = _require_subscription(state, fixture.tenant_id)
        now = datetime.now(timezone.utc)
        snapshot = cycle_snapshot(subscription, at=now)
        if (state.credit_ledger is None or snapshot is None or snapshot.trial
                or not snapshot.starts_at <= now < snapshot.ends_at
                or not entitlement_access_is_active(subscription, now=now)
                or payment_access_is_blocked(state, subscription, at=now)):
            raise ApiError("BILLING_CONSENT_REJECTED", "Excedente exige ciclo pago vigente.", status_code=409)
        if (body.policy_version != snapshot.policy_version
                or body.extra_credit_price != snapshot.extra_credit_price
                or body.cycle_id != snapshot.cycle_id):
            raise ApiError("BILLING_TERMS_CHANGED", "Revise o ciclo, a versão e o preço antes de autorizar.", status_code=409)
        state.credit_ledger.decide(fixture.tenant_id, 'consent', cycle_id=snapshot.cycle_id,
                                  cap=body.cap, actor=fixture.user_id,
                                  reference='http:' + key, at=now)
        subscription = replace(subscription, extra_credit_consent=ExtraCreditConsent(
            tenant_id=fixture.tenant_id, reference='http:' + key, actor=fixture.user_id,
            at=now, cap=body.cap, policy_version=body.policy_version,
            extra_credit_price=body.extra_credit_price))
        state.subscriptions[fixture.tenant_id] = subscription
        state.audit.append(tenant_id=fixture.tenant_id, actor=fixture.user_id,
                           action="BILLING_EXTRA_CREDIT_CONSENT", target=snapshot.cycle_id,
                           details={"cap": str(body.cap), "version": body.policy_version,
                                    "price": str(body.extra_credit_price)})
        return usage_payload(state, subscription, at=now)

    result, _ = state.idempotency.execute(fixture.tenant_id, 'http:credit-consent:' + key, _do_consent)
    return JSONResponse(result)


async def list_billing_charges(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_VIEW)
    if hasattr(state.charges, "items_for_tenant"):
        rows = state.charges.items_for_tenant(fixture.tenant_id)
    else:
        rows = [(key, charge) for key, charge in state.charges.items()
                if charge.tenant_id == fixture.tenant_id]
    rows.sort(key=lambda row: (
        row[1].created_at or datetime.min.replace(tzinfo=timezone.utc), row[0]
    ), reverse=True)
    start = 0
    cursor = request.query_params.get("cursor")
    if cursor:
        ids = [key for key, _charge in rows]
        if cursor not in ids:
            raise ApiError("VALIDATION_FAILED", "Cursor inválido ou indisponível.")
        start = ids.index(cursor) + 1
    page = rows[start:start + 50]
    response = BillingChargeHistoryResponse(items=[BillingChargeHistoryItem(
        billing_id=charge.billing_id,
        gateway_charge_id=key,
        competence=charge.competence,
        currency=charge.currency,
        amount=str(charge.amount),
        plan_id=charge.plan_id,
        purpose=charge.purpose.value,
        created_at=charge.created_at,
        gateway_status=charge.gateway_status,
        gateway_provider=charge.gateway_provider,
        gateway_mode=charge.gateway_mode,
        status_observed_at=charge.status_observed_at,
        status_source=charge.status_source,
        gateway_observed_amount=(str(charge.gateway_observed_amount) if charge.gateway_observed_amount is not None else None),
        payment_reconciliation_state=charge.payment_reconciliation_state,
        gateway_chargeback_status=charge.gateway_chargeback_status,
        gateway_refund_amount=(str(charge.gateway_refund_amount) if charge.gateway_refund_amount is not None else None),
        gateway_refund_state=charge.gateway_refund_state,
        gateway_refund_observed_at=charge.gateway_refund_observed_at,
        withdrawal_state=withdrawal_state(state, charge),
        withdrawal_observed_at=withdrawal_observed_at(state, charge),
        withdrawal_fingerprint=withdrawal_quote(state, key, charge),
        reconciliation_available=(charge.commercial_lifecycle_id is not None
            and (charge.commercial_gateway_provider or charge.gateway_provider) == state.billing_gateway.provider
            and (charge.commercial_gateway_mode or charge.gateway_mode) == state.billing_gateway.mode.value
            and callable(getattr(state.billing_gateway, 'inspect_charge', None))),
        invoice_url=(safe_asaas_invoice_url(charge.invoice_url, charge.gateway_mode)
                     if charge.gateway_provider == "ASAAS" and withdrawal_state(state, charge) is None else None),
    ) for key, charge in page],
        next_cursor=page[-1][0] if start + 50 < len(rows) else None)
    return JSONResponse(response.model_dump(mode="json"))


def _review_checkout(state, charge, body):
    if body.expected_quote_fingerprint is not None and not body.accept_quote:
        raise ApiError("VALIDATION_FAILED", "Confirme o aceite dos valores revisados antes de emitir.")
    if (body.expected_quote_fingerprint is not None
            and body.expected_quote_fingerprint != checkout_quote(state, charge)['fingerprint']):
        raise ApiError("BILLING_QUOTE_CHANGED", "As condições da cobrança mudaram. Atualize e revise novamente.", status_code=409)
    return charge


async def get_billing_renewal(request: Request) -> JSONResponse:
    from .billing_renewal import renewal_quote
    fixture, state = _authorize_billing(request, Permission.BILLING_VIEW)
    with state.db.transaction() if state.db is not None else nullcontext():
        if state.db is not None:
            state.idempotency._table.lock_key(f"tenant:{fixture.tenant_id}")
        return JSONResponse(renewal_quote(state, fixture.tenant_id))


async def set_billing_renewal(request: Request) -> JSONResponse:
    from .billing_renewal import set_renewal_consent
    from .models import BillingRenewalRequest
    fixture, state = _authorize_billing(request, Permission.BILLING_MANAGE)
    key = require_idempotency_key(request)
    body = await parse_body(request, BillingRenewalRequest)
    return JSONResponse(set_renewal_consent(state, fixture, key, body.model_dump()))


async def get_billing_guarantee(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_VIEW)
    with state.db.transaction() if state.db is not None else nullcontext():
        if state.db is not None:
            state.idempotency._table.lock_key(f"tenant:{fixture.tenant_id}")
        _require_subscription(state, fixture.tenant_id)
        return JSONResponse(guarantee_quote(state, fixture.tenant_id, at=datetime.now(timezone.utc)))


async def request_billing_guarantee(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_MANAGE)
    key = require_idempotency_key(request)
    body = await parse_body(request, BillingClosureRequest)
    requested_at = datetime.now(timezone.utc)
    return JSONResponse(request_guarantee(state, fixture, key, body.model_dump(), at=requested_at))


async def get_billing_closure(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_VIEW)
    with state.db.transaction() if state.db is not None else nullcontext():
        if state.db is not None:
            state.idempotency._table.lock_key(f"tenant:{fixture.tenant_id}")
        sub = _require_subscription(state, fixture.tenant_id)
        return JSONResponse(closure_quote(state, sub))


async def close_billing_usage(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_MANAGE)
    key = require_idempotency_key(request)
    body = await parse_body(request, BillingClosureRequest)
    context = sha256(json.dumps([fixture.user_id, fixture.business_unit_id, body.model_dump()], sort_keys=True).encode()).hexdigest()
    def _claim_request():
        sub = _require_subscription(state, fixture.tenant_id)
        quote = closure_quote(state, sub)
        if not body.accept or body.fingerprint != quote['fingerprint']:
            raise ApiError("BILLING_QUOTE_CHANGED", "Revise e aceite o fechamento antes de confirmar.", status_code=409)
        if quote['state'] not in {'NO_CHARGE', 'ABSORBABLE', 'ABSORBED', 'INVOICE_REQUIRED', 'INVOICED', 'SETTLED', 'GUARANTEE_CLOSED'}:
            raise ApiError("BILLING_FINAL_USAGE_PENDING", "Fechamento ainda exige conciliação.", status_code=409)
        state.audit.append(tenant_id=fixture.tenant_id, actor=fixture.user_id,
                           action="BILLING_FINAL_USAGE_ACCEPTED", target=quote['lifecycle_id'],
                           details={'fingerprint': quote['fingerprint']})
        return {'context': context, 'sub': sub, 'quote': quote}
    accepted, _ = state.idempotency.execute(fixture.tenant_id, 'billing-closure-request:' + key, _claim_request)
    if accepted['context'] != context:
        raise ApiError("IDEMPOTENCY_CONFLICT", "A chave identifica outro fechamento/contexto.", status_code=409)
    sub = accepted['sub']; quote = accepted['quote']
    if quote['state'] in {'SETTLED', 'GUARANTEE_CLOSED'}:
        return JSONResponse(quote)
    if quote['state'] in {'NO_CHARGE', 'ABSORBABLE', 'ABSORBED'}:
        result, _ = state.idempotency.execute(fixture.tenant_id, 'http:billing_closure:' + key,
            lambda: close_without_invoice(state, sub, actor=fixture.user_id))
    else:
        def _prepare():
            fresh = closure_quote(state, sub)
            if fresh['fingerprint'] != body.fingerprint:
                raise ApiError("BILLING_QUOTE_CHANGED", "Fechamento mudou; atualize e revise novamente.", status_code=409)
            return final_charge(state, sub)
        def _persist(charge, gateway_result):
            _persist_billing_charge(state, fixture, charge, gateway_result)
            statement = {**quote, 'state': 'INVOICED', 'invoice': charge.billing_id}
            saved, _ = state.idempotency.execute(fixture.tenant_id, closure_result_key(quote['lifecycle_id']), lambda: statement)
            return saved
        result = execute_invoice(state, fixture, key, body.model_dump(), _prepare, dispatch_frozen_charge,
                                 _persist, operation='billing_final_usage')
    return JSONResponse(result)


async def get_billing_checkout(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_VIEW)
    with state.db.transaction() if state.db is not None else nullcontext():
        if state.db is not None:
            state.idempotency._table.lock_key(f"tenant:{fixture.tenant_id}")
        sub = _require_subscription(state, fixture.tenant_id)
        if sub.plan.credit_policy is None or sub.paid_cycle_schedule is None or state.credit_ledger is None:
            return JSONResponse(BillingCheckoutResponse(state="UNAVAILABLE").model_dump(mode="json"))
        if sub.status is SubscriptionStatus.CANCELED or sub.cancel_at_period_end is not None:
            return JSONResponse(BillingCheckoutResponse(state="CLOSED").model_dump(mode="json"))
        schedule = sub.paid_cycle_schedule
        index = schedule.paid_through_index + 1
        if schedule.anchor_at is not None:
            due = schedule.bounds(index)[0]
            if datetime.now(timezone.utc) < due:
                return JSONResponse(BillingCheckoutResponse(state="NOT_DUE", available_at=due).model_dump(mode="json"))
        charge = _prepare_billing_charge(state, fixture, BillingChargeCreate(competence="server-cycle"))
        registered = next((c for _key, c in state.charges.items_for_tenant(fixture.tenant_id)
                           if c.billing_id == charge.billing_id), None)
        dispatched = state.idempotency.get(fixture.tenant_id, 'billing-dispatch:' + charge.billing_id)
        status = "REGISTERED" if registered else "PENDING" if dispatched else "READY"
        invoice_url = (safe_asaas_invoice_url(registered.invoice_url, registered.gateway_mode)
                       if registered and registered.gateway_provider == "ASAAS" else None)
        return JSONResponse(BillingCheckoutResponse(state=status, quote=checkout_quote(state, charge),
                                                     invoice_url=invoice_url).model_dump(mode="json"))


def _prepare_billing_charge(state, fixture, body):
    require_no_payment_review(state, fixture.tenant_id)
    subscription = _require_subscription(state, fixture.tenant_id)
    try:
        billing_plan = None
        purpose = ChargePurpose.REGULAR
        if subscription.pending_plan is not None:
            if (
                subscription.pending_plan_change_billing_mode
                is not PlanChangeBillingMode.TARGET_PLAN_FULL_CYCLE
            ):
                raise ValueError("modo de cobranca da troca de plano nao suportado.")
            billing_plan = subscription.pending_plan
            purpose = ChargePurpose.PLAN_CHANGE
        elif subscription.reactivation_requested_at is not None:
            if (
                subscription.plan.reactivation_billing_mode
                is not ReactivationBillingMode.CURRENT_PLAN_FULL_CYCLE
            ):
                raise ValueError("modo de cobranca da reativacao nao suportado.")
            purpose = ChargePurpose.REACTIVATION

        commercial_schedule = subscription.paid_cycle_schedule
        if subscription.plan.credit_policy is not None:
            if commercial_schedule is None or state.credit_ledger is None:
                raise ValueError("Contrato comercial sem identidade/persistência de ciclo.")
            if body.extra_credits_used != 0:
                raise ValueError("Consumo comercial é calculado pelo servidor, nunca pelo cliente.")
            if subscription.cancel_at_period_end is not None:
                raise ValueError("Renovação cancelada; não emitir mensalidade posterior.")
            index = commercial_schedule.paid_through_index + 1
            now = datetime.now(timezone.utc)
            if commercial_schedule.anchor_at is not None:
                if period_index(commercial_schedule.anchor_at, now) < index:
                    raise ValueError("A renovação é emitida somente no aniversário.")
            frozen = state.idempotency.get(fixture.tenant_id, obligation_key(
                commercial_schedule.obligation_id(fixture.tenant_id, index)))
            if frozen is not None:
                return _review_checkout(state, frozen.result, body)
            closed_extra = Decimal("0.00")
            if index > 0:
                previous_id = commercial_schedule.obligation_id(subscription.tenant_id, index - 1)
                previous = state.credit_ledger.balance(subscription.tenant_id, previous_id)
                if previous.reserved_credits:
                    raise ValueError("Uso anterior pendente de reconciliação; não fechar estimativa como consumo.")
                closed_extra = previous.extra_consumed_amount
            competence = f"cycle:{index}"
        else:
            competence = body.competence

        charge = compute_cycle_charge(
            subscription,
            competence=competence,
            extra_credits_used=body.extra_credits_used,
            billing_plan=billing_plan,
            purpose=purpose,
        )
        if subscription.plan.credit_policy is not None:
            lines = [ChargeLineItem(f"Mensalidade antecipada — ciclo {index}", (billing_plan or subscription.plan).monthly_price)]
            if closed_extra:
                start, end = commercial_schedule.bounds(index - 1)
                lines.append(ChargeLineItem(
                    f"Excedente fechado — {start.isoformat()} / {end.isoformat()}", closed_extra))
            charge = replace(charge,
                billing_id=commercial_schedule.obligation_id(subscription.tenant_id, index),
                line_items=tuple(lines), commercial_cycle_index=index,
                commercial_lifecycle_id=commercial_schedule.lifecycle_id,
                commercial_plan=billing_plan or subscription.plan,
                commercial_gateway_provider=state.billing_gateway.provider,
                commercial_gateway_mode=state.billing_gateway.mode.value,
                commercial_due_at=(commercial_schedule.bounds(index)[0] if commercial_schedule.anchor_at is not None
                    else now.astimezone(COMMERCIAL_TIMEZONE).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)))
    except ValueError as exc:
        raise ApiError("VALIDATION_FAILED", str(exc)) from exc

    if subscription.plan.credit_policy is not None:
        existing_obligation = next((c for _key, c in state.charges.items_for_tenant(fixture.tenant_id)
                                    if c.billing_id == charge.billing_id), None)
        if existing_obligation is not None:
            charge = existing_obligation
    return _review_checkout(state, charge, body)



def _persist_billing_charge(state, fixture, charge, result):
    # Guarda a cobranca pelo id real do gateway -- e assim que o webhook do Asaas
    # (que so conhece o payment_id, nunca o billing_id interno) encontra de volta a
    # cobranca a que um evento de pagamento pertence.
    existing = state.charges.get(result.gateway_charge_id)
    if existing is not None:
        if existing.tenant_id != charge.tenant_id or existing.billing_id != charge.billing_id:
            raise ApiError("INVALID_STATE", "Identificador de cobrança inconsistente.")
        # Another HTTP key can replay the same durable gateway result. Preserve
        # webhook observations rather than reverting them to the creation snapshot.
    else:
        observed_at = datetime.now(timezone.utc)
        state.charges[result.gateway_charge_id] = replace(
            charge, created_at=observed_at, status_observed_at=observed_at,
            gateway_status=result.status.value, gateway_provider=result.provider,
            gateway_mode=result.mode.value, status_source="CREATE",
            invoice_url=result.invoice_url,
        )
    state.audit.append(
        tenant_id=fixture.tenant_id,
        actor=fixture.user_id,
        actor_kind=getattr(fixture, "actor_kind", "USER"),
        action="BILLING_CHARGE_CREATE",
        target=result.gateway_charge_id,
    )
    return BillingChargeResponse(
        billing_id=charge.billing_id,
        tenant_id=charge.tenant_id,
        competence=charge.competence,
        currency=charge.currency,
        amount=charge.amount,
        gateway_charge_id=result.gateway_charge_id,
        gateway_status=result.status.value,
    ).model_dump(mode="json")


async def create_charge(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_MANAGE)
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, BillingChargeCreate)
    def _prepare_charge():
        return _prepare_billing_charge(state, fixture, body)

    def _persist_charge(charge, result):
        return _persist_billing_charge(state, fixture, charge, result)

    subscription = _require_subscription(state, fixture.tenant_id)
    if subscription.plan.credit_policy is not None:
        result = execute_invoice(state, fixture, idem_key, body.model_dump(mode="json"),
                                 _prepare_charge, dispatch_frozen_charge, _persist_charge)
    else:
        def _do_charge():
            charge = _prepare_charge()
            try:
                result = charge_subscription(charge, state.billing_gateway)
            except PaymentGatewayError as exc:
                raise ApiError(exc.code, exc.message, details=dict(exc.details)) from exc
            return _persist_charge(charge, result)
        result, _replay = state.idempotency.execute(
            fixture.tenant_id, f"http:billing_charge_create:{idem_key}", _do_charge)
    return JSONResponse(result, status_code=202)


async def withdraw_billing_renewal(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_MANAGE)
    key = require_idempotency_key(request)
    body = await parse_body(request, BillingWithdrawalRequest)
    return JSONResponse(withdraw_unpaid_renewal(state, fixture,
        request.path_params['gatewayChargeId'], key, body.model_dump()))


async def reconcile_billing_payment(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_MANAGE)
    key = require_idempotency_key(request)
    if await request.body():
        await parse_body(request, ApiModel)  # No client amount/status/paid flag is accepted.
    gateway_id = request.path_params['gatewayChargeId']
    def owned_charge():
        charge = state.charges.get(gateway_id)
        if charge is None or charge.tenant_id != fixture.tenant_id:
            raise ApiError("NOT_FOUND", "Cobrança indisponível.", status_code=404)
        if charge.commercial_lifecycle_id is None:
            raise ApiError("CAPABILITY_UNSUPPORTED", "Conferência estruturada indisponível neste contrato.", status_code=422)
        return charge
    charge = owned_charge()
    context = sha256(json.dumps([fixture.user_id, fixture.business_unit_id, gateway_id]).encode()).hexdigest()
    operation = 'http:billing_payment_reconcile:' + key
    existing = state.idempotency.get(fixture.tenant_id, operation)
    if existing is not None:
        if existing.result['context'] != context:
            raise ApiError("IDEMPOTENCY_CONFLICT", "A chave identifica outra consulta ou contexto.", status_code=409)
        return JSONResponse(existing.result['response'])
    if ((charge.commercial_gateway_provider or charge.gateway_provider) != state.billing_gateway.provider
            or (charge.commercial_gateway_mode or charge.gateway_mode) != state.billing_gateway.mode.value):
        raise ApiError("BILLING_RECONCILIATION_REQUIRED", "Consulte no provedor/ambiente original da obrigação.", status_code=409)
    inspect = getattr(state.billing_gateway, 'inspect_charge', None)
    if inspect is None:
        raise ApiError("BILLING_RECONCILIATION_REQUIRED", "Consulta externa indisponível.", status_code=503)
    lookup_started_at = datetime.now(timezone.utc)
    try:
        inspected = inspect(gateway_id, charge_command(charge))  # Read-only HTTP OUTSIDE DB transaction.
    except Exception as exc:
        raise ApiError("BILLING_RECONCILIATION_REQUIRED", "Não foi possível confirmar a consulta ao provedor.", status_code=503) from exc
    if (inspected.gateway_charge_id != gateway_id or inspected.provider != state.billing_gateway.provider
            or inspected.mode != state.billing_gateway.mode):
        raise ApiError("BILLING_RECONCILIATION_REQUIRED", "Resposta externa incompatível com a obrigação.", status_code=503)
    raw_status = inspected.source_status or inspected.status.value
    if not isinstance(raw_status, str):
        raise ApiError("BILLING_RECONCILIATION_REQUIRED", "Status externo inválido.", status_code=503)
    event_type = "PAYMENT_REFUND_RECONCILIATION" if ("REFUND" in raw_status or "CHARGEBACK" in raw_status) else "PAYMENT_RECONCILIATION"
    event = AsaasPaymentEvent('reconcile:' + sha256((fixture.tenant_id + ':' + key).encode()).hexdigest(),
        event_type, gateway_id, raw_status, inspected.observed_amount,
        inspected.refund_observations, inspected.refunds_present, inspected.chargeback_status)
    observed_at = datetime.now(timezone.utc)
    def _commit():
        fresh = owned_charge()
        observed_event = event
        if inspected.status is not GatewayChargeStatus.CONFIRMED and fresh.status is not ChargeStatus.SETTLED and event_type == "PAYMENT_RECONCILIATION":
            observed_event = replace(event, event_type="PAYMENT_UPDATED")
        response = _apply_verified_payment_event(state, fresh, observed_event, observed_at=observed_at,
            source="RECONCILIATION", mapped_status=inspected.status, snapshot_started_at=lookup_started_at)
        state.audit.append(tenant_id=fixture.tenant_id, actor=fixture.user_id,
                           action="BILLING_PAYMENT_LOOKUP", target=fresh.billing_id)
        payload = json.loads(response.body)
        payload.update(gateway_charge_id=gateway_id, observed_amount=(str(inspected.observed_amount)
            if inspected.observed_amount is not None else None), observed_at=observed_at.isoformat())
        return {'context': context, 'response': payload}
    recorded, _ = state.idempotency.execute(fixture.tenant_id, operation, _commit)
    if recorded['context'] != context:
        raise ApiError("IDEMPOTENCY_CONFLICT", "A chave identifica outra consulta ou contexto.", status_code=409)
    return JSONResponse(recorded['response'])


def _apply_verified_payment_event(state, charge, event, *, observed_at, source="WEBHOOK", mapped_status=None, snapshot_started_at=None):
    """Caller authenticates the source and holds the existing F3 tenant transaction.

    Both provider webhooks and explicit read-only provider reconciliation use this
    same settlement authority. Client-submitted amounts never enter this function.
    """
    if source == "RECONCILIATION" and charge.status_observed_at is not None and charge.status_observed_at > (snapshot_started_at or observed_at):
        return JSONResponse({"accepted": True, "processed": False, "reconciled": False,
                             "reconciliation_state": "STALE_OBSERVATION", "billing_id": charge.billing_id})
    if event.event_type in {
        "PAYMENT_CREDIT_CARD_CAPTURE_REFUSED",
        "PAYMENT_REPROVED_BY_RISK_ANALYSIS",
    } and not has_reversal_signal(event):
        state.audit.append(
            tenant_id=charge.tenant_id,
            actor="asaas",
            actor_kind="EXTERNAL_PROVIDER",
            action="BILLING_PAYMENT_ATTEMPT_FAILED",
            target=charge.billing_id,
            details={
                "event_type": event.event_type,
                "payment_status": event.asaas_status,
            },
        )
        return JSONResponse(
            {
                "accepted": True,
                "processed": True,
                "billing_id": charge.billing_id,
                "event": event.event_type,
            }
        )

    status = mapped_status if mapped_status is not None else map_asaas_status(event.asaas_status)
    if (source == "WEBHOOK" and charge.status is ChargeStatus.SETTLED
            and status in {GatewayChargeStatus.OVERDUE, GatewayChargeStatus.PENDING} and not has_reversal_signal(event)):
        state.audit.append(tenant_id=charge.tenant_id, actor="asaas", actor_kind="EXTERNAL_PROVIDER",
                           action="BILLING_STALE_OVERDUE_IGNORED", target=charge.billing_id)
        return JSONResponse({"accepted": True, "processed": False, "status": status.value})
    void_pending = state.idempotency.get(charge.tenant_id, void_intent_key(charge.billing_id)) is not None
    if void_pending and event.event_type == "PAYMENT_RESTORED":
        state.charges[event.payment_id] = replace(charge, gateway_status=status.value,
            payment_reconciliation_state="CANCELLATION_CONFLICT", status_source=source, status_observed_at=observed_at)
        state.audit.append(tenant_id=charge.tenant_id, actor="asaas", actor_kind="EXTERNAL_PROVIDER",
            action="BILLING_WITHDRAWN_INVOICE_RESTORED", target=charge.billing_id)
        return JSONResponse({"accepted": True, "processed": True, "reconciled": False,
                             "reconciliation_state": "CANCELLATION_CONFLICT"})
    is_reversal = has_reversal_signal(event)
    if charge.commercial_lifecycle_id is not None and (
            status is GatewayChargeStatus.CONFIRMED or event.event_type == "PAYMENT_UPDATED" or is_reversal
            or (source == "RECONCILIATION" and charge.status is ChargeStatus.SETTLED)):
        decision = observe_payment(state, charge, event, at=observed_at, gateway_status=status.value, source=source)
        if decision != "MATCHED" and not (decision == "TERMS_OBSERVED" and status is not GatewayChargeStatus.CONFIRMED):
            return JSONResponse({"accepted": True, "processed": True, "billing_id": charge.billing_id,
                                 "reconciled": decision == "ALREADY_SETTLED", "reconciliation_state": decision})
        charge = state.charges[event.payment_id]
    # Receipt observation only: never a fresh provider poll or a synthesized ledger.
    state.charges[event.payment_id] = replace(
        charge, gateway_status=status.value, status_observed_at=observed_at,
        status_source=source,
    )

    if status is GatewayChargeStatus.OVERDUE and charge.purpose is ChargePurpose.FINAL_USAGE:
        return JSONResponse({"accepted": True, "processed": True, "status": status.value})
    if status is GatewayChargeStatus.OVERDUE:
        subscription = state.subscriptions.get(charge.tenant_id)
        if subscription is None:
            return JSONResponse(
                {"accepted": True, "processed": False, "status": status.value}
            )

        if (charge.status is ChargeStatus.SETTLED or (subscription.paid_cycle_schedule is not None
                and any(identity == charge.billing_id for identity, _index
                        in subscription.paid_cycle_schedule.settled_obligations))):
            state.audit.append(tenant_id=charge.tenant_id, actor="asaas",
                actor_kind="EXTERNAL_PROVIDER", action="BILLING_STALE_OVERDUE_IGNORED",
                target=charge.billing_id)
            return JSONResponse({"accepted": True, "processed": False, "status": status.value})

        if (subscription.plan.credit_policy is not None and subscription.paid_cycle_schedule is not None
                and charge.commercial_lifecycle_id != subscription.paid_cycle_schedule.lifecycle_id):
            return JSONResponse({"accepted": True, "processed": False, "status": status.value})
        try:
            past_due = mark_past_due(
                subscription,
                overdue_at=observed_at,
                billed_plan_id=(subscription.plan.plan_id if subscription.plan.credit_policy else charge.plan_id),
                billed_purpose=(ChargePurpose.REGULAR if subscription.plan.credit_policy else charge.purpose),
            )
        except ValueError as exc:
            state.audit.append(
                tenant_id=charge.tenant_id,
                actor="asaas",
                actor_kind="EXTERNAL_PROVIDER",
                action="BILLING_SUBSCRIPTION_PAST_DUE_SKIPPED",
                target=subscription.plan.plan_id,
                details={
                    "billing_id": charge.billing_id,
                    "billed_plan_id": charge.plan_id,
                    "charge_purpose": charge.purpose.value,
                    "reason": str(exc),
                },
            )
            return JSONResponse(
                {"accepted": True, "processed": False, "status": status.value}
            )

        state.subscriptions[charge.tenant_id] = past_due
        if past_due != subscription:
            state.audit.append(
                tenant_id=charge.tenant_id,
                actor="asaas",
                actor_kind="EXTERNAL_PROVIDER",
                action="BILLING_SUBSCRIPTION_PAST_DUE",
                target=past_due.plan.plan_id,
                details={
                    "billing_id": charge.billing_id,
                    "grace_period_ends_at": (
                        past_due.grace_period_ends_at.isoformat()
                        if past_due.grace_period_ends_at is not None
                        else None
                    ),
                },
            )
        return JSONResponse(
            {
                "accepted": True,
                "processed": True,
                "billing_id": charge.billing_id,
                "status": status.value,
            }
        )

    fact = try_settle_from_status(charge, status, settled_at=observed_at)
    if fact is None:
        return JSONResponse({"accepted": True, "processed": False, "status": status.value})

    record_settled_fact(state, charge, event, fact, source=source)
    handoff = build_campaia_fiscal_handoff(fact)
    state.charges[event.payment_id] = replace(state.charges[event.payment_id], status=ChargeStatus.SETTLED)

    subscription = state.subscriptions.get(charge.tenant_id)
    if void_pending:
        state.charges[event.payment_id] = replace(state.charges[event.payment_id], payment_reconciliation_state="CANCELLATION_CONFLICT")
    if subscription is not None and charge.purpose is not ChargePurpose.FINAL_USAGE and not void_pending:
        was_past_due = subscription.status is SubscriptionStatus.PAST_DUE
        try:
            schedule = subscription.paid_cycle_schedule
            if subscription.plan.credit_policy is not None:
                if (schedule is None or charge.commercial_lifecycle_id != schedule.lifecycle_id
                        or charge.commercial_cycle_index is None):
                    raise ValueError("Pagamento sem vínculo ao ciclo/lifecycle comercial vigente.")
                schedule = schedule.confirm_payment(subscription.tenant_id, charge.billing_id,
                                                    charge.commercial_cycle_index, fact.settled_at)
            if subscription.plan.credit_policy is not None:
                billed_plan = charge.commercial_plan or subscription.plan
                activated = activate_commercial_payment(subscription, schedule=schedule,
                    billed_plan=billed_plan, billed_index=charge.commercial_cycle_index,
                    billed_purpose=charge.purpose, billing_id=charge.billing_id, settled_at=fact.settled_at)
            else:
                activated = activate_from_settled_payment(subscription, settled_at=fact.settled_at,
                    billed_plan_id=charge.plan_id, billed_purpose=charge.purpose)
        except ValueError as exc:
            # A liquidacao financeira do gateway e um fato independente do estado comercial
            # atual. Uma cobranca antiga pode chegar depois de cancelamento ou depois de uma
            # troca de plano ter sido solicitada. Nunca reative/libere entitlement por isso,
            # mas tambem nao responda 409 ao Asaas: isso so provocaria retries de um pagamento
            # que ja aconteceu. Registre a divergencia para reconciliacao humana/operacional.
            state.audit.append(
                tenant_id=charge.tenant_id,
                actor="asaas",
                actor_kind="EXTERNAL_PROVIDER",
                action="BILLING_SUBSCRIPTION_ACTIVATION_SKIPPED",
                target=subscription.plan.plan_id,
                details={
                    "billing_id": charge.billing_id,
                    "billed_plan_id": charge.plan_id,
                    "charge_purpose": charge.purpose.value,
                    "reason": str(exc),
                },
            )
        else:
            if subscription.plan.credit_policy is not None:
                activated = replace(activated, paid_cycle_schedule=schedule,
                                    activated_at=schedule.anchor_at)
                grant_paid_cycle(state, activated, index=charge.commercial_cycle_index,
                                 plan=billed_plan, at=fact.settled_at)
            state.subscriptions[charge.tenant_id] = activated
            state.audit.append(
                tenant_id=charge.tenant_id,
                actor="asaas",
                actor_kind="EXTERNAL_PROVIDER",
                action=(
                    "BILLING_SUBSCRIPTION_RECOVERED"
                    if was_past_due
                    else "BILLING_SUBSCRIPTION_ACTIVATED"
                ),
                target=activated.plan.plan_id,
                details={"billing_id": charge.billing_id},
            )

    state.audit.append(
        tenant_id=charge.tenant_id,
        actor="asaas",
        actor_kind="EXTERNAL_PROVIDER",
        action="BILLING_CHARGE_SETTLED",
        target=charge.billing_id,
        details={"fiscal_handoff_idempotency_key": handoff.idempotency_key},
    )
    result = {"accepted": True, "processed": True, "billing_id": charge.billing_id}
    if charge.commercial_lifecycle_id is not None:
        result["reconciled"] = not void_pending
        if void_pending:
            result["reconciliation_state"] = "CANCELLATION_CONFLICT"
    return JSONResponse(result)


async def asaas_webhook(request: Request) -> JSONResponse:
    """Recebe a notificacao de pagamento do Asaas. Sem autenticacao de usuario -- a
    autenticidade vem do token estatico verificado por `AsaasWebhookReceiver`, nunca de um
    Bearer token de sessao (o Asaas nao tem um).

    Duplicata processada retorna 200. Cobrança autenticada ainda não persistida retorna
    503 sem marcar dedupe, permitindo retry após o commit da emissão. Token inválido vira 401.

    Item 1.2 do cronograma mestre (24/09/2026): unico endpoint sem autenticacao de usuario
    deste app, entao o unico alvo publico de flood de aplicacao -- rate limit por IP de
    origem, antes de qualquer outra verificacao (nem token invalido deve custar processamento
    ilimitado). 429 para excedente, sem detalhe de quanto falta (nao ajuda um atacante a
    calibrar, e o Asaas reenvia notificacoes legitimas de qualquer forma).
    """
    state = get_state(request)
    client_ip = request.client.host if request.client else ""
    if not state.asaas_webhook_rate_limiter.allow(client_ip, now=datetime.now(timezone.utc)):
        return JSONResponse({"accepted": False, "reason": "RATE_LIMITED"}, status_code=429)

    received_token = request.headers.get("asaas-access-token")

    try:
        payload = await request.json()
    except ValueError as exc:
        raise ApiError("VALIDATION_FAILED", f"Corpo do webhook nao e JSON valido: {exc}") from exc

    def _process_event():
        authenticated = state.asaas_webhook.authenticate(received_token)
        if not authenticated:
            from campaia_core.webhooks import RejectionReason
            status_code = 401 if authenticated.reason is RejectionReason.SIGNATURE_INVALID else 200
            return JSONResponse({"accepted": False, "reason": authenticated.reason}, status_code=status_code)
        try:
            event = parse_asaas_payment_event(payload)
        except ValueError:
            return JSONResponse({"accepted": True, "processed": False})
        charge = state.charges.get(event.payment_id)
        if charge is None:
            # A valid callback can beat the charge-creation transaction commit.
            # Do not acknowledge or mark seen before the durable obligation exists.
            raise ApiError("BILLING_CHARGE_NOT_READY", "Cobrança ainda não disponível para reconciliação.",
                           status_code=503)
        if state.db is not None:
            # Match the existing HTTP idempotency tenant lock before any mutations.
            state.idempotency._table.lock_key(f"tenant:{charge.tenant_id}")
            charge = state.charges.get(event.payment_id)
        verdict = state.asaas_webhook.receive(received_token=received_token, event_id=event.event_id)
        if not verdict:
            return JSONResponse({"accepted": False, "reason": verdict.reason})

        return _apply_verified_payment_event(state, charge, event,
            observed_at=datetime.now(timezone.utc))

    if state.db is not None:
        with state.db.transaction():
            return _process_event()
    return _process_event()
