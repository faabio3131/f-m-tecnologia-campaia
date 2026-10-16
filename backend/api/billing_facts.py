"""Persist the existing settled fact once; never a second debit or grant authority."""
from .billing_receipts import tenant_charges

FIRST_PAID_KEY = 'billing-first-paid'


def fact_key(billing_id):
    return 'billing-settlement-fact:' + billing_id


def record_settled_fact(state, charge, event, fact, *, source):
    if charge.commercial_lifecycle_id is None:
        return
    record = {'fact': {'billing_id': fact.billing_id, 'amount': fact.amount,
        'currency': fact.currency, 'settled_at': fact.settled_at},
        'gateway_charge_id': event.payment_id, 'event_id': event.event_id,
        'source': source, 'provider': charge.gateway_provider, 'mode': charge.gateway_mode,
        'lifecycle_id': charge.commercial_lifecycle_id, 'purpose': charge.purpose.value}
    recorded, _ = state.idempotency.execute(charge.tenant_id, fact_key(charge.billing_id), lambda: record)
    def first_paid():
        candidates = [recorded]
        for gateway_id, previous in tenant_charges(state, charge.tenant_id):
            if previous.billing_id == charge.billing_id:
                continue
            if previous.status.value != 'SETTLED':
                continue
            saved = state.idempotency.get(charge.tenant_id, fact_key(previous.billing_id))
            if saved is None or saved.result['gateway_charge_id'] != gateway_id:
                return {'state': 'HISTORY_REVIEW_REQUIRED'}
            candidates.append(saved.result)
        earliest = min(candidates, key=lambda item: item['fact']['settled_at'])
        return {'state': 'KNOWN', 'billing_id': earliest['fact']['billing_id'],
                'paid_at': earliest['fact']['settled_at']}
    state.idempotency.execute(charge.tenant_id, FIRST_PAID_KEY, first_paid)
