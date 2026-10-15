"""Final delivered usage belongs to the closed lifecycle; it never buys another month."""
from decimal import Decimal
from hashlib import sha256
import json

from campaia_core.credit_ledger import CreditLedgerError
from campaia_core.subscription import SubscriptionStatus, SubscriptionCharge, ChargeLineItem, ChargePurpose, ChargeStatus
from .billing_dispatch import obligation_key
from .errors import ApiError


def closure_key(lifecycle):
    return 'billing-closure:' + lifecycle


def result_key(lifecycle):
    return 'billing-closure-result:' + lifecycle


def record_closed_lifecycle(state, sub):
    schedule = sub.paid_cycle_schedule
    if (sub.plan.credit_policy is not None and sub.status is SubscriptionStatus.CANCELED
            and schedule is not None and schedule.anchor_at is not None):
        # Preserve the paid schedule/terms before reactivation replaces their identity.
        state.idempotency.execute(sub.tenant_id, closure_key(schedule.lifecycle_id), lambda: sub)


def closure_quote(state, sub):
    schedule = sub.paid_cycle_schedule
    if sub.status is not SubscriptionStatus.CANCELED or schedule is None or schedule.anchor_at is None:
        return {'state': 'UNAVAILABLE', 'fingerprint': None, 'amount': None, 'minimum': None, 'lifecycle_id': None,
                'cycle_id': None, 'invoice': None, 'provider': None, 'mode': None}
    lifecycle = schedule.lifecycle_id
    stored = state.idempotency.get(sub.tenant_id, closure_key(lifecycle))
    if stored is None:
        raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Encerramento sem snapshot financeiro.', status_code=503)
    closed = stored.result
    schedule = closed.paid_cycle_schedule
    index = schedule.paid_through_index
    cycle_id = schedule.obligation_id(sub.tenant_id, index)
    if state.credit_ledger is None:
        raise ApiError('BILLING_USAGE_UNAVAILABLE', 'Medição financeira indisponível.', status_code=503)
    try:
        balance = state.credit_ledger.balance(sub.tenant_id, cycle_id)
    except CreditLedgerError as exc:
        raise ApiError('BILLING_USAGE_UNAVAILABLE', 'Consumo sem ciclo reconciliado.', status_code=503) from exc
    if balance.reserved_credits:
        status = 'PENDING_USAGE'
    else:
        status = 'READY'
    amount = balance.extra_consumed_amount
    minimum = getattr(state.billing_gateway, 'minimum_charge_amount', None)
    if minimum is not None and (not isinstance(minimum, Decimal) or not minimum.is_finite() or minimum <= 0 or minimum > Decimal('1000000000000') or minimum != minimum.quantize(Decimal('0.01'))):
        minimum = None
    final_id = schedule.obligation_id(sub.tenant_id, index, purpose='FINAL_USAGE')
    invoice = next((c for _key, c in state.charges.items_for_tenant(sub.tenant_id) if c.billing_id == final_id), None)
    frozen = state.idempotency.get(sub.tenant_id, obligation_key(final_id))
    closed_result = state.idempotency.get(sub.tenant_id, result_key(lifecycle))
    if closed_result is not None:
        status = closed_result.result['state']
        amount = Decimal(closed_result.result['amount'])
        if status == 'INVOICED' and invoice is not None and invoice.status is ChargeStatus.SETTLED:
            status = 'SETTLED'
    elif frozen is not None:
        status = 'INVOICE_REQUIRED'
        amount = frozen.result.amount
    elif status == 'READY':
        # Never charge the same usage again if a renewal already included it. Even
        # an uncertain/unpaid renewal must be reconciled/canceled before separating it.
        next_base = schedule.obligation_id(sub.tenant_id, index + 1)
        if state.idempotency.get(sub.tenant_id, obligation_key(next_base)) is not None:
            status = 'RECONCILIATION_REQUIRED'
        elif amount == 0:
            status = 'NO_CHARGE'
        elif minimum is None:
            status = 'MINIMUM_UNAVAILABLE'
        elif amount < minimum:
            status = 'ABSORBABLE'
        else:
            status = 'INVOICE_REQUIRED'
    provider = (frozen.result.commercial_gateway_provider if frozen is not None else state.billing_gateway.provider)
    mode = (frozen.result.commercial_gateway_mode if frozen is not None else state.billing_gateway.mode.value)
    payload = {'provider': provider, 'mode': mode, 'state': status, 'amount': str(amount.quantize(Decimal('0.01'))),
               'minimum': str(minimum) if minimum is not None else None,
               'lifecycle_id': lifecycle, 'cycle_id': cycle_id, 'invoice': invoice.billing_id if invoice else None}
    payload['fingerprint'] = sha256(json.dumps({key: value for key, value in payload.items()
        if key not in {'state', 'invoice'}}, sort_keys=True).encode()).hexdigest()
    return payload


def final_charge(state, sub):
    quote = closure_quote(state, sub)
    if quote['state'] not in {'INVOICE_REQUIRED', 'INVOICED'}:
        raise ApiError('BILLING_FINAL_USAGE_PENDING', 'Fechamento exige conferência de consumo/obrigações antes de emitir.', status_code=409)
    closed = state.idempotency.get(sub.tenant_id, closure_key(quote['lifecycle_id'])).result
    schedule = closed.paid_cycle_schedule
    if closed.canceled_at is None:
        raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Encerramento sem data financeira conhecida.', status_code=503)
    index = schedule.paid_through_index
    identity = schedule.obligation_id(sub.tenant_id, index, purpose='FINAL_USAGE')
    frozen = state.idempotency.get(sub.tenant_id, obligation_key(identity))
    if frozen is not None:
        return frozen.result
    paid = next((c for _key, c in state.charges.items_for_tenant(sub.tenant_id)
                 if c.billing_id == quote['cycle_id']), None)
    if paid is None or paid.commercial_plan is None:
        raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Termos do ciclo consumido indisponíveis.', status_code=503)
    return SubscriptionCharge(billing_id=identity, tenant_id=sub.tenant_id, customer_ref=closed.customer_ref,
        customer_document=closed.customer_document, competence=f'final:{index}', currency=paid.currency,
        line_items=(ChargeLineItem('Excedente final do período pago; sem nova mensalidade', Decimal(quote['amount'])),),
        plan_id=paid.plan_id, purpose=ChargePurpose.FINAL_USAGE,
        commercial_cycle_index=index, commercial_lifecycle_id=schedule.lifecycle_id,
        commercial_plan=paid.commercial_plan, commercial_due_at=closed.canceled_at,
        commercial_gateway_provider=state.billing_gateway.provider,
        commercial_gateway_mode=state.billing_gateway.mode.value)


def close_without_invoice(state, sub, *, actor):
    quote = closure_quote(state, sub)
    if quote['state'] not in {'NO_CHARGE', 'ABSORBABLE', 'ABSORBED'}:
        raise ApiError('BILLING_FINAL_USAGE_PENDING', 'Consumo final ou obrigação anterior ainda pendente de quitação.', status_code=409)
    result = {**quote, 'state': 'ABSORBED' if Decimal(quote['amount']) else 'NO_CHARGE'}
    saved, replayed = state.idempotency.execute(sub.tenant_id, result_key(quote['lifecycle_id']), lambda: result)
    if not replayed:
        state.audit.append(tenant_id=sub.tenant_id, actor=actor, action='BILLING_FINAL_USAGE_CLOSED',
                           target=quote['lifecycle_id'], details={'state': saved['state'], 'amount': saved['amount']})
    return saved


def require_final_usage_resolved(state, sub, *, actor):
    if sub.plan.credit_policy is None or sub.status is not SubscriptionStatus.CANCELED:
        return
    quote = closure_quote(state, sub)
    if quote['state'] == 'UNAVAILABLE':
        return  # Trial never had post-paid extras.
    if quote['state'] in {'NO_CHARGE', 'ABSORBABLE', 'ABSORBED'}:
        close_without_invoice(state, sub, actor=actor)
    elif quote['state'] != 'SETTLED':
        raise ApiError('BILLING_FINAL_USAGE_PENDING', 'Conclua e quite o consumo final antes da nova contratação.', status_code=409)
