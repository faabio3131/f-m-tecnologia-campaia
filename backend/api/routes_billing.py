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
from campaia_core.payment_gateway import PaymentGatewayError
from campaia_core.permissions import Permission, Resource, authorize
from campaia_core.plan_catalog import PlanCatalogError, get_plan, load_plan_catalog
from campaia_core.subscription import Subscription, compute_cycle_charge

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
    BillingSubscriptionResponse,
    BillingSubscriptionUpsert,
)
from .state import AppState


def _authorize_billing(request: Request, permission: Permission):
    fixture = require_auth(request)
    note_step_up_header(request, fixture)
    state = get_state(request)
    principal = build_domain_principal(state, fixture)
    resource = Resource(tenant_id=fixture.tenant_id)
    decision = authorize(principal, permission, resource, now=datetime.now(timezone.utc))
    if not decision.allowed:
        raise ApiError(decision.code.value, decision.reason)
    return fixture, state


def _serialize_subscription(sub: Subscription) -> dict:
    return BillingSubscriptionResponse(
        tenant_id=sub.tenant_id,
        customer_ref=sub.customer_ref,
        customer_document=sub.customer_document,
        plan_id=sub.plan.plan_id,
        plan_name=sub.plan.name,
        status=sub.status.value,
    ).model_dump(mode="json")


def _require_subscription(state: AppState, tenant_id: str) -> Subscription:
    subscription = state.subscriptions.get(tenant_id)
    if subscription is None:
        raise ApiError(
            "NOT_FOUND",
            "Nenhuma assinatura configurada para este tenant. Configure uma via "
            "PUT /billing/subscription antes de gerar uma cobranca.",
        )
    return subscription


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

        try:
            subscription = Subscription(
                tenant_id=fixture.tenant_id,
                customer_ref=fixture.tenant_id,
                customer_document=body.customer_document,
                plan=plan,
            )
        except ValueError as exc:
            raise ApiError("VALIDATION_FAILED", str(exc)) from exc

        state.subscriptions[fixture.tenant_id] = subscription
        state.audit.append(
            tenant_id=fixture.tenant_id,
            actor=fixture.user_id,
            action="BILLING_SUBSCRIPTION_UPSERT",
            target=body.plan_id,
        )
        return _serialize_subscription(subscription)

    result, _replay = state.idempotency.execute(
        fixture.tenant_id, f"http:billing_subscription_upsert:{idem_key}", _do_upsert
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
            charge = compute_cycle_charge(
                subscription,
                competence=body.competence,
                extra_credits_used=body.extra_credits_used,
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
    """
    state = get_state(request)
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

    status = map_asaas_status(event.asaas_status)
    fact = try_settle_from_status(charge, status, settled_at=datetime.now(timezone.utc))
    if fact is None:
        return JSONResponse({"accepted": True, "processed": False, "status": status.value})

    handoff = build_campaia_fiscal_handoff(fact)
    state.audit.append(
        tenant_id=charge.tenant_id,
        actor="asaas",
        actor_kind="EXTERNAL_PROVIDER",
        action="BILLING_CHARGE_SETTLED",
        target=charge.billing_id,
        details={"fiscal_handoff_idempotency_key": handoff.idempotency_key},
    )
    return JSONResponse({"accepted": True, "processed": True, "billing_id": charge.billing_id})
