"""Commercial closure backed by full provider refund proof, never a fiscal credit note."""
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json

from .billing_guarantee_scope import REQUEST_KEY, get_scope, ensure_scope
from .billing_refund_policy import eligible_payments
from .errors import ApiError


def adjustment_key(billing_id):
    return 'billing-guarantee-adjustment:' + billing_id


def _paid_coverage(state, tenant, case):
    scope = get_scope(state, tenant, case)
    if scope is None:
        raise ApiError('BILLING_GUARANTEE_REVIEW_REQUIRED', 'Escopo do pedido ainda não comprovado.', status_code=409)
    end = datetime.fromisoformat(case['deadline'])
    rows, _excluded = eligible_payments(state, tenant, case, at=end)
    proof = {'request_id': case['request_id'], 'scope_billing_ids': list(scope['billing_ids']),
        'payments': [{'billing_id': charge.billing_id, 'gateway_charge_id': gateway_id,
            'amount': str(charge.amount), 'paid_at': record['fact']['settled_at'].isoformat()}
            for gateway_id, charge, record in rows]}
    fingerprint = sha256(json.dumps(proof, sort_keys=True).encode()).hexdigest()
    return rows, fingerprint


def _full_refund(charge):
    return (charge.gateway_refund_state == 'FULL_DONE' and charge.gateway_refund_amount == charge.amount
        and charge.gateway_chargeback_status is None
        and charge.payment_reconciliation_state not in {
            'AMOUNT_MISMATCH', 'TERMS_MISMATCH', 'STATUS_MISMATCH', 'CANCELLATION_CONFLICT'})


def current_resolution(state, tenant, case):
    try:
        rows, fingerprint = _paid_coverage(state, tenant, case)
    except ApiError:
        return None
    saved = state.idempotency.get(tenant, 'billing-guarantee-resolution:' + fingerprint)
    if (saved is None or saved.result.get('state') != 'RESOLVED'
            or saved.result.get('request_id') != case['request_id'] or not rows
            or not all(_full_refund(charge) for _gateway_id, charge, _record in rows)):
        return None
    return saved.result


def fee_was_adjusted(state, tenant, charge, gateway_id):
    saved = state.idempotency.get(tenant, adjustment_key(charge.billing_id))
    if saved is None:
        return False
    proof = saved.result
    return (proof.get('state') == 'APPLIED' and proof.get('gateway_charge_id') == gateway_id
        and proof.get('amount') == charge.amount and proof.get('purpose') == 'FINAL_USAGE'
        and charge.purpose.value == 'FINAL_USAGE' and _full_refund(charge))


def finalize_guarantee(state, tenant, *, execute=False, at=None):
    now = at or datetime.now(timezone.utc)
    stored = state.idempotency.get(tenant, REQUEST_KEY)
    if stored is None:
        return {'state': 'UNAVAILABLE'}
    case = stored.result
    if execute:
        try:
            ensure_scope(state, tenant, case)
        except ApiError as exc:
            return {'state': 'REVIEW_REQUIRED', 'code': exc.code}
    try:
        rows, fingerprint = _paid_coverage(state, tenant, case)
    except ApiError as exc:
        return {'state': 'REVIEW_REQUIRED', 'code': exc.code}
    if not rows or not all(_full_refund(charge) for _gateway_id, charge, _record in rows):
        return {'state': 'REFUND_PROOF_REQUIRED', 'request_id': case['request_id']}
    previous = current_resolution(state, tenant, case)
    if previous is not None:
        return {**previous, 'state': 'FINANCIALLY_RESOLVED'}
    if not execute:
        return {'state': 'DRY_RUN', 'request_id': case['request_id'],
                'billing_ids': [charge.billing_id for _gateway_id, charge, _record in rows]}
    def resolve():
        fresh_case = state.idempotency.get(tenant, REQUEST_KEY)
        if fresh_case is None or fresh_case.result != case:
            raise ApiError('BILLING_GUARANTEE_REVIEW_REQUIRED', 'Pedido mudou antes do ajuste.', status_code=409)
        fresh_rows, fresh_fingerprint = _paid_coverage(state, tenant, case)
        if fresh_fingerprint != fingerprint or not all(_full_refund(charge) for _gid, charge, _record in fresh_rows):
            raise ApiError('BILLING_GUARANTEE_REVIEW_REQUIRED', 'Prova de devolução mudou antes do ajuste.', status_code=409)
        scope = get_scope(state, tenant, case)
        for lifecycle in scope['lifecycle_ids']:
            closed = state.idempotency.get(tenant, 'billing-closure:' + lifecycle)
            if closed is None or closed.result.status.value != 'CANCELED':
                raise ApiError('BILLING_GUARANTEE_REVIEW_REQUIRED', 'Contratação coberta sem encerramento comprovado.', status_code=409)
        for gateway_id, charge, _record in fresh_rows:
            adjustment = {'state': 'APPLIED', 'request_id': case['request_id'],
                'billing_id': charge.billing_id, 'gateway_charge_id': gateway_id,
                'amount': charge.amount, 'currency': charge.currency, 'purpose': charge.purpose.value,
                'lifecycle_id': charge.commercial_lifecycle_id, 'coverage_fingerprint': fingerprint,
                'recorded_at': now, 'fiscal_adjustment_state': 'PENDING_CAPABILITY'}
            saved, _ = state.idempotency.execute(tenant, adjustment_key(charge.billing_id), lambda adjustment=adjustment: adjustment)
            if (saved['request_id'] != case['request_id'] or saved['amount'] != charge.amount
                    or saved['gateway_charge_id'] != gateway_id):
                raise ApiError('BILLING_GUARANTEE_REVIEW_REQUIRED', 'Outro ajuste já está vinculado à obrigação.', status_code=409)
            state.charges[gateway_id] = replace(charge, payment_reconciliation_state='GUARANTEE_REFUNDED')
        result = {'state': 'RESOLVED', 'request_id': case['request_id'],
            'coverage_fingerprint': fingerprint, 'resolved_at': now.isoformat(),
            'billing_ids': [charge.billing_id for _gid, charge, _record in fresh_rows],
            'fiscal_adjustment_state': 'PENDING_CAPABILITY'}
        state.audit.append(tenant_id=tenant, actor='billing-guarantee-worker', actor_kind='SYSTEM',
            action='BILLING_GUARANTEE_FINANCIALLY_RESOLVED', target=case['request_id'],
            details={'billing_ids': result['billing_ids'], 'coverage_fingerprint': fingerprint,
                     'fiscal_adjustment_state': 'PENDING_CAPABILITY', 'new_credit_grant': False})
        return result
    try:
        result, _ = state.idempotency.execute(tenant, 'billing-guarantee-resolution:' + fingerprint, resolve)
    except ApiError as exc:
        return {'state': 'REVIEW_REQUIRED', 'code': exc.code}
    return {**result, 'state': 'FINANCIALLY_RESOLVED'}
