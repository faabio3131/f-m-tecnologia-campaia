"""One persisted dispatch claim, short DB transactions, no provider call under a lock.

Unknown external outcomes remain reserved. A replay only recovers the committed delivery;
it never silently redispatches the provider. Existing F3 idempotency stores both the claim
and the atomic delivery result, so no parallel job store or billing authority is introduced.
"""
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json

from campaia_core.credit_ledger import CreditLedgerError, CreditLimitExceeded
from campaia_core.subscription import entitlement_access_is_active, refresh_trial_status

from .billing_credits import cycle_snapshot
from .errors import ApiError


def commercial_subscription(state, tenant_id):
    sub = state.subscriptions.get(tenant_id)
    return refresh_trial_status(sub) if sub is not None and sub.plan.credit_policy is not None else None


def quote_action(state, tenant_id, action):
    sub = commercial_subscription(state, tenant_id)
    if sub is None:
        return {'mode': 'LEGACY', 'action': action, 'cycle_id': None, 'policy_version': None,
                'credits': None, 'extra_amount': None, 'included_available': None}
    at = datetime.now(timezone.utc)
    if not entitlement_access_is_active(sub, now=at) or state.credit_ledger is None:
        raise ApiError('BILLING_ACCESS_REQUIRED', 'É necessário trial ou ciclo pago vigente.', status_code=409)
    cycle = cycle_snapshot(sub, at=at)
    if cycle is None:
        raise ApiError('BILLING_USAGE_UNAVAILABLE', 'Franquia indisponível para esta operação.', status_code=503)
    try:
        balance = state.credit_ledger.balance(tenant_id, cycle.cycle_id)
        credits = dict(cycle.action_weights)[action]
    except (CreditLedgerError, KeyError) as exc:
        raise ApiError('BILLING_USAGE_UNAVAILABLE', 'Medição da ação indisponível.', status_code=503) from exc
    extra_units = max(credits - balance.included_available, 0)
    extra_amount = extra_units * cycle.extra_credit_price
    committed_extra = balance.extra_committed_amount + extra_amount
    # After anniversary, only the remaining previously-paid quota is usable.
    if (at >= cycle.ends_at and extra_units) or committed_extra > balance.extra_cap:
        raise ApiError('QUOTA_EXHAUSTED', 'A operação completa não cabe na franquia e no teto autorizado.', status_code=409)
    return {'mode': 'COMMERCIAL', 'action': action, 'cycle_id': cycle.cycle_id,
            'policy_version': cycle.policy_version, 'credits': credits,
            'extra_amount': str(extra_amount), 'included_available': balance.included_available}


def execute_metered(state, fixture, key, request_identity, confirmation, action, generate, deliver):
    tenant = fixture.tenant_id
    fingerprint = sha256(json.dumps([fixture.user_id, fixture.business_unit_id, request_identity,
                                      confirmation], sort_keys=True, default=str).encode()).hexdigest()
    operation = sha256((tenant + ':' + key).encode()).hexdigest()

    def claim():
        quoted = quote_action(state, tenant, action)
        if (confirmation is None or quoted['mode'] != 'COMMERCIAL'
                or any(confirmation.get(field) != quoted[field]
                       for field in ('cycle_id', 'policy_version', 'credits'))
                or Decimal(str(confirmation.get('extra_amount', '-1'))) < Decimal(quoted['extra_amount'])):
            raise ApiError('CREDIT_QUOTE_CHANGED', 'Revise o débito e confirme novamente antes de executar.', status_code=409)
        try:
            reserved = state.credit_ledger.decide(tenant, 'reserve', cycle_id=quoted['cycle_id'],
                                                 operation_id=operation, action=action, at=datetime.now(timezone.utc))
            if reserved.replayed:
                raise ApiError('AI_OPERATION_PENDING', 'Reserva prévia exige reconciliação; execução não repetida.', status_code=503)
        except CreditLimitExceeded as exc:
            raise ApiError('QUOTA_EXHAUSTED', 'Franquia/teto insuficiente para a operação completa.', status_code=409) from exc
        state.audit.append(tenant_id=tenant, actor=fixture.user_id, action='AI_CREDITS_RESERVED', target=operation)
        return {'fingerprint': fingerprint, 'operation_id': operation, 'cycle_id': quoted['cycle_id']}

    claimed, replayed = state.idempotency.execute(tenant, 'ai-dispatch:' + key, claim)
    if claimed['fingerprint'] != fingerprint:
        raise ApiError('IDEMPOTENCY_CONFLICT', 'A chave já identifica outra operação ou contexto.', status_code=409)
    existing = state.idempotency.get(tenant, key)
    if existing is not None:
        return existing.result
    if replayed:
        entries = state.credit_ledger.entries(tenant)
        latest = next(e for e in reversed(entries) if e.operation_id == operation)
        if latest.kind == 'RELEASE':
            raise ApiError('AI_OPERATION_FAILED', 'A operação falhou sem débito. Revise antes de solicitar uma nova geração.', status_code=422)
        raise ApiError('AI_OPERATION_PENDING', 'Entrega pendente de conclusão/reconciliação. Reutilize esta confirmação para consultar o resultado.', status_code=503)

    def release():
        state.credit_ledger.decide(tenant, 'finish', operation_id=operation, kind='RELEASE',
                                  reference='known-failure:' + operation, at=datetime.now(timezone.utc))
        state.audit.append(tenant_id=tenant, actor=fixture.user_id, action='AI_CREDITS_RELEASED', target=operation)
        return {'released': True}

    try:
        # The dispatch claim and reservation have COMMITTED before this callback.
        generated = generate()
        def settle_delivery():
            current = commercial_subscription(state, tenant)
            at = datetime.now(timezone.utc)
            cycle = cycle_snapshot(current, at=at) if current is not None else None
            if (current is None or not entitlement_access_is_active(current, now=at)
                    or cycle is None or cycle.cycle_id != claimed['cycle_id']):
                raise ApiError('AI_SUBSCRIPTION_CHANGED', 'A contratação encerrou ou mudou durante a geração; entrega descartada sem débito.', status_code=409)
            result = deliver(generated)
            state.credit_ledger.decide(tenant, 'finish', operation_id=operation, kind='SETTLE',
                                      reference='delivery:' + operation, at=datetime.now(timezone.utc))
            state.audit.append(tenant_id=tenant, actor=fixture.user_id, action='AI_CREDITS_SETTLED', target=operation)
            return result
        result, _ = state.idempotency.execute(tenant, key, settle_delivery)
        return result
    except ApiError as exc:
        if exc.code == 'AI_OPERATION_PENDING':
            raise
        # Known invalid output/policy rejection or rejected stale delivery: no valid
        # output became available. Provider cost remains internal regardless.
        state.idempotency.execute(tenant, 'ai-release:' + key, release)
        raise
    except Exception as exc:
        # Failure may have happened after external execution. Keep evidence and credit
        # reservation; a second request must not call the provider automatically.
        raise ApiError('AI_OPERATION_PENDING', 'Resultado externo incerto; reserva mantida para reconciliação.', status_code=503) from exc
