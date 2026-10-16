"""Finance inbox API: tenant authority and individual reading, never delivery by email."""
from starlette.responses import JSONResponse
from campaia_core.permissions import Permission
from .routes_billing import _authorize_billing
from .deps import require_idempotency_key
from .helpers import parse_body
from .models import ApiModel
from .billing_notices import serialize_notice, mark_notice_read
from .errors import ApiError


async def list_billing_notices(request):
    fixture, state = _authorize_billing(request, Permission.BILLING_VIEW)
    rows = sorted(state.billing_notices.list(fixture.tenant_id),
                  key=lambda row: (row['created_at'], row['id']), reverse=True)
    start = 0
    cursor = request.query_params.get('cursor')
    if cursor:
        identities = [row['id'] for row in rows]
        if cursor not in identities:
            raise ApiError('VALIDATION_FAILED', 'Cursor inválido ou indisponível.', status_code=422)
        start = identities.index(cursor) + 1
    page = rows[start:start + 50]
    return JSONResponse({'items': [serialize_notice(state, fixture.tenant_id, fixture.user_id, row) for row in page],
        'next_cursor': page[-1]['id'] if start + 50 < len(rows) else None})


async def read_billing_notice(request):
    fixture, state = _authorize_billing(request, Permission.BILLING_VIEW)
    key = require_idempotency_key(request)
    if await request.body():
        await parse_body(request, ApiModel)
    return JSONResponse(mark_notice_read(state, fixture, request.path_params['noticeId'], key))
