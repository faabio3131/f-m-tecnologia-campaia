"""Durable finance inbox. Availability, user reading and external delivery are distinct."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

from campaia_core.subscription import ChargeStatus, ChargePurpose, SubscriptionStatus, refresh_trial_status
from .billing_receipts import tenant_charges, has_payment_review, REVIEW_STATES
from .billing_void import verified_void
from .errors import ApiError


def notice_id(tenant, billing_id, offset):
    return 'notice_' + sha256(json.dumps([tenant, billing_id, offset]).encode()).hexdigest()


def read_id(tenant, user, identity):
    return sha256(json.dumps([tenant, user, identity]).encode()).hexdigest()


class BillingNoticeRepository:
    def __init__(self, table=None, reads=None):
        self._table, self._reads = table, reads
        self._items, self._read_items = {}, {}

    def get(self, tenant, identity):
        return (self._table.get_for_tenant(identity, tenant) if self._table is not None
                else self._items.get((tenant, identity)))

    def append(self, tenant, record):
        previous = self.get(tenant, record['id'])
        if previous is not None:
            return previous
        if self._table is not None:
            self._table.put(record['id'], tenant, record)
        else:
            self._items[(tenant, record['id'])] = record
        return record

    def list(self, tenant):
        return ([record for _id, _tenant, record in self._table.rows_for_tenant(tenant)]
                if self._table is not None else [r for (t, _id), r in self._items.items() if t == tenant])

    def read_at(self, tenant, user, identity):
        key = read_id(tenant, user, identity)
        result = (self._reads.get_for_tenant(key, tenant) if self._reads is not None
                  else self._read_items.get((tenant, key)))
        return result['read_at'] if result is not None else None

    def mark_read(self, tenant, user, identity, *, at):
        existing = self.read_at(tenant, user, identity)
        if existing is not None:
            return existing
        record = {'notice_id': identity, 'user_id': user, 'read_at': at}
        key = read_id(tenant, user, identity)
        if self._reads is not None:
            self._reads.put(key, tenant, record)
        else:
            self._read_items[(tenant, key)] = record
        return at


def _candidate(state, tenant, gateway_id, charge, at):
    if (charge.tenant_id != tenant or charge.commercial_lifecycle_id is None
            or charge.commercial_plan is None or charge.commercial_plan.credit_policy is None
            or charge.status is ChargeStatus.SETTLED or charge.commercial_due_at is None
            or charge.commercial_due_at > at or verified_void(state, tenant, charge.billing_id)
            or has_payment_review(state, tenant)):
        return None
    policy = charge.commercial_plan.dunning_policy
    if policy is None:
        return None
    sub = state.subscriptions.get(tenant)
    if sub is None:
        return None
    if charge.purpose is ChargePurpose.FINAL_USAGE:
        closed = state.idempotency.get(tenant, 'billing-closure:' + charge.commercial_lifecycle_id)
        if closed is None or closed.result.status is not SubscriptionStatus.CANCELED:
            return None
    else:
        sub = refresh_trial_status(sub, now=at)
        if (charge.commercial_cycle_index is None or charge.commercial_cycle_index < 1
                or sub.status not in {SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE}
                or sub.paid_cycle_schedule is None
                or sub.paid_cycle_schedule.lifecycle_id != charge.commercial_lifecycle_id
                or sub.cancel_at_period_end is not None):
            return None
    due = charge.commercial_due_at
    elapsed = [offset for offset in policy.reminder_offsets_days if due + timedelta(days=offset) <= at]
    if not elapsed:
        return None
    offset = max(elapsed)  # An offline worker never pretends the missed reminders were delivered.
    return {'id': notice_id(tenant, charge.billing_id, offset), 'billing_id': charge.billing_id,
        'gateway_charge_id': gateway_id, 'offset_days': offset, 'scheduled_at': due + timedelta(days=offset),
        'due_at': due, 'amount': str(charge.amount), 'currency': charge.currency,
        'channel': 'IN_APP', 'created_at': at, 'mode': charge.commercial_gateway_mode,
        'earlier_offsets_not_backfilled': [day for day in elapsed if day < offset]}


def process_billing_notices(state, tenant, *, execute=False, at=None):
    """Private worker; no payment lookup, email, SMS or payment-state mutation."""
    now = at or datetime.now(timezone.utc)
    results = []
    for gateway_id, charge in tenant_charges(state, tenant):
        candidate = _candidate(state, tenant, gateway_id, charge, now)
        if candidate is None:
            continue
        if not execute:
            results.append({'state': 'DRY_RUN', 'id': candidate['id'], 'offset_days': candidate['offset_days']})
            continue
        def deliver():
            fresh = state.charges.get(gateway_id)
            record = _candidate(state, tenant, gateway_id, fresh, now) if fresh is not None else None
            if record is None or record['id'] != candidate['id']:
                raise ApiError('NOTICE_NO_LONGER_ELIGIBLE', 'Aviso não é mais aplicável.', status_code=409)
            saved = state.billing_notices.append(tenant, record)
            state.audit.append(tenant_id=tenant, actor='billing-notice-worker', actor_kind='SYSTEM',
                action='BILLING_NOTICE_AVAILABLE', target=saved['id'],
                details={'billing_id': saved['billing_id'], 'channel': 'IN_APP',
                         'offset_days': saved['offset_days'], 'external_message_sent': False})
            return {'state': 'AVAILABLE', 'id': saved['id'], 'offset_days': saved['offset_days']}
        try:
            result, _ = state.idempotency.execute(tenant, 'billing-notice-delivery:' + candidate['id'], deliver)
        except ApiError as exc:
            if exc.code != 'NOTICE_NO_LONGER_ELIGIBLE':
                raise
            result = {'state': 'SUPPRESSED', 'id': candidate['id']}
        results.append(result)
    return {'state': 'PROCESSED' if execute else 'DRY_RUN', 'items': results}


def serialize_notice(state, tenant, user, notice):
    charge = state.charges.get(notice['gateway_charge_id'])
    status = 'INVOICE_UNAVAILABLE'
    if charge is not None and charge.tenant_id == tenant and charge.billing_id == notice['billing_id']:
        status = ('REVIEW_REQUIRED' if charge.payment_reconciliation_state in REVIEW_STATES else
            'FINANCIALLY_ADJUSTED' if charge.payment_reconciliation_state == 'GUARANTEE_REFUNDED' else
            'PAYMENT_CONFIRMED' if charge.status is ChargeStatus.SETTLED else
            'VOID' if verified_void(state, tenant, charge.billing_id) else 'PENDING_CONFIRMATION')
    return {'id': notice['id'], 'billing_id': notice['billing_id'],
        'gateway_charge_id': notice['gateway_charge_id'], 'channel': 'IN_APP',
        'offset_days': notice['offset_days'], 'scheduled_at': notice['scheduled_at'].isoformat(),
        'created_at': notice['created_at'].isoformat(), 'due_at': notice['due_at'].isoformat(),
        'amount': notice['amount'], 'currency': notice['currency'], 'mode': notice['mode'],
        'invoice_state': status, 'read_at': (state.billing_notices.read_at(tenant, user, notice['id']).isoformat()
            if state.billing_notices.read_at(tenant, user, notice['id']) is not None else None)}


def mark_notice_read(state, fixture, identity, key, *, at=None):
    tenant, user = fixture.tenant_id, fixture.user_id
    context = sha256(json.dumps([user, fixture.business_unit_id, identity]).encode()).hexdigest()
    def mark():
        notice = state.billing_notices.get(tenant, identity)
        if notice is None:
            raise ApiError('NOT_FOUND', 'Aviso indisponível.', status_code=404)
        timestamp = state.billing_notices.mark_read(tenant, user, identity, at=at or datetime.now(timezone.utc))
        return {'context': context, 'response': {'id': identity, 'read_at': timestamp.isoformat()}}
    result, _ = state.idempotency.execute(tenant, 'http:billing-notice-read:' + key, mark)
    if result['context'] != context:
        raise ApiError('IDEMPOTENCY_CONFLICT', 'A chave identifica outra leitura ou contexto.', status_code=409)
    return result['response']
