"""Bounded JSON parsing before model validation, shared by protected write endpoints."""
import asyncio
from pydantic import ValidationError
from .errors import ApiError


async def parse_bounded_body(request, model, *, max_bytes=256 * 1024):
    limit = max_bytes
    if request.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise ApiError("VALIDATION_FAILED", "Envie os campos em JSON.", status_code=422)
    length = request.headers.get("Content-Length")
    if request.headers.get("Content-Encoding", "identity").lower() != "identity":
        raise ApiError("VALIDATION_FAILED", "Envie os campos em JSON sem compactação HTTP.", status_code=422)
    if length is not None:
        normalized = length.lstrip("0") or "0"
        if (not length.isascii() or not length.isdecimal() or len(normalized) > len(str(limit))
                or int(normalized) > limit):
            raise ApiError("REQUEST_TOO_LARGE", "O pedido excede o tamanho permitido.", status_code=413)
    raw = bytearray()
    try:
        async with asyncio.timeout(15):
            async for chunk in request.stream():
                if len(raw) + len(chunk) > limit:
                    raise ApiError("REQUEST_TOO_LARGE", "O pedido excede o tamanho permitido.", status_code=413)
                raw.extend(chunk)
    except TimeoutError:
        raise ApiError("REQUEST_TIMEOUT", "O envio do pedido excedeu o tempo disponível.", status_code=408) from None
    try:
        return model.model_validate_json(bytes(raw))
    except ValidationError:
        raise ApiError("VALIDATION_FAILED", "Confira os campos do pedido.", status_code=422) from None
