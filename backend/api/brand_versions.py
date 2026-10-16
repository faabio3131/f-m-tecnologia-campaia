"""Immutable text revisions in the existing F3 store; no new financial/storage authority."""
from .errors import ApiError
from .helpers import serialize_brand_profile


def version_key(identity, version):
    return 'brand-profile-version:' + identity + ':' + str(version)


def freeze_version(state, profile, *, editor_id=None, recorded_at=None):
    snapshot = serialize_brand_profile(profile).model_dump(mode='json')
    result, _ = state.idempotency.execute(profile.tenant_id, version_key(profile.brand_profile_id, profile.version),
        lambda: {'profile': snapshot, 'editor_id': editor_id, 'recorded_at': recorded_at})
    if result['profile'] != snapshot:
        raise ApiError('BRAND_HISTORY_INCOMPLETE', 'O histórico diverge da versão atual; confira antes de alterar.', status_code=409)
    return snapshot


def version_page(state, profile, cursor=None):
    before = profile.version + 1
    if cursor is not None:
        if (not cursor.isascii() or not cursor.isdecimal() or len(cursor) > 20
                or not 1 <= int(cursor) <= profile.version):
            raise ApiError('VALIDATION_FAILED', 'Cursor de versões inválido.', status_code=422)
        before = int(cursor)
    versions = range(before - 1, max(0, before - 51), -1)
    items = []
    for version in versions:
        record = state.idempotency.get(profile.tenant_id, version_key(profile.brand_profile_id, version))
        if record is None:
            if profile.version == 1 and version == 1:
                items.append(serialize_brand_profile(profile).model_dump(mode='json'))
                continue
            raise ApiError('BRAND_HISTORY_INCOMPLETE', 'Uma versão histórica precisa de conferência.', status_code=503)
        items.append(record.result['profile'])
    return {'items': items, 'next_cursor': str(items[-1]['version']) if items and items[-1]['version'] > 1 else None}
