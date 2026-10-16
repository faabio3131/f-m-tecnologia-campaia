"""Legacy strategy execution still needs a committed claim before external AI cost."""
from hashlib import sha256
import json
from .errors import ApiError


def execute_unmetered(state, fixture, key, campaign_id, snapshot, generate, deliver):
    tenant = fixture.tenant_id
    fingerprint = sha256(json.dumps([fixture.user_id, fixture.business_unit_id, campaign_id]).encode()).hexdigest()
    completed_key = 'http:regenerate_plan:' + key
    claim_key = 'ai-unmetered-dispatch:' + key
    previous = state.idempotency.get(tenant, completed_key)
    prior_claim = state.idempotency.get(tenant, claim_key)
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
        known = state.idempotency.get(tenant, 'ai-unmetered-failure:' + key)
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
        state.idempotency.execute(tenant, 'ai-unmetered-failure:' + key, lambda: {'known_no_delivery': True})
        raise
    except Exception as exc:
        raise ApiError('AI_OPERATION_PENDING', 'Resultado externo incerto; execução não será repetida automaticamente.', status_code=503) from exc
