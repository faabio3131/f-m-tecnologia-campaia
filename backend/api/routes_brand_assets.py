from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from hashlib import sha256

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from campaia_core.asset_images import AssetImageError, normalize_asset_image
from campaia_core.asset_storage import AssetStorageError, MAX_ASSET_BYTES
from campaia_core.permissions import Permission
from .brand_assets import public_asset, stored
from .deps import require_idempotency_key
from .errors import ApiError
from .routes_brand import _authorize_brand, _owned_profile


def _owned(request, permission):
    fixture, state = _authorize_brand(request, permission)
    profile = request.path_params["brandProfileId"]
    _owned_profile(state, fixture.tenant_id, profile)
    return fixture, state, profile


def _available(state):
    if state.asset_store is None or state.asset_storage.mode == "DISABLED":
        raise ApiError("ASSET_STORAGE_UNAVAILABLE", "Os arquivos da marca estão indisponíveis no momento.", status_code=503)
    if state.asset_storage.mode == "SIMULATOR" and state.env not in ("test", "dev-local"):
        raise ApiError("ASSET_STORAGE_UNAVAILABLE", "Os arquivos da marca estão indisponíveis no momento.", status_code=503)
    return state.asset_store, state.asset_storage


def _asset(request, fixture, state, profile):
    if state.asset_store is None:
        raise ApiError("NOT_FOUND", "Arquivo indisponível.", status_code=404)
    return state.asset_store.get(fixture.tenant_id, profile, request.path_params["assetId"])


async def list_brand_assets(request: Request):
    fixture, state, profile = _owned(request, Permission.CAMPAIGN_VIEW)
    result = (state.asset_store.page(fixture.tenant_id, profile, request.query_params.get("cursor"))
              if state.asset_store else {"items": [], "next_cursor": None})
    storage = state.asset_storage
    result["capability"] = {
        "enabled": state.asset_store is not None and storage.mode != "DISABLED",
        "mode": storage.mode, "max_input_bytes": MAX_ASSET_BYTES,
        "max_active_bytes": storage.max_active_bytes,
        "used_bytes": state.asset_store.usage(fixture.tenant_id) if state.asset_store else 0,
    }
    return JSONResponse(result, headers={"Cache-Control": "private, no-store"})


async def upload_brand_asset(request: Request):
    fixture, state, profile = _owned(request, Permission.BRAND_MANAGE)
    key = require_idempotency_key(request)
    store, storage = _available(state)
    kind = request.query_params.get("kind")
    if kind not in ("LOGO", "REFERENCE"):
        raise ApiError("VALIDATION_FAILED", "Escolha logo ou imagem de referência.", status_code=422)
    if request.headers.get("Content-Encoding", "identity").lower() != "identity":
        raise ApiError("VALIDATION_FAILED", "Envie uma imagem sem compactação HTTP.", status_code=422)
    if request.headers.get("Content-Type", "").split(";", 1)[0].lower() not in (
            "application/octet-stream", "image/png", "image/jpeg", "image/webp"):
        raise ApiError("VALIDATION_FAILED", "Envie PNG, JPEG ou WebP.", status_code=422)
    length = request.headers.get("Content-Length")
    if length is not None and (not length.isascii() or not length.isdecimal() or int(length) > MAX_ASSET_BYTES):
        raise ApiError("ASSET_TOO_LARGE", "O arquivo deve ter até 5 MiB.", status_code=413)
    if not state.asset_rate_limiter.allow(fixture.tenant_id, now=datetime.now(timezone.utc)):
        raise ApiError("RATE_LIMITED", "Aguarde antes de enviar mais arquivos.", status_code=429)
    if not state.asset_upload_slots.acquire(blocking=False):
        raise ApiError("ASSET_BUSY", "Há outros arquivos em processamento. Tente novamente.", status_code=429)
    try:
        payload = bytearray()
        try:
            async with asyncio.timeout(15):
                async for chunk in request.stream():
                    if len(payload) + len(chunk) > MAX_ASSET_BYTES:
                        raise ApiError("ASSET_TOO_LARGE", "O arquivo deve ter até 5 MiB.", status_code=413)
                    payload.extend(chunk)
        except TimeoutError:
            raise ApiError("ASSET_TIMEOUT", "O envio da imagem excedeu o tempo disponível.", status_code=408) from None
        raw = bytes(payload)
        try:
            image = await run_in_threadpool(normalize_asset_image, raw)
        except AssetImageError as error:
            if error.code == "IMAGE_PROCESSING_UNAVAILABLE":
                raise ApiError(error.code, "Não foi possível processar a imagem agora.", status_code=503) from None
            raise ApiError("INVALID_IMAGE", "Envie uma imagem PNG, JPEG ou WebP estática e válida, com até 4 megapixels.", status_code=422) from None
        def execute():
            record, dispatch = store.reserve(fixture, profile, key, sha256(raw).hexdigest(), kind, image, storage)
            return store.upload(fixture.tenant_id, record, image, storage, dispatch)
        record = await run_in_threadpool(execute)
        return JSONResponse(public_asset(record), status_code=201 if record["status"] == "READY" else 202,
                            headers={"Cache-Control": "private, no-store"})
    finally:
        state.asset_upload_slots.release()


async def reconcile_brand_asset(request: Request):
    fixture, state, profile = _owned(request, Permission.BRAND_MANAGE)
    key = require_idempotency_key(request)
    record = _asset(request, fixture, state, profile)
    store, storage = _available(state)
    def execute():
        store.remember_intent(fixture, record, key, "RECONCILE")
        return store.reconcile(fixture.tenant_id, record, storage)
    current = await run_in_threadpool(execute)
    return JSONResponse(public_asset(current), headers={"Cache-Control": "private, no-store"})


async def delete_brand_asset(request: Request):
    fixture, state, profile = _owned(request, Permission.BRAND_MANAGE)
    key = require_idempotency_key(request)
    record = _asset(request, fixture, state, profile)
    store, storage = _available(state)
    current = await run_in_threadpool(store.delete, fixture, record, key, storage)
    return JSONResponse(public_asset(current), status_code=200 if current["status"] == "DELETED" else 202,
                        headers={"Cache-Control": "private, no-store"})


async def read_brand_asset(request: Request):
    fixture, state, profile = _owned(request, Permission.CAMPAIGN_VIEW)
    record = _asset(request, fixture, state, profile)
    if record["status"] != "READY":
        raise ApiError("NOT_FOUND", "Arquivo indisponível.", status_code=404)
    store, storage = _available(state)
    store._scope(record, storage)
    try:
        raw = await run_in_threadpool(storage.read, stored(record))
    except AssetStorageError:
        raise ApiError("ASSET_CONTENT_UNAVAILABLE", "Não foi possível conferir a imagem.", status_code=503) from None
    # Re-check tombstone after a concurrent delete; never return a known removed asset.
    if store.get(fixture.tenant_id, profile, record["asset_id"])["status"] != "READY":
        raise ApiError("NOT_FOUND", "Arquivo indisponível.", status_code=404)
    return Response(raw, media_type="image/png", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "Content-Disposition": f'inline; filename="{record["asset_id"]}.png"',
    })
