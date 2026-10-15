"""Durable V1 obligation and dispatch fence using the existing F3 store.

Commit the financial snapshot before a provider can observe it. A repeated/uncertain
dispatch may only LOOK UP the external reference; absence is not permission to POST.
There is deliberately no automatic expiry or reset of an uncertain financial claim.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json

from campaia_core.billing_settlement import charge_command
from campaia_core.subscription import SubscriptionStatus, refresh_trial_status
from .errors import ApiError


def obligation_key(billing_id):
    return 'billing-obligation:' + billing_id


def execute_invoice(state, fixture, http_key, body, prepare, dispatch, persist):
    tenant = fixture.tenant_id
    context = sha256(json.dumps([fixture.user_id, fixture.business_unit_id, body],
                               sort_keys=True, default=str).encode()).hexdigest()
    result_key = 'http:billing_charge_create:' + http_key
    # A completed response from the previous implementation has no request claim.
    # Recover that tenant-scoped response without preparing/issuing another obligation.
    previous = state.idempotency.get(tenant, result_key)
    request_claim = state.idempotency.get(tenant, 'billing-request:' + http_key)
    if previous is not None and request_claim is None:
        return previous.result

    def freeze():
        charge = prepare()
        frozen, replayed = state.idempotency.execute(tenant, obligation_key(charge.billing_id), lambda: charge)
        if not replayed:
            state.audit.append(tenant_id=tenant, actor=fixture.user_id,
                               action='BILLING_OBLIGATION_FROZEN', target=frozen.billing_id)
        return {'context': context, 'charge': frozen}

    request, _ = state.idempotency.execute(tenant, 'billing-request:' + http_key, freeze)
    if request['context'] != context:
        raise ApiError('IDEMPOTENCY_CONFLICT', 'A chave já identifica outra solicitação ou contexto.', status_code=409)
    previous = state.idempotency.get(tenant, result_key)
    if previous is not None:
        return previous.result
    charge = request['charge']

    def claim():
        current = refresh_trial_status(state.subscriptions[tenant])
        if (current.paid_cycle_schedule is None
                or current.paid_cycle_schedule.lifecycle_id != charge.commercial_lifecycle_id
                or current.status is SubscriptionStatus.CANCELED
                or current.cancel_at_period_end is not None):
            raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Contratação mudou após o fechamento; concilie antes de emitir.', status_code=409)
        state.audit.append(tenant_id=tenant, actor=fixture.user_id,
                           action='BILLING_DISPATCH_CLAIMED', target=charge.billing_id)
        return {'claimed_at': datetime.now(timezone.utc)}

    _, replayed = state.idempotency.execute(tenant, 'billing-dispatch:' + charge.billing_id, claim)
    provider_key = 'billing-provider-result:' + charge.billing_id
    observed = state.idempotency.get(tenant, provider_key)
    if observed is not None:
        result = observed.result
    else:
        try:
            if replayed:
                lookup = getattr(state.billing_gateway, 'recover_charge', None)
                result = lookup(charge_command(charge)) if lookup is not None else None
                if result is None:
                    raise ApiError('BILLING_DISPATCH_PENDING', 'Emissão anterior incerta. Nenhuma nova cobrança foi enviada; aguarde conciliação.', status_code=503)
            else:
                # Both obligation and dispatch claim are already committed here.
                result = dispatch(charge, state.billing_gateway)
        except ApiError:
            raise
        except Exception as exc:
            # Even a timeout can follow a successful external POST. Never reset this
            # claim or use another HTTP key to authorize a second external creation.
            raise ApiError('BILLING_DISPATCH_PENDING', 'Resultado de emissão não confirmado; consulte a mesma solicitação para conciliar.', status_code=503) from exc
        result, _ = state.idempotency.execute(tenant, provider_key, lambda: result)

    if result.observed_amount != charge.amount:
        raise ApiError('BILLING_RECONCILIATION_REQUIRED', 'Valor externo diverge da obrigação; concilie antes de ativar.', status_code=503)
    response, _ = state.idempotency.execute(tenant, result_key, lambda: persist(charge, result))
    return response
