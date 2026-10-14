"""Superficie HTTP do motor de cobranca propria do CampaIA (B11 / ADR-0020).

Deliberadamente minima: uma assinatura ativa por tenant, uma cobranca por competencia, e o
webhook que recebe a confirmacao do Asaas. Nao expoe (ainda) historico de faturas, catalogo
de planos navegavel nem régua de cobranca -- blocos maiores, com decisoes de produto proprias,
fora do escopo desta integracao pontual (ver docs/18_ADR_0020_MODELO_COMERCIAL_E_GATEWAY_DE_PAGAMENTO.md).

O webhook (`POST /webhooks/asaas`) e o UNICO endpoint deste arquivo sem autenticacao de
usuario: quem chama e o Asaas, nao o app. A autenticidade vem da verificacao de token do
proprio `AsaasWebhookReceiver` (`asaas-access-token`), nunca de um Bearer token de usuario.
"""

from __future__ import annotations

from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

from campaia_core.asaas_gateway import map_asaas_status
from campaia_core.asaas_webhook import parse_asaas_payment_event
from campaia_core.billing_settlement import charge_subscription, try_settle_from_status
from campaia_core.fiscal_handoff import build_campaia_fiscal_handoff
from campaia_core.payment_gateway import GatewayChargeStatus, PaymentGatewayError
from campaia_core.permissions import Permission, Resource, authorize
from campaia_core.plan_catalog import PlanCatalogError, get_plan, load_plan_catalog
from campaia_core.subscription import (
    ChargePurpose,
    PlanChangeBillingMode,
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
    BillingChargeCreate,
    BillingChargeResponse,
    BillingEntitlementsResponse,
    BillingPlanChangeRequest,
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


def _serialize_subscription(sub: Subscription) -> dict:
    current = refresh_trial_status(sub)
    entitlements = current.plan.entitlements
    entitlement_payload = None
    if entitlements is not None:
        entitlement_payload = BillingEntitlementsResponse(
            max_users=current.plan.effective_max_users,
            max_active_campaigns=entitlements.max_active_campaigns,
            channels=list(entitlements.channels),
            ai_capabilities=list(entitlements.ai_capabilities),
            resources=list(entitlements.resources),
        )

    return BillingSubscriptionResponse(
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
        entitlement_access_active=entitlement_access_is_active(current),
        entitlements=entitlement_payload,
    ).model_dump(mode="json")


def _require_subscription(state: AppState, tenant_id: str) -> Subscription:
    subscription = state.subscriptions.get(tenant_id)
    if subscription is None:
        raise ApiError(
            "NOT_FOUND",
            "Nenhuma assinatura configurada para este tenant. Configure uma via "
            "PUT /billing/subscription antes de gerar uma cobranca.",
        )

    refreshed = refresh_trial_status(subscription, now=datetime.now(timezone.utc))
    if refreshed != subscription:
        state.subscriptions[tenant_id] = refreshed
        state.audit.append(
            tenant_id=tenant_id,
            actor="system",
            actor_kind="SYSTEM",
            action="BILLING_TRIAL_EXPIRED",
            target=refreshed.plan.plan_id,
        )
    return refreshed


async def put_subscription(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_MANAGE)
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, BillingSubscriptionUpsert)

    def _do_upsert() -> dict:
        try:
            catalog = load_plan_catalog()
            plan = get_plan(body.plan_id, catalog)
        except PlanCatalogError as exc:
            raise ApiError(
                "BILLING_CATALOG_UNAVAILABLE", str(exc), status_code=503
            ) from exc

        existing = state.subscriptions.get(fixture.tenant_id)
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
                )
            else:
                subscription = Subscription(
                    tenant_id=existing.tenant_id,
                    customer_ref=existing.customer_ref,
                    customer_document=body.customer_document,
                    plan=plan,
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
                )

            if body.start_trial:
                subscription = start_trial(
                    subscription,
                    now=datetime.now(timezone.utc),
                )
        except ValueError as exc:
            raise ApiError("VALIDATION_FAILED", str(exc)) from exc

        state.subscriptions[fixture.tenant_id] = subscription
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="BILLING_SUBSCRIPTION_UPSERT",
            target=body.plan_id,
            details={
                "status": subscription.status.value,
                "trial_requested": body.start_trial,
            },
        )
        return _serialize_subscription(subscription)

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
            updated = request_plan_change(subscription, target)
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
        return _serialize_subscription(updated)

    result, _ = state.idempotency.execute(
        fixture.tenant_id, f"http:billing_plan_change:{idem_key}", _do_change
    )
    return JSONResponse(result, status_code=200)


async def cancel_billing_subscription(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_MANAGE)
    idem_key = require_idempotency_key(request)

    def _do_cancel() -> dict:
        subscription = _require_subscription(state, fixture.tenant_id)
        try:
            updated = cancel_subscription(subscription, now=datetime.now(timezone.utc))
        except ValueError as exc:
            raise ApiError("BILLING_CANCEL_REJECTED", str(exc), status_code=409) from exc
        state.subscriptions[fixture.tenant_id] = updated
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="BILLING_SUBSCRIPTION_CANCELED",
            target=updated.plan.plan_id,
        )
        return _serialize_subscription(updated)

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
            updated = request_reactivation(subscription, now=datetime.now(timezone.utc))
        except ValueError as exc:
            raise ApiError("BILLING_REACTIVATION_REJECTED", str(exc), status_code=409) from exc
        state.subscriptions[fixture.tenant_id] = updated
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="BILLING_REACTIVATION_REQUESTED",
            target=updated.plan.plan_id,
        )
        return _serialize_subscription(updated)

    result, _ = state.idempotency.execute(
        fixture.tenant_id, f"http:billing_reactivate:{idem_key}", _do_reactivate
    )
    return JSONResponse(result, status_code=200)


async def get_subscription(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_VIEW)
    subscription = _require_subscription(state, fixture.tenant_id)
    return JSONResponse(_serialize_subscription(subscription))


async def create_charge(request: Request) -> JSONResponse:
    fixture, state = _authorize_billing(request, Permission.BILLING_MANAGE)
    idem_key = require_idempotency_key(request)
    body = await parse_body(request, BillingChargeCreate)
    subscription = _require_subscription(state, fixture.tenant_id)

    def _do_charge() -> dict:
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

            charge = compute_cycle_charge(
                subscription,
                competence=body.competence,
                extra_credits_used=body.extra_credits_used,
                billing_plan=billing_plan,
                purpose=purpose,
            )
        except ValueError as exc:
            raise ApiError("VALIDATION_FAILED", str(exc)) from exc

        try:
            result = charge_subscription(charge, state.billing_gateway)
        except PaymentGatewayError as exc:
            raise ApiError(exc.code, exc.message, details=dict(exc.details)) from exc

        # Guarda a cobranca pelo id real do gateway -- e assim que o webhook do Asaas
        # (que so conhece o payment_id, nunca o billing_id interno) encontra de volta a
        # cobranca a que um evento de pagamento pertence.
        state.charges[result.gateway_charge_id] = charge
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
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

    result, _replay = state.idempotency.execute(
        fixture.tenant_id, f"http:billing_charge_create:{idem_key}", _do_charge
    )
    return JSONResponse(result, status_code=202)


async def asaas_webhook(request: Request) -> JSONResponse:
    """Recebe a notificacao de pagamento do Asaas. Sem autenticacao de usuario -- a
    autenticidade vem do token estatico verificado por `AsaasWebhookReceiver`, nunca de um
    Bearer token de sessao (o Asaas nao tem um).

    Sempre responde 200 para um token valido, mesmo em duplicata ou payment_id desconhecido
    -- o Asaas reenvia em qualquer resposta que nao seja 2xx, e "ja processado"/"cobranca
    desconhecida" nao sao falhas que justifiquem esse reenvio. So token invalido vira 401.

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

    event_id = payload.get("id", "") if isinstance(payload, dict) else ""
    verdict = state.asaas_webhook.receive(received_token=received_token, event_id=event_id)
    if not verdict:
        from campaia_core.webhooks import RejectionReason

        status_code = 401 if verdict.reason is RejectionReason.SIGNATURE_INVALID else 200
        return JSONResponse({"accepted": False, "reason": verdict.reason}, status_code=status_code)

    try:
        event = parse_asaas_payment_event(payload)
    except ValueError:
        # Token valido mas corpo malformado -- aceitar o recebimento (200, nao repetir).
        # Nao ha tenant real identificavel ainda neste ponto, entao nao ha em nome de quem
        # registrar auditoria; jamais processar um evento parcialmente interpretado.
        return JSONResponse({"accepted": True, "processed": False})

    charge = state.charges.get(event.payment_id)
    if charge is None:
        # payment_id que este processo nao originou (ou cobranca de uma execucao anterior,
        # em memoria, ja perdida) -- aceitar o recebimento sem erro, nao ha o que liquidar.
        return JSONResponse({"accepted": True, "processed": False})

    observed_at = datetime.now(timezone.utc)
    status = map_asaas_status(event.asaas_status)

    if status is GatewayChargeStatus.OVERDUE:
        subscription = state.subscriptions.get(charge.tenant_id)
        if subscription is None:
            return JSONResponse(
                {"accepted": True, "processed": False, "status": status.value}
            )

        try:
            past_due = mark_past_due(
                subscription,
                overdue_at=observed_at,
                billed_plan_id=charge.plan_id,
                billed_purpose=charge.purpose,
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

    handoff = build_campaia_fiscal_handoff(fact)

    subscription = state.subscriptions.get(charge.tenant_id)
    if subscription is not None:
        was_past_due = subscription.status is SubscriptionStatus.PAST_DUE
        try:
            activated = activate_from_settled_payment(
                subscription,
                settled_at=fact.settled_at,
                billed_plan_id=charge.plan_id,
                billed_purpose=charge.purpose,
            )
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
    return JSONResponse({"accepted": True, "processed": True, "billing_id": charge.billing_id})
