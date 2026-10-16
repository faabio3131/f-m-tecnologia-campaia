"""Legacy strategy execution still needs a committed claim before external AI cost."""
from hashlib import sha256
import json
from .errors import ApiError


def execute_unmetered(state, fixture, key, campaign_id, snapshot, generate, deliver, *,
                      namespace=None, request_identity=None):
    tenant = fixture.tenant_id
    identity = [fixture.user_id, fixture.business_unit_id, campaign_id]
    if namespace is not None:
        identity.extend([namespace, request_identity])
    fingerprint = sha256(json.dumps(identity, sort_keys=True, default=str).encode()).hexdigest()
    # Preserve historical strategy keys/fingerprints exactly; new actions are separate scopes.
    completed_key = ('http:regenerate_plan:' if namespace is None else 'http:ai-proposal:' + namespace + ':') + key
    claim_key = ('ai-unmetered-dispatch:' if namespace is None else 'ai-proposal-dispatch:' + namespace + ':') + key
    failure_key = ('ai-unmetered-failure:' if namespace is None else 'ai-proposal-failure:' + namespace + ':') + key
    previous = state.idempotency.get(tenant, completed_key)
    prior_claim = state.idempotency.get(tenant, claim_key)
    if previous is not None and prior_claim is None and namespace is not None:
        raise ApiError('AI_OPERATION_PENDING', 'Entrega sem claim correspondente exige conferência.', status_code=503)
    if previous is not None and prior_claim is None:
        if previous.result.get('campaign_id') != campaign_id:
            raise ApiError('IDEMPOTENCY_CONFLICT', 'A chave identifica outra campanha.', status_code=409)
        return previous.result
    def claim():
        brief_hash, version = snapshot()
        return {'fingerprint': fingerprint, 'brief_hash': brief_hash, 'version': version}
    claimed, replay = state.idempotency.execute(tenant, claim_key, claim)
    if claimed['fingerprint'] != fingerprint:
        raise ApiError('IDEMPOTENCY_CONFLICT', 'A chave identifica outra operação ou contexto.', status_code=409)
    previous = state.idempotency.get(tenant, completed_key)
    if previous is not None:
        return previous.result
    if replay:
        known = state.idempotency.get(tenant, failure_key)
        if known is not None:
            raise ApiError('AI_OPERATION_FAILED', 'Geração anterior sem entrega válida; revise antes de uma nova solicitação.', status_code=422)
        raise ApiError('AI_OPERATION_PENDING', 'Resultado externo pendente de conferência; execução não repetida.', status_code=503)
    try:
        generated = generate()
        def save():
            brief_hash, version = snapshot()
            if brief_hash != claimed['brief_hash'] or version != claimed['version']:
                raise ApiError('AI_INPUT_CHANGED', 'A campanha mudou durante a geração; saída descartada.', status_code=409)
            return deliver(generated)
        result, _ = state.idempotency.execute(tenant, completed_key, save)
        return result
    except ApiError as exc:
        if exc.code == 'AI_OPERATION_PENDING':
            raise
        state.idempotency.execute(tenant, failure_key, lambda: {'known_no_delivery': True})
        raise
    except Exception as exc:
        raise ApiError('AI_OPERATION_PENDING', 'Resultado externo incerto; execução não será repetida automaticamente.', status_code=503) from exc
