"""Private worker for an already accepted guarantee. Dry-run is the default.

No public money endpoint, no automatic expiration/reset of a dispatch fence.
An uncertain owner may only be recovered with a provider GET on future attempts.
"""
from datetime import datetime, timezone
from uuid import uuid4

from campaia_core.asaas_webhook import AsaasPaymentEvent
from campaia_core.billing_settlement import charge_command
from campaia_core.payment_gateway import refund_snapshot
from campaia_core.subscription import SubscriptionStatus, refresh_trial_status
from .billing_guarantee import REQUEST_KEY
from .billing_refund_policy import eligible_payments, refund_intent_key, processing_key, refund_progress, refund_review_key
from .errors import ApiError


def _context(state, charge):
    if (charge.commercial_gateway_provider != state.billing_gateway.provider
            or charge.commercial_gateway_mode != state.billing_gateway.mode.value):
        raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Gateway/ambiente original indisponível.', status_code=409)


def _observe(state, tenant, gateway_id, frozen, observed, *, started_at, case_id):
    if (observed.gateway_charge_id != gateway_id or observed.provider != frozen.commercial_gateway_provider
            or observed.mode.value != frozen.commercial_gateway_mode):
        raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Resposta externa incompatível.', status_code=503)
    event_id = 'guarantee-refund-read:' + uuid4().hex
    raw = observed.source_status or observed.status.value
    event = AsaasPaymentEvent(event_id, 'PAYMENT_RECONCILIATION', gateway_id, raw,
        observed.observed_amount, observed.refund_observations, observed.refunds_present, observed.chargeback_status)
    at = datetime.now(timezone.utc)
    def persist():
        from .routes_billing import _apply_verified_payment_event
        fresh = state.charges.get(gateway_id)
        if fresh is None or fresh.tenant_id != tenant or fresh.billing_id != frozen.billing_id:
            raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Obrigação mudou durante consulta.', status_code=409)
        response = _apply_verified_payment_event(state, fresh, event, observed_at=at,
            source='RECONCILIATION', mapped_status=observed.status, snapshot_started_at=started_at)
        state.audit.append(tenant_id=tenant, actor='billing-refund-worker', actor_kind='SYSTEM',
            action='BILLING_GUARANTEE_REFUND_OBSERVED', target=case_id,
            details={'billing_id': frozen.billing_id, 'event_id': event_id})
        return {'observed': True, 'processed': response.status_code == 200}
    state.idempotency.execute(tenant, 'billing-guarantee-observation:' + event_id, persist)


def process_guarantee_refunds(state, tenant, *, execute=False, at=None):
    """Caller is a private trusted runtime; the accepted tenant request is the authority."""
    now = at or datetime.now(timezone.utc)
    stored = state.idempotency.get(tenant, REQUEST_KEY)
    if stored is None:
        return {'state': 'UNAVAILABLE', 'items': [], 'excluded': []}
    case = stored.result
    try:
        eligible, excluded = eligible_payments(state, tenant, case, at=now)
        preview = refund_progress(state, tenant, case, at=now)
    except ApiError as exc:
        return {'state': 'REVIEW_REQUIRED', 'code': exc.code, 'items': [], 'excluded': []}
    if not execute:
        return {'state': 'DRY_RUN', 'request_id': case['request_id'], 'items': preview, 'excluded': excluded}
    sub = state.subscriptions.get(tenant)
    if sub is None or refresh_trial_status(sub, now=now).status is not SubscriptionStatus.CANCELED:
        return {'state': 'REVIEW_REQUIRED', 'code': 'PAID_ACCESS_NOT_ENDED', 'items': preview, 'excluded': excluded}
    if not callable(getattr(state.billing_gateway, 'refund_charge', None)):
        return {'state': 'REVIEW_REQUIRED', 'code': 'REFUND_UNSUPPORTED', 'items': preview, 'excluded': excluded}
    resolution = state.idempotency.get(tenant, 'billing-guarantee-resolution')
    if resolution is not None:
        return {'state': 'REVIEW_REQUIRED', 'code': 'CASE_RESOLUTION_REQUIRES_REVIEW', 'items': preview, 'excluded': excluded}
    enabled = getattr(state.billing_gateway, 'refund_dispatch_enabled', False) is True
    has_intent = any(state.idempotency.get(tenant, refund_intent_key(case['request_id'], charge.billing_id))
                     is not None for _gateway_id, charge, _record in eligible)
    if not enabled and not has_intent:
        return {'state': 'DISABLED', 'items': preview, 'excluded': excluded}
    def started():
        state.audit.append(tenant_id=tenant, actor='billing-refund-worker', actor_kind='SYSTEM',
            action='BILLING_GUARANTEE_PROCESSING_STARTED', target=case['request_id'],
            details={'completion_verified': False})
        return {'started_at': now, 'request_id': case['request_id']}
    state.idempotency.execute(tenant, processing_key(case['request_id']), started)
    results = []
    for gateway_id, charge, _record in eligible:
        key = refund_intent_key(case['request_id'], charge.billing_id)
        try:
            _context(state, charge)
            prior = state.idempotency.get(tenant, key)
            lookup_started = datetime.now(timezone.utc)
            try:
                current = state.billing_gateway.inspect_charge(gateway_id, charge_command(charge))
            except Exception:
                results.append({'billing_id': charge.billing_id, 'state': 'READ_UNAVAILABLE'})
                continue
            _observe(state, tenant, gateway_id, charge, current, started_at=lookup_started, case_id=case['request_id'])
            snapshot = refund_snapshot(current, charge_command(charge))
            if prior is not None:
                results.append({'billing_id': charge.billing_id, 'state': (
                    'REFUND_DONE_ADJUSTMENT_PENDING' if snapshot['state'] == 'FULL_DONE' else
                    'PROVIDER_PENDING' if snapshot['state'] == 'PROVIDER_PENDING' else 'DISPATCH_UNCERTAIN')})
                continue  # Existing claim only GETs; never another POST, even if no refund appears.
            if snapshot['state'] != 'READY':
                results.append({'billing_id': charge.billing_id, 'state': (
                    'REFUND_DONE_ADJUSTMENT_PENDING' if snapshot['state'] == 'FULL_DONE' else snapshot['state'])})
                continue
            if not enabled:
                results.append({'billing_id': charge.billing_id, 'state': 'DISABLED'})
                continue
            if (current.billing_type not in {'PIX', 'CREDIT_CARD'}
                    or (current.source_status is not None and current.source_status not in {'CONFIRMED', 'RECEIVED'})):
                results.append({'billing_id': charge.billing_id, 'state': 'METHOD_REVIEW_REQUIRED'})
                continue
            def claim():
                _context(state, charge)
                fresh_case = state.idempotency.get(tenant, REQUEST_KEY)
                if fresh_case is None or fresh_case.result != case:
                    raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Pedido mudou antes do envio.', status_code=409)
                subscription = state.subscriptions[tenant]
                fresh = state.charges[gateway_id]
                if (refresh_trial_status(subscription, now=now).status is not SubscriptionStatus.CANCELED
                        or fresh.tenant_id != tenant or fresh.billing_id != charge.billing_id
                        or fresh.status.value != 'SETTLED' or fresh.amount != charge.amount
                        or fresh.gateway_refund_state in {'MISSING', 'INVALID', 'AMOUNT_CONFLICT', 'OBSERVATION_CONFLICT'}
                        or (fresh.payment_reconciliation_state in {'REVERSAL_PENDING', 'CANCELLATION_CONFLICT'}
                            and fresh.gateway_refund_state not in {'NO_COMPLETED_REFUND', 'PARTIAL_DONE'})
                        or (fresh.gateway_refund_amount is not None and fresh.gateway_refund_amount != snapshot['completed'])):
                    raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Recebimento ou ajuste mudou; não enviar.', status_code=409)
                state.audit.append(tenant_id=tenant, actor='billing-refund-worker', actor_kind='SYSTEM',
                    action='BILLING_GUARANTEE_REFUND_DISPATCH_CLAIMED', target=charge.billing_id,
                    details={'request_id': case['request_id'], 'amount': str(snapshot['remaining'])})
                return {'request_id': case['request_id'], 'gateway_charge_id': gateway_id,
                    'billing_id': charge.billing_id, 'amount': snapshot['remaining'],
                    'completed_before': snapshot['completed'], 'provider': charge.commercial_gateway_provider,
                    'mode': charge.commercial_gateway_mode, 'claimed_at': now}
            intent, replay = state.idempotency.execute(tenant, key, claim)
            if replay:
                results.append({'billing_id': charge.billing_id, 'state': 'DISPATCH_UNCERTAIN'})
                continue  # Another owner now holds it; the next run may only inspect.
            dispatch_started = datetime.now(timezone.utc)
            try:
                observed = state.billing_gateway.refund_charge(gateway_id, charge_command(charge), intent['amount'])
            except Exception:
                results.append({'billing_id': charge.billing_id, 'state': 'DISPATCH_UNCERTAIN'})
                continue
            _observe(state, tenant, gateway_id, charge, observed, started_at=dispatch_started, case_id=case['request_id'])
            after = refund_snapshot(observed, charge_command(charge))
            results.append({'billing_id': charge.billing_id, 'state': (
                'REFUND_DONE_ADJUSTMENT_PENDING' if after['state'] == 'FULL_DONE' else
                'PROVIDER_PENDING' if after['state'] == 'PROVIDER_PENDING' else 'DISPATCH_UNCERTAIN')})
        except ApiError as exc:
            results.append({'billing_id': charge.billing_id, 'state': 'REVIEW_REQUIRED', 'code': exc.code})
    for result in results:
        if result['state'] not in {'REFUND_DONE_ADJUSTMENT_PENDING', 'PROVIDER_PENDING'}:
            def review(result=result):
                state.audit.append(tenant_id=tenant, actor='billing-refund-worker', actor_kind='SYSTEM',
                    action='BILLING_GUARANTEE_REFUND_REVIEW_REQUIRED', target=result['billing_id'],
                    details={'state': result['state'], 'request_id': case['request_id']})
                return {'state': result['state'], 'checked_at': now}
            state.idempotency.execute(tenant, refund_review_key(case['request_id'], result['billing_id']), review)
    return {'state': 'PROCESSING', 'request_id': case['request_id'], 'items': results, 'excluded': excluded}
