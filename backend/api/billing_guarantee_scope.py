"""Freeze the accepted request's existing obligations; a new contract is new consent."""
from datetime import datetime
from .billing_facts import fact_key
from .billing_receipts import tenant_charges
from .errors import ApiError

REQUEST_KEY = 'billing-guarantee-request'


def scope_key(case_id):
    return 'billing-guarantee-scope:' + case_id


def get_scope(state, tenant, case):
    saved = state.idempotency.get(tenant, scope_key(case['request_id']))
    return saved.result if saved is not None else None


def capture_scope(state, tenant, case, subscription):
    def freeze():
        at = datetime.fromisoformat(case['requested_at'])
        lifecycles = set()
        identities = {item['billing_id'] for item in case['items']}
        schedules = []
        for item in case['items']:
            fact = state.idempotency.get(tenant, fact_key(item['billing_id']))
            if fact is None or fact.result['gateway_charge_id'] != item['gateway_charge_id']:
                raise ApiError('BILLING_GUARANTEE_REVIEW_REQUIRED', 'Pedido sem prova do pagamento considerado.', status_code=409)
            lifecycles.add(fact.result['lifecycle_id'])
        schedule = subscription.paid_cycle_schedule
        if schedule is not None:
            lifecycles.add(schedule.lifecycle_id)
            schedules.append(schedule)
        for lifecycle in tuple(lifecycles):
            closed = state.idempotency.get(tenant, 'billing-closure:' + lifecycle)
            if closed is not None and closed.result.paid_cycle_schedule is not None:
                schedules.append(closed.result.paid_cycle_schedule)
        for _gateway_id, charge in tenant_charges(state, tenant):
            if charge.commercial_lifecycle_id not in lifecycles:
                continue
            frozen = state.idempotency.get(tenant, 'billing-obligation:' + charge.billing_id)
            if (charge.billing_id in identities or (charge.created_at is not None and charge.created_at <= at)
                    or (frozen is not None and frozen.stored_at <= at)):
                identities.add(charge.billing_id)
        for schedule in schedules:
            candidates = {schedule.obligation_id(tenant, schedule.paid_through_index + 1)}
            if schedule.paid_through_index >= 0:
                candidates.add(schedule.obligation_id(tenant, schedule.paid_through_index))
                candidates.add(schedule.obligation_id(tenant, schedule.paid_through_index, purpose='FINAL_USAGE'))
            for identity in candidates:
                frozen = state.idempotency.get(tenant, 'billing-obligation:' + identity)
                if frozen is not None and frozen.stored_at <= at:
                    identities.add(identity)
        return {'version': 'accepted-request-v1', 'request_id': case['request_id'],
            'requested_at': at, 'billing_ids': tuple(sorted(identities)),
            'lifecycle_ids': tuple(sorted(lifecycles))}
    result, _ = state.idempotency.execute(tenant, scope_key(case['request_id']), freeze)
    return result


def ensure_scope(state, tenant, case):
    known = get_scope(state, tenant, case)
    if known is not None:
        return known
    from .billing_refund_policy import validate_case
    validate_case(state, tenant, case)
    sub = state.subscriptions.get(tenant)
    at = datetime.fromisoformat(case['requested_at'])
    if (sub is None or sub.status.value != 'CANCELED' or sub.canceled_at is None or sub.canceled_at > at
            or state.idempotency.get(tenant, 'billing-guarantee-resolution') is not None):
        raise ApiError('BILLING_GUARANTEE_REVIEW_REQUIRED', 'Escopo histórico exige conferência, sem ampliar o pedido.', status_code=409)
    if sub.paid_cycle_schedule is not None:
        state.idempotency.execute(tenant, 'billing-closure:' + sub.paid_cycle_schedule.lifecycle_id, lambda: sub)
    return capture_scope(state, tenant, case, sub)


def access_scope_is_ended(state, tenant, case, subscription):
    scope = get_scope(state, tenant, case)
    if scope is None:
        return subscription.status.value == 'CANCELED'
    schedule = subscription.paid_cycle_schedule
    if schedule is None or schedule.lifecycle_id in scope['lifecycle_ids']:
        return subscription.status.value == 'CANCELED'
    return all(state.idempotency.get(tenant, 'billing-closure:' + lifecycle) is not None
               for lifecycle in scope['lifecycle_ids'])
