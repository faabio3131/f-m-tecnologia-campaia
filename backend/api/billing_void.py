"""Withdraw a canceled, unpaid renewal before separating final delivered usage.

The original obligation, dispatch fence, invoice and usage journal are retained.
An uncertain DELETE is never repeated: later calls only inspect the known invoice.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json

from campaia_core.billing_settlement import charge_command
from campaia_core.payment_gateway import GatewayChargeStatus
from campaia_core.subscription import ChargeStatus, ChargePurpose, SubscriptionStatus, refresh_trial_status
from .billing_receipts import REVIEW_STATES, tenant_charges
from .errors import ApiError


def intent_key(billing_id):
    return 'billing-void-intent:' + billing_id


def result_key(billing_id):
    return 'billing-void-result:' + billing_id


def verified_void(state, tenant, billing_id):
    saved = state.idempotency.get(tenant, result_key(billing_id))
    if saved is None or saved.result['state'] != 'VOID':
        return False
    charge = next((c for _key, c in tenant_charges(state, tenant) if c.billing_id == billing_id), None)
    return charge is not None and charge.status is not ChargeStatus.SETTLED and charge.payment_reconciliation_state not in REVIEW_STATES


def withdrawal_quote(state, gateway_id, charge):
    if state.idempotency.get(charge.tenant_id, result_key(charge.billing_id)) is not None:
        return None
    sub = state.subscriptions.get(charge.tenant_id)
    if sub is None:
        return None
    sub = refresh_trial_status(sub)
    if sub.paid_cycle_schedule is None or sub.paid_cycle_schedule.lifecycle_id != charge.commercial_lifecycle_id:
        closed = state.idempotency.get(charge.tenant_id, 'billing-closure:' + (charge.commercial_lifecycle_id or ''))
        if closed is None:
            return None
        sub = closed.result
    schedule = sub.paid_cycle_schedule
    if (sub.status is not SubscriptionStatus.CANCELED or schedule is None
            or charge.commercial_lifecycle_id != schedule.lifecycle_id
            or charge.commercial_cycle_index != schedule.paid_through_index + 1
            or charge.purpose is ChargePurpose.FINAL_USAGE or charge.status is ChargeStatus.SETTLED
            or charge.payment_reconciliation_state in REVIEW_STATES
            or charge.commercial_gateway_provider != state.billing_gateway.provider
            or charge.commercial_gateway_mode != state.billing_gateway.mode.value
            or not callable(getattr(state.billing_gateway, 'void_charge', None))):
        return None
    return sha256(json.dumps([gateway_id, charge.billing_id, str(charge.amount),
        charge.commercial_lifecycle_id, charge.commercial_gateway_provider,
        charge.commercial_gateway_mode, 'CANCELED_UNPAID_RENEWAL']).encode()).hexdigest()


def withdrawal_observed_at(state, charge):
    saved = state.idempotency.get(charge.tenant_id, result_key(charge.billing_id))
    return saved.result['observed_at'] if saved is not None else None


def withdrawal_state(state, charge):
    saved = state.idempotency.get(charge.tenant_id, result_key(charge.billing_id))
    if saved is not None:
        return 'VOID' if verified_void(state, charge.tenant_id, charge.billing_id) else 'REVIEW'
    return 'REQUESTED' if state.idempotency.get(charge.tenant_id, intent_key(charge.billing_id)) is not None else None


def withdraw_unpaid_renewal(state, fixture, gateway_id, key, body):
    tenant = fixture.tenant_id
    def owned():
        charge = state.charges.get(gateway_id)
        if charge is None or charge.tenant_id != tenant:
            raise ApiError('NOT_FOUND', 'Cobrança indisponível.', status_code=404)
        return charge
    charge = owned()
    context = sha256(json.dumps([fixture.user_id, fixture.business_unit_id, gateway_id, body], sort_keys=True).encode()).hexdigest()
    http_key = 'http:billing-void:' + key
    def check_context(record):
        if record['context'] != context:
            raise ApiError('IDEMPOTENCY_CONFLICT', 'A chave identifica outra retirada ou contexto.', status_code=409)
    completed = state.idempotency.get(tenant, http_key)
    if completed is not None:
        check_context(completed.result)
        return completed.result['response']
    if body.get('accept') is not True:
        raise ApiError('VALIDATION_FAILED', 'Confirme a revisão antes de retirar a cobrança.', status_code=422)
    def prepare():
        fresh = owned()
        prior_intent = state.idempotency.get(tenant, intent_key(fresh.billing_id))
        if verified_void(state, tenant, fresh.billing_id) and prior_intent is not None:
            intent = prior_intent.result
            if intent['gateway_id'] == gateway_id and intent['fingerprint'] == body.get('fingerprint'):
                return {'context': context, 'intent': intent}
        fingerprint = withdrawal_quote(state, gateway_id, fresh)
        if fingerprint is None or fingerprint != body.get('fingerprint'):
            raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Retirada indisponível ou condições alteradas; revise o histórico.', status_code=409)
        intent, replay = state.idempotency.execute(tenant, intent_key(fresh.billing_id),
            lambda: {'gateway_id': gateway_id, 'charge': fresh, 'fingerprint': fingerprint})
        if intent['gateway_id'] != gateway_id or intent['fingerprint'] != fingerprint:
            raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Outra retirada já está vinculada à obrigação.', status_code=409)
        if not replay:
            state.audit.append(tenant_id=tenant, actor=fixture.user_id,
                action='BILLING_UNPAID_RENEWAL_WITHDRAWAL_REQUESTED', target=fresh.billing_id)
        return {'context': context, 'intent': intent}
    request, _ = state.idempotency.execute(tenant, 'billing-void-request:' + key, prepare)
    check_context(request)
    intent = request['intent']; frozen = intent['charge']
    def require_gateway():
        if (frozen.commercial_gateway_provider != state.billing_gateway.provider
                or frozen.commercial_gateway_mode != state.billing_gateway.mode.value):
            raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Consulte no ambiente original da obrigação.', status_code=409)
    def claim():
        require_gateway()
        if withdrawal_quote(state, gateway_id, owned()) != intent['fingerprint']:
            raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Contratação ou recebimento mudou; não retirar.', status_code=409)
        return {'claimed_at': datetime.now(timezone.utc)}
    _claim, replay = state.idempotency.execute(tenant, 'billing-void-dispatch:' + frozen.billing_id, claim)
    require_gateway()
    saved = state.idempotency.get(tenant, result_key(frozen.billing_id))
    if saved is not None:
        proof = saved.result
    else:
        try:
            # The committed fence survives timeout/restart. Absence/404 is not deletion proof.
            operation = state.billing_gateway.inspect_charge if replay else state.billing_gateway.void_charge
            observed = operation(gateway_id, charge_command(frozen))
        except Exception as exc:
            raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Retirada não confirmada. Nova tentativa apenas consultará a cobrança; nenhuma nova exclusão será enviada.', status_code=503) from exc
        def persist():
            fresh = owned()
            if (observed.gateway_charge_id != gateway_id or observed.provider != frozen.commercial_gateway_provider
                    or observed.mode.value != frozen.commercial_gateway_mode or observed.deleted is not True
                    or observed.status not in {GatewayChargeStatus.PENDING, GatewayChargeStatus.OVERDUE}
                    or (observed.source_status is not None and observed.source_status not in {'PENDING', 'OVERDUE'})
                    or observed.observed_amount != frozen.amount or fresh.status is ChargeStatus.SETTLED
                    or fresh.payment_reconciliation_state in REVIEW_STATES):
                raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Consulta não comprova retirada de cobrança não paga; concilie sem separar o consumo.', status_code=503)
            proof = {'state': 'VOID', 'billing_id': frozen.billing_id, 'gateway_charge_id': gateway_id,
                'provider': observed.provider, 'mode': observed.mode.value, 'amount': str(frozen.amount),
                'observed_at': datetime.now(timezone.utc).isoformat()}
            state.audit.append(tenant_id=tenant, actor=fixture.user_id,
                action='BILLING_UNPAID_RENEWAL_WITHDRAWAL_CONFIRMED', target=frozen.billing_id,
                details={'gateway_charge_id': gateway_id, 'amount': str(frozen.amount)})
            return proof
        proof, _ = state.idempotency.execute(tenant, result_key(frozen.billing_id), persist)
    recorded, _ = state.idempotency.execute(tenant, http_key, lambda: {'context': context, 'response': proof})
    check_context(recorded)
    return recorded['response']
