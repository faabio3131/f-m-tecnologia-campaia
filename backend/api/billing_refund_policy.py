"""Private guarantee scope and derived progress; never an instruction to move money."""
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json

from .billing_facts import FIRST_PAID_KEY, fact_key
from .billing_receipts import tenant_charges
from .billing_guarantee_scope import get_scope
from .errors import ApiError


def refund_intent_key(case_id, billing_id):
    digest = sha256(json.dumps([case_id, billing_id]).encode()).hexdigest()
    return 'billing-guarantee-refund:' + digest


def refund_review_key(case_id, billing_id):
    return refund_intent_key(case_id, billing_id).replace('billing-guarantee-refund:', 'billing-guarantee-refund-review:', 1)


def processing_key(case_id):
    return 'billing-guarantee-processing:' + case_id


def validate_case(state, tenant, case):
    try:
        start = datetime.fromisoformat(case['first_paid_at'])
        end = datetime.fromisoformat(case['deadline'])
        requested = datetime.fromisoformat(case['requested_at'])
        first = state.idempotency.get(tenant, FIRST_PAID_KEY)
        expected_id = 'campaia:guarantee:' + sha256((tenant + ':' + case['first_paid_at']).encode()).hexdigest()
        proof = {key: case[key] for key in ('first_paid_at', 'deadline', 'paid_amount', 'currency', 'items')}
        proof.update(request_id=None, requested_at=None)
        fingerprint = sha256(json.dumps(proof, sort_keys=True).encode()).hexdigest()
        if (case['state'] != 'REQUESTED' or case['request_id'] != expected_id or case['currency'] != 'BRL'
                or first is None or first.result.get('state') != 'KNOWN' or first.result['paid_at'] != start
                or start.tzinfo is None or end != start + timedelta(days=7)
                or not start <= requested <= end or case['fingerprint'] != fingerprint):
            raise ValueError('Invalid guarantee scope')
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError('BILLING_GUARANTEE_REVIEW_REQUIRED', 'Pedido ou primeira contratação exige conferência.', status_code=409) from exc
    return start, end, requested


def eligible_payments(state, tenant, case, *, at):
    start, end, requested = validate_case(state, tenant, case)
    if at < requested:
        raise ApiError('BILLING_GUARANTEE_REVIEW_REQUIRED', 'Relógio anterior ao recebimento do pedido.', status_code=409)
    scope = get_scope(state, tenant, case)
    eligible = []
    excluded = []
    seen = set()
    for gateway_id, charge in tenant_charges(state, tenant):
        if scope is not None and charge.billing_id not in scope['billing_ids']:
            if charge.status.value == 'SETTLED':
                excluded.append({'billing_id': charge.billing_id, 'state': 'OUTSIDE_ACCEPTED_REQUEST'})
            continue
        if charge.status.value != 'SETTLED':
            continue
        stored = state.idempotency.get(tenant, fact_key(charge.billing_id))
        if (stored is None or stored.result['gateway_charge_id'] != gateway_id or charge.billing_id in seen):
            raise ApiError('BILLING_GUARANTEE_REVIEW_REQUIRED', 'Pagamento sem prova única da obrigação.', status_code=409)
        seen.add(charge.billing_id)
        fact = stored.result['fact']
        if fact['amount'] != charge.amount or fact['currency'] != 'BRL' or charge.commercial_lifecycle_id is None:
            raise ApiError('BILLING_GUARANTEE_REVIEW_REQUIRED', 'Termos pagos divergem da obrigação.', status_code=409)
        if start <= fact['settled_at'] <= min(at, end):
            eligible.append((gateway_id, charge, stored.result))
        else:
            excluded.append({'billing_id': charge.billing_id, 'state': 'OUTSIDE_COMMERCIAL_WINDOW'})
    covered = {charge.billing_id: (gateway_id, charge) for gateway_id, charge, _ in eligible}
    for item in case['items']:
        match = covered.get(item['billing_id'])
        if match is None or match[0] != item['gateway_charge_id'] or match[1].amount != Decimal(item['amount']):
            raise ApiError('BILLING_GUARANTEE_REVIEW_REQUIRED', 'Pagamento considerado no pedido perdeu a prova correspondente.', status_code=409)
    eligible.sort(key=lambda item: (item[2]['fact']['settled_at'], item[1].billing_id))
    return eligible, excluded


def refund_progress(state, tenant, case, *, at):
    eligible, _excluded = eligible_payments(state, tenant, case, at=at)
    result = []
    for gateway_id, charge, _record in eligible:
        intent = state.idempotency.get(tenant, refund_intent_key(case['request_id'], charge.billing_id))
        observed = charge.gateway_refund_state
        if observed == 'FULL_DONE' and charge.gateway_refund_amount == charge.amount:
            status = 'REFUND_DONE_ADJUSTMENT_PENDING'
        elif observed == 'PROCESSING':
            status = 'PROVIDER_PENDING'
        elif observed in {'INVALID', 'MISSING', 'AMOUNT_CONFLICT', 'OBSERVATION_CONFLICT'}:
            status = 'REVIEW_REQUIRED'
        elif intent is not None:
            status = 'DISPATCH_UNCERTAIN'
        elif state.idempotency.get(tenant, refund_review_key(case['request_id'], charge.billing_id)) is not None:
            status = 'REVIEW_REQUIRED'
        else:
            status = 'NOT_DISPATCHED'
        result.append({'billing_id': charge.billing_id, 'gateway_charge_id': gateway_id,
            'paid_amount': str(charge.amount), 'completed_amount': (
                str(charge.gateway_refund_amount) if charge.gateway_refund_amount is not None else None),
            'state': status, 'mode': charge.commercial_gateway_mode})
    return result
