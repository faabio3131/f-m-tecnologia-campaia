"""One invoice authority for manual checkout and consented paid anniversaries."""
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from decimal import Decimal
import json
from types import SimpleNamespace

from campaia_core.billing_renewal import RenewalInvoiceConsent
from campaia_core.subscription import refresh_trial_status, SubscriptionStatus
from campaia_core.billing_settlement import dispatch_frozen_charge
from .billing_receipts import has_payment_review
from .billing_dispatch import execute_invoice
from .errors import ApiError
from .models import BillingChargeCreate


def renewal_quote(state, tenant, *, at=None):
    from .routes_billing import _plan_fingerprint
    now = at or datetime.now(timezone.utc)
    sub = state.subscriptions.get(tenant)
    if sub is None:
        raise ApiError('NOT_FOUND', 'Assinatura indisponível.', status_code=404)
    sub = refresh_trial_status(sub, now=now)
    schedule = sub.paid_cycle_schedule
    plan = sub.pending_plan or sub.plan
    provider, mode = state.billing_gateway.provider, state.billing_gateway.mode.value
    identity = schedule.lifecycle_id if schedule is not None else None
    terms = {'version': 'anniversary-invoice-v1', 'lifecycle_id': identity,
        'plan_fingerprint': _plan_fingerprint(plan), 'provider': provider, 'mode': mode}
    fingerprint = sha256(json.dumps(terms, sort_keys=True).encode()).hexdigest()
    saved = sub.renewal_invoice_consent
    valid = bool(saved is not None and saved.lifecycle_id == identity and saved.fingerprint == fingerprint)
    can_enable = (plan.credit_policy is not None and schedule is not None and schedule.anchor_at is not None
        and sub.status is SubscriptionStatus.ACTIVE and sub.cancel_at_period_end is None
        and not has_payment_review(state, tenant))
    return {'enabled': saved is not None, 'valid': valid, 'can_enable': can_enable,
        'fingerprint': fingerprint, 'lifecycle_id': identity, 'plan_name': plan.name,
        'monthly_price': str(plan.monthly_price.quantize(Decimal('0.01'))),
        'currency': plan.currency, 'provider': provider, 'mode': mode,
        'next_due_at': (schedule.bounds(schedule.paid_through_index + 1)[0].isoformat()
                        if schedule is not None and schedule.anchor_at is not None else None),
        'accepted_at': saved.accepted_at.isoformat() if saved is not None else None}


def set_renewal_consent(state, fixture, key, body, *, at=None):
    now = at or datetime.now(timezone.utc)
    tenant = fixture.tenant_id
    context = sha256(json.dumps([fixture.user_id, fixture.business_unit_id, body], sort_keys=True).encode()).hexdigest()
    def update():
        quote = renewal_quote(state, tenant, at=now)
        if body.get('fingerprint') != quote['fingerprint']:
            raise ApiError('BILLING_QUOTE_CHANGED', 'As condições da renovação mudaram; revise novamente.', status_code=409)
        if body.get('enabled') is True and not quote['can_enable']:
            raise ApiError('BILLING_RENEWAL_REJECTED', 'Autorização exige contrato pago vigente e sem pendências.', status_code=409)
        sub = state.subscriptions[tenant]
        consent = (RenewalInvoiceConsent(quote['lifecycle_id'], quote['fingerprint'], now,
            fixture.user_id, fixture.business_unit_id) if body.get('enabled') is True else None)
        state.subscriptions[tenant] = replace(sub, renewal_invoice_consent=consent)
        state.audit.append(tenant_id=tenant, actor=fixture.user_id,
            action='BILLING_RENEWAL_CONSENT_CHANGED', target=quote['lifecycle_id'] or sub.plan.plan_id,
            details={'enabled': consent is not None, 'fingerprint': quote['fingerprint'],
                     'automatic_debit_authorized': False})
        return {'context': context, 'response': renewal_quote(state, tenant, at=now)}
    result, _ = state.idempotency.execute(tenant, 'http:billing-renewal-consent:' + key, update)
    if result['context'] != context:
        raise ApiError('IDEMPOTENCY_CONFLICT', 'A chave identifica outra autorização ou contexto.', status_code=409)
    return result['response']


def process_renewal_invoice(state, tenant, *, execute=False, dispatch_enabled=False, at=None):
    """Trusted private runtime, one explicit tenant. No trial/first-payment conversion."""
    from .routes_billing import _prepare_billing_charge, _persist_billing_charge, _plan_fingerprint
    now = at or datetime.now(timezone.utc)
    sub = state.subscriptions.get(tenant)
    schedule = sub.paid_cycle_schedule if sub is not None else None
    if schedule is None or schedule.anchor_at is None or sub.plan.credit_policy is None:
        return {'state': 'UNAVAILABLE'}
    index = schedule.paid_through_index + 1
    identity = schedule.obligation_id(tenant, index)
    existing = next(((gid, charge) for gid, charge in state.charges.items_for_tenant(tenant)
                     if charge.billing_id == identity), None)
    if existing is not None:
        return {'state': 'REGISTERED', 'billing_id': identity, 'gateway_charge_id': existing[0]}
    dispatched = state.idempotency.get(tenant, 'billing-dispatch:' + identity) is not None
    due = schedule.bounds(index)[0]
    if not dispatched:
        quote = renewal_quote(state, tenant, at=now)
        if not quote['enabled'] or not quote['valid'] or not quote['can_enable']:
            return {'state': 'CONSENT_REQUIRED', 'billing_id': identity}
        if now < due:
            return {'state': 'NOT_DUE', 'billing_id': identity, 'available_at': due.isoformat()}
    if not execute:
        return {'state': 'DRY_RUN', 'billing_id': identity, 'recovery_only': dispatched, 'due_at': due.isoformat()}
    if not dispatched and dispatch_enabled is not True:
        return {'state': 'DISABLED', 'billing_id': identity}
    fixture = SimpleNamespace(tenant_id=tenant, user_id='billing-renewal-worker',
                              business_unit_id=None, actor_kind='SYSTEM')
    body = BillingChargeCreate(competence='server-anniversary')
    def validate(charge=None):
        fresh = state.subscriptions.get(tenant)
        fresh_quote = renewal_quote(state, tenant)
        if (fresh is None or fresh.paid_cycle_schedule is None
                or fresh.paid_cycle_schedule.lifecycle_id != schedule.lifecycle_id
                or not fresh_quote['enabled'] or not fresh_quote['valid'] or not fresh_quote['can_enable']
                or datetime.now(timezone.utc) < due
                or (charge is not None and _plan_fingerprint(charge.commercial_plan)
                    != _plan_fingerprint(fresh.pending_plan or fresh.plan))):
            raise ApiError('BILLING_RENEWAL_REJECTED', 'Autorização ou contratação mudou antes da emissão.', status_code=409)
    def prepare():
        if state.idempotency.get(tenant, 'billing-dispatch:' + identity) is not None:
            frozen = state.idempotency.get(tenant, 'billing-obligation:' + identity)
            if frozen is None:
                raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Emissão sem obrigação comprovada.', status_code=409)
            return frozen.result  # Existing fence allows GET recovery only, including after revocation.
        validate()
        charge = _prepare_billing_charge(state, fixture, body)
        if charge.billing_id != identity:
            raise ApiError('BILLING_RENEWAL_REJECTED', 'O ciclo mudou; execute a próxima conferência.', status_code=409)
        return charge
    try:
        result = execute_invoice(state, fixture, 'anniversary:' + identity, body.model_dump(mode='json'),
            prepare, dispatch_frozen_charge, lambda charge, result: _persist_billing_charge(state, fixture, charge, result),
            operation='billing_renewal', validate_dispatch=validate)
    except ApiError as exc:
        return {'state': 'REVIEW_REQUIRED', 'billing_id': identity, 'code': exc.code}
    return {**result, 'state': 'REGISTERED'}
