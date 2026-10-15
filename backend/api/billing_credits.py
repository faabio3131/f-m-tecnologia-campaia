"""Trusted subscription-to-credit boundary. Reads never invent quota or usage."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from hashlib import sha256

from campaia_core.credit_ledger import CreditCycle, CreditLedgerError
from campaia_core.subscription import SubscriptionStatus, PastDueAccessMode, refresh_trial_status, entitlement_access_is_active

from .errors import ApiError
from .billing_receipts import payment_access_is_blocked


def cycle_snapshot(subscription, *, at: datetime):
    policy = subscription.plan.credit_policy
    schedule = subscription.paid_cycle_schedule
    if policy is None or schedule is None:
        return None
    if subscription.status is SubscriptionStatus.TRIAL:
        return CreditCycle(subscription.tenant_id, 'trial:' + schedule.lifecycle_id,
                           subscription.trial_started_at, subscription.trial_ends_at,
                           policy.version, policy.trial_credits,
                           subscription.plan.extra_credit_unit_price,
                           policy.action_weights, trial=True)
    index = schedule.current_paid_index(at)
    if index is None:
        if schedule.anchor_at is None:
            return None
        index = schedule.paid_through_index
        _start, end = schedule.bounds(index)
        dunning = subscription.plan.dunning_policy
        if (dunning is None or dunning.access_mode is not PastDueAccessMode.ALLOW_DURING_GRACE
                or not end <= at < end + timedelta(days=dunning.grace_period_days)):
            return None
    start, end = schedule.bounds(index)
    return CreditCycle(subscription.tenant_id, schedule.obligation_id(subscription.tenant_id, index),
                       start, end, policy.version, int(subscription.plan.included_credits),
                       subscription.plan.extra_credit_unit_price, policy.action_weights,
                       included_grace_ends_at=(end + timedelta(days=subscription.plan.dunning_policy.grace_period_days)
                                               if subscription.plan.dunning_policy and subscription.plan.dunning_policy.access_mode
                                               is PastDueAccessMode.ALLOW_DURING_GRACE else None))


def grant_current_cycle(state, subscription, *, at: datetime) -> None:
    if subscription.plan.credit_policy is None:
        return
    if state.credit_ledger is None:
        raise ApiError('BILLING_USAGE_UNAVAILABLE', 'Persistência de créditos indisponível.', status_code=503)
    cycle = cycle_snapshot(subscription, at=at)
    if cycle is not None:
        state.credit_ledger.decide(subscription.tenant_id, 'open_cycle', cycle=cycle, at=at)
        consent = subscription.extra_credit_consent
        if (not cycle.trial and cycle.starts_at <= at < cycle.ends_at and consent is not None
                and consent.tenant_id == subscription.tenant_id
                and consent.policy_version == cycle.policy_version
                and consent.extra_credit_price == cycle.extra_credit_price):
            reference = sha256((consent.reference + ':' + cycle.cycle_id).encode()).hexdigest()
            state.credit_ledger.decide(subscription.tenant_id, 'consent', cycle_id=cycle.cycle_id,
                                      cap=consent.cap, actor=consent.actor,
                                      reference=reference, at=at)



def grant_paid_cycle(state, subscription, *, index, plan, at):
    schedule = subscription.paid_cycle_schedule
    if schedule is None or plan.credit_policy is None or state.credit_ledger is None:
        raise ApiError('BILLING_USAGE_UNAVAILABLE', 'Ciclo pago sem termos ou persistência.', status_code=503)
    start, end = schedule.bounds(index)
    policy = plan.credit_policy
    cycle = CreditCycle(subscription.tenant_id, schedule.obligation_id(subscription.tenant_id, index),
                        start, end, policy.version, int(plan.included_credits),
                        plan.extra_credit_unit_price, policy.action_weights,
                        included_grace_ends_at=(end + timedelta(days=plan.dunning_policy.grace_period_days)
                            if plan.dunning_policy and plan.dunning_policy.access_mode
                            is PastDueAccessMode.ALLOW_DURING_GRACE else None))
    state.credit_ledger.decide(subscription.tenant_id, 'open_cycle', cycle=cycle, at=at)
    consent = subscription.extra_credit_consent
    if (consent is not None and at < end and consent.tenant_id == subscription.tenant_id
            and consent.policy_version == cycle.policy_version
            and consent.extra_credit_price == cycle.extra_credit_price):
        reference = sha256((consent.reference + ':' + cycle.cycle_id).encode()).hexdigest()
        state.credit_ledger.decide(subscription.tenant_id, 'consent', cycle_id=cycle.cycle_id,
                                  cap=consent.cap, actor=consent.actor, reference=reference, at=at)


def usage_payload(state, subscription, *, at: datetime | None = None) -> dict:
    now = at or datetime.now(timezone.utc)
    current = refresh_trial_status(subscription, now=now)
    snapshot = cycle_snapshot(current, at=now)
    unavailable = {'access_active': False, 'can_authorize_extras': False, 'availability': 'UNAVAILABLE', 'cycle': None, 'balance': None, 'actions': [], 'alerts': []}
    if state.credit_ledger is None or snapshot is None:
        return unavailable
    try:
        balance = state.credit_ledger.balance(subscription.tenant_id, snapshot.cycle_id)
    except CreditLedgerError:
        return unavailable
    alerts = []
    committed = balance.consumed_credits + balance.reserved_credits
    if balance.included_credits:
        for level in (80, 100):
            if committed * 100 >= balance.included_credits * level:
                alerts.append(f'INCLUDED_{level}')
    if balance.extra_cap:
        for level in (80, 100):
            if balance.extra_committed_amount * 100 >= balance.extra_cap * level:
                alerts.append(f'EXTRA_CAP_{level}')
    return {
        'access_active': entitlement_access_is_active(current, now=now) and not payment_access_is_blocked(state, current, at=now),
        'can_authorize_extras': (entitlement_access_is_active(current, now=now) and not payment_access_is_blocked(state, current, at=now) and not snapshot.trial
                                 and snapshot.starts_at <= now < snapshot.ends_at),
        'alerts': alerts,
        'availability': 'AVAILABLE',
        'cycle': {'id': snapshot.cycle_id, 'starts_at': snapshot.starts_at.isoformat(),
                  'ends_at': snapshot.ends_at.isoformat(), 'trial': snapshot.trial,
                  'policy_version': snapshot.policy_version},
        'balance': {'included_credits': balance.included_credits,
                    'reserved_credits': balance.reserved_credits,
                    'consumed_credits': balance.consumed_credits,
                    'included_available': balance.included_available,
                    'extra_committed_amount': str(balance.extra_committed_amount),
                    'extra_consumed_amount': str(balance.extra_consumed_amount),
                    'extra_cap': str(balance.extra_cap),
                    'extra_credit_price': str(snapshot.extra_credit_price), 'currency': 'BRL'},
        'actions': [{'action': name, 'credits': amount} for name, amount in snapshot.action_weights],
    }
