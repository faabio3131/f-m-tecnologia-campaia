"""A timely guarantee REQUEST is not a completed refund or fiscal adjustment."""
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
import json

from campaia_core.subscription import cancel_subscription
from .billing_facts import FIRST_PAID_KEY, fact_key
from .billing_receipts import tenant_charges
from .billing_closure import record_closed_lifecycle
from .errors import ApiError

REQUEST_KEY = 'billing-guarantee-request'


def guarantee_quote(state, tenant, *, at):
    pending = state.idempotency.get(tenant, REQUEST_KEY)
    if pending is not None:
        return pending.result
    result = {'state': 'UNAVAILABLE', 'fingerprint': None, 'first_paid_at': None,
        'deadline': None, 'paid_amount': None, 'currency': 'BRL', 'items': [],
        'request_id': None, 'requested_at': None}
    first = state.idempotency.get(tenant, FIRST_PAID_KEY)
    rows = tenant_charges(state, tenant)
    paid = [(key, charge) for key, charge in rows if charge.status.value == 'SETTLED']
    if first is None:
        if paid:
            result['state'] = 'MANUAL_REVIEW'
        return result
    marker = first.result
    if marker.get('state') != 'KNOWN':
        return {**result, 'state': 'MANUAL_REVIEW'}
    start = marker['paid_at']
    end = start + timedelta(days=7)
    result.update(first_paid_at=start.isoformat(), deadline=end.isoformat())
    if at < start:
        return {**result, 'state': 'MANUAL_REVIEW'}
    items = []
    seen = set()
    for gateway_id, charge in paid:
        saved = state.idempotency.get(tenant, fact_key(charge.billing_id))
        if (saved is None or saved.result['gateway_charge_id'] != gateway_id
                or charge.billing_id in seen):
            return {**result, 'state': 'MANUAL_REVIEW'}
        seen.add(charge.billing_id)
        fact = saved.result['fact']
        if fact['currency'] != 'BRL' or fact['amount'] != charge.amount:
            return {**result, 'state': 'MANUAL_REVIEW'}
        if start <= fact['settled_at'] <= min(at, end):
            items.append({'billing_id': charge.billing_id, 'gateway_charge_id': gateway_id,
                'amount': str(fact['amount']), 'paid_at': fact['settled_at'].isoformat(),
                'purpose': charge.purpose.value, 'provider': saved.result['provider'],
                'mode': saved.result['mode']})
    items.sort(key=lambda item: (item['paid_at'], item['billing_id']))
    if not items:
        return {**result, 'state': 'MANUAL_REVIEW'}
    result.update(state='ELIGIBLE' if at <= end else 'EXPIRED', items=items,
                  paid_amount=str(sum((Decimal(item['amount']) for item in items), Decimal('0.00'))))
    result['fingerprint'] = sha256(json.dumps({key: value for key, value in result.items()
        if key not in {'state', 'fingerprint'}}, sort_keys=True).encode()).hexdigest()
    return result


def request_guarantee(state, fixture, key, body, *, at):
    if body.get('accept') is not True:
        raise ApiError('VALIDATION_FAILED', 'Confirme a solicitação e o encerramento do acesso pago.', status_code=422)
    tenant = fixture.tenant_id
    context = sha256(json.dumps([fixture.user_id, fixture.business_unit_id, body], sort_keys=True).encode()).hexdigest()
    def register():
        existing = state.idempotency.get(tenant, REQUEST_KEY)
        if existing is not None:
            if existing.result['fingerprint'] != body.get('fingerprint'):
                raise ApiError('BILLING_QUOTE_CHANGED', 'Consulte a solicitação já registrada.', status_code=409)
            return {'context': context, 'response': existing.result}
        quote = guarantee_quote(state, tenant, at=at)
        if quote['state'] != 'ELIGIBLE' or quote['fingerprint'] != body.get('fingerprint'):
            raise ApiError('BILLING_GUARANTEE_REVIEW_REQUIRED',
                'Revise a janela comercial e os pagamentos. Direitos legais e revisão de cobranças indevidas permanecem preservados.',
                status_code=409)
        sub = state.subscriptions.get(tenant)
        if sub is None or sub.plan.credit_policy is None:
            raise ApiError('BILLING_GUARANTEE_REVIEW_REQUIRED', 'Contrato exige conferência antes da solicitação.', status_code=409)
        def accept():
            canceled = cancel_subscription(sub, now=at, immediate=True)
            state.subscriptions[tenant] = canceled
            record_closed_lifecycle(state, canceled)
            result = {**quote, 'state': 'REQUESTED',
                'request_id': 'campaia:guarantee:' + sha256((tenant + ':' + quote['first_paid_at']).encode()).hexdigest(),
                'requested_at': at.isoformat()}
            state.audit.append(tenant_id=tenant, actor=fixture.user_id, action='BILLING_GUARANTEE_REQUESTED',
                target=result['request_id'], details={'paid_amount': quote['paid_amount'],
                    'billing_ids': [item['billing_id'] for item in quote['items']],
                    'requested_at': result['requested_at'], 'deadline': quote['deadline'],
                    'paid_access_ended': True, 'refund_dispatched': False})
            return result
        accepted, _ = state.idempotency.execute(tenant, REQUEST_KEY, accept)
        return {'context': context, 'response': accepted}
    result, _ = state.idempotency.execute(tenant, 'http:billing-guarantee:' + key, register)
    if result['context'] != context:
        raise ApiError('IDEMPOTENCY_CONFLICT', 'A chave identifica outra solicitação ou contexto.', status_code=409)
    return result['response']
