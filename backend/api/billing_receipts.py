"""Persist minimal authenticated observations; never substitute invoice value for cash.

Unknown/mismatched amounts are acknowledged after durable recording, but cannot settle
the obligation or grant access. No raw webhook/card/customer payload is retained here.
"""
from dataclasses import replace
from decimal import Decimal

from campaia_core.subscription import ChargeStatus
from .errors import ApiError

REVIEW_STATES = frozenset({'AMOUNT_MISSING', 'AMOUNT_MISMATCH', 'TERMS_MISMATCH', 'REVERSAL_PENDING', 'STATUS_MISMATCH', 'CANCELLATION_CONFLICT'})


def tenant_charges(state, tenant):
    return (state.charges.items_for_tenant(tenant) if hasattr(state.charges, 'items_for_tenant')
            else [(key, charge) for key, charge in state.charges.items() if charge.tenant_id == tenant])


def has_payment_review(state, tenant):
    return any(charge.payment_reconciliation_state in REVIEW_STATES for _key, charge in tenant_charges(state, tenant))


def payment_access_is_blocked(state, sub, *, at):
    schedule = sub.paid_cycle_schedule
    if sub.plan.credit_policy is None or schedule is None or schedule.anchor_at is None:
        return False
    index = schedule.current_paid_index(at)
    funding = schedule.obligation_id(sub.tenant_id, index if index is not None else schedule.paid_through_index)
    return any(charge.billing_id == funding and charge.payment_reconciliation_state in {'REVERSAL_PENDING', 'AMOUNT_MISMATCH', 'STATUS_MISMATCH'}
               for _key, charge in tenant_charges(state, sub.tenant_id))


def require_no_payment_review(state, tenant):
    if has_payment_review(state, tenant):
        raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Há recebimento ou ajuste pendente de conciliação; não emitir outra obrigação.', status_code=409)



def has_reversal_signal(event):
    return (event.event_type.startswith('PAYMENT_REFUND') or 'CHARGEBACK' in event.event_type
        or event.event_type in {'PAYMENT_PARTIALLY_REFUNDED', 'PAYMENT_RECEIVED_IN_CASH_UNDONE'}
        or 'REFUND' in event.asaas_status or 'CHARGEBACK' in event.asaas_status
        or event.refunds_present or bool(event.refund_observations))


def observe_refunds(state, charge, event, *, at):
    entries = event.refund_observations
    amount = None
    if entries is None:
        decision = 'MISSING'
    elif any(status not in {'DONE', 'PENDING', 'CANCELLED'} or value is None for status, value in entries):
        decision = 'INVALID'
    else:
        completed = sum((value for status, value in entries if status == 'DONE'), Decimal('0.00'))
        committed = sum((value for status, value in entries if status in {'DONE', 'PENDING'}), Decimal('0.00'))
        if committed > charge.amount or event.observed_amount != charge.amount:
            decision = 'AMOUNT_CONFLICT'
        elif charge.gateway_refund_amount is not None and completed < charge.gateway_refund_amount:
            decision = 'OBSERVATION_CONFLICT'
        else:
            amount = completed
            decision = ('FULL_DONE' if completed == charge.amount else
                        'PROCESSING' if any(status == 'PENDING' for status, _ in entries) else
                        'PARTIAL_DONE' if completed else 'NO_COMPLETED_REFUND')
    observed = replace(charge, gateway_refund_amount=(amount if amount is not None else charge.gateway_refund_amount),
        gateway_refund_state=decision, gateway_refund_observed_at=at)
    state.charges[event.payment_id] = observed
    return observed


def observe_payment(state, charge, event, *, at, gateway_status, source="WEBHOOK"):
    reversal = has_reversal_signal(event)
    if reversal:
        charge = observe_refunds(state, charge, event, at=at)
    if reversal:
        decision = 'REVERSAL_PENDING'
    elif source == 'RECONCILIATION' and gateway_status != 'CONFIRMED' and charge.status is ChargeStatus.SETTLED:
        decision = 'STATUS_MISMATCH'
    elif event.event_type == 'PAYMENT_UPDATED':
        decision = 'TERMS_MISMATCH' if event.observed_amount != charge.amount else 'TERMS_OBSERVED'
    elif event.observed_amount is None:
        decision = 'AMOUNT_MISSING'
    else:
        decision = 'MATCHED' if event.observed_amount == charge.amount else 'AMOUNT_MISMATCH'
    observation = {'payment_id': event.payment_id, 'billing_id': charge.billing_id,
        'event_type': event.event_type, 'gateway_status': gateway_status,
        'expected_amount': charge.amount, 'observed_amount': event.observed_amount,
        'observed_at': at, 'decision': decision, 'source': source,
        'refund_observations': event.refund_observations,
        'refund_state': charge.gateway_refund_state if reversal else None,
        'refund_completed_amount': charge.gateway_refund_amount if reversal else None}
    state.idempotency.execute(charge.tenant_id, 'billing-receipt:' + event.event_id, lambda: observation)
    if charge.payment_reconciliation_state in {'REVERSAL_PENDING', 'CANCELLATION_CONFLICT'} and not reversal:
        return charge.payment_reconciliation_state  # A stale confirmation cannot erase a known refund/dispute.
    if charge.payment_reconciliation_state == 'AMOUNT_MISMATCH' and decision in {'TERMS_OBSERVED', 'TERMS_MISMATCH'}:
        return 'AMOUNT_MISMATCH'  # Editing invoice terms is not evidence of missing cash arriving.
    if charge.status is ChargeStatus.SETTLED and not reversal:
        # A later duplicate/stale confirmation never replaces the proven settlement,
        # erases a refund observation or grants another period. Keep divergence evidence.
        if decision in {'MATCHED', 'AMOUNT_MISMATCH', 'TERMS_MISMATCH', 'STATUS_MISMATCH'}:
            state.charges[event.payment_id] = replace(charge, gateway_status=gateway_status,
                status_source=source, status_observed_at=at, gateway_observed_amount=event.observed_amount,
                payment_reconciliation_state=decision)
        state.audit.append(tenant_id=charge.tenant_id, actor='asaas', actor_kind='EXTERNAL_PROVIDER',
                           action='BILLING_RECEIPT_AFTER_SETTLEMENT_OBSERVED', target=charge.billing_id,
                           details={'decision': decision, 'event_id': event.event_id})
        return 'ALREADY_SETTLED' if decision == 'MATCHED' else 'STALE_DIVERGENCE'
    if decision == 'TERMS_OBSERVED':
        return decision  # A pending update is not a payment and cannot clear a receipt hold.
    state.charges[event.payment_id] = replace(charge, gateway_status=gateway_status,
        status_source=source, status_observed_at=at,
        gateway_observed_amount=event.observed_amount, payment_reconciliation_state=decision)
    state.audit.append(tenant_id=charge.tenant_id, actor='asaas', actor_kind='EXTERNAL_PROVIDER',
                       action='BILLING_PAYMENT_RECONCILIATION', target=charge.billing_id,
                       details={'decision': decision, 'event_id': event.event_id})
    return decision
