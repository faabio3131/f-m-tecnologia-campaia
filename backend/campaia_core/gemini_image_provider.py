"""Opt-in, bounded text-to-image transport. No routes, storage or commercial activation.

Primary protocol: ai.google.dev/gemini-api/docs/image-generation and interactions-overview,
verified 2026-10-16. Images travel only as inline bytes from model_output steps. SDK
output_image is a convenience property, not a wire field. No history/search/URL fetching.
Tariffs are explicit conservative estimates, never an invoice or certified margin.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import json
import math
import os
import re
from threading import BoundedSemaphore
import time
from typing import ClassVar

import httpx

from .ai_gateway import (AIRequest, AITask, CostObservation, CredentialInPayload,
                         ModerationBlocked, OutputSchema, ProviderError,
                         ProviderOutputInvalid, ProviderResponse, ProviderTimeout,
                         assert_no_credentials)
from .asset_images import AssetImageError, normalize_asset_image
from .asset_storage import MAX_ASSET_BYTES, PNG_SIGNATURE
from .sanitizer import sanitize

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_CONTEXT_BYTES = 64 * 1024
IMAGE_SCHEMA = OutputSchema("generated-image", frozenset({"mime_type", "data_base64", "width", "height"}),
    {"mime_type": str, "data_base64": str, "width": int, "height": int})


def _not_sent():
    return CostObservation("NOT_DISPATCHED", Decimal("0"), dispatched=False)


class GeminiImageConfigError(ProviderError):
    pass


def _metadata(value, *, model=False):
    if (not isinstance(value, str) or not 1 <= len(value) <= 160
            or not re.fullmatch(r"[a-z][a-z0-9._-]*" if model else r"[A-Za-z0-9][A-Za-z0-9._:/-]*", value)):
        raise GeminiImageConfigError("Configuração de imagem inválida.", cost_observation=_not_sent())
    try:
        value.encode("utf-8")
        assert_no_credentials(value)
    except (UnicodeError, CredentialInPayload):
        raise GeminiImageConfigError("Configuração de imagem inválida.", cost_observation=_not_sent()) from None
    return value


@dataclass(frozen=True, slots=True)
class GeminiImageConfig:
    enabled: bool = False
    api_key: str | None = field(default=None, repr=False)
    model: str | None = None
    input_usd_per_million: Decimal | None = None
    output_usd_per_million: Decimal | None = None
    pricing_reference: str | None = None

    def __post_init__(self):
        if type(self.enabled) is not bool:
            raise GeminiImageConfigError("Ativação de imagem inválida.", cost_observation=_not_sent())
        if self.api_key is not None and (not isinstance(self.api_key, str)
                or not re.fullmatch(r"[A-Za-z0-9._~-]{1,512}", self.api_key)):
            raise GeminiImageConfigError("Credencial de imagem inválida.", cost_observation=_not_sent())
        if self.model is not None:
            _metadata(self.model, model=True)
        if self.pricing_reference is not None:
            _metadata(self.pricing_reference)
        for value in (self.input_usd_per_million, self.output_usd_per_million):
            if value is not None and (not isinstance(value, Decimal) or not value.is_finite()
                                      or not Decimal("0") < value <= Decimal("1000000")):
                raise GeminiImageConfigError("Estimativa de imagem inválida.", cost_observation=_not_sent())
        if self.enabled and any(value is None for value in (
                self.api_key, self.model, self.input_usd_per_million,
                self.output_usd_per_million, self.pricing_reference)):
            raise GeminiImageConfigError("Ativação de imagem exige modelo, credencial e estimativas explícitas.",
                                         cost_observation=_not_sent())

    @classmethod
    def from_env(cls):
        flag = os.environ.get("GEMINI_IMAGE_ENABLED", "false").strip().lower()
        if flag not in ("true", "false"):
            raise GeminiImageConfigError("Ativação de imagem inválida.", cost_observation=_not_sent())
        if flag == "false":
            return cls()  # Do not even resolve an existing text-provider credential while disabled.
        try:
            return cls(enabled=True, api_key=os.environ.get("GEMINI_IMAGE_API_KEY"),
                model=os.environ.get("GEMINI_IMAGE_MODEL"),
                input_usd_per_million=Decimal(os.environ.get("GEMINI_IMAGE_INPUT_USD_PER_MILLION", "")),
                output_usd_per_million=Decimal(os.environ.get("GEMINI_IMAGE_OUTPUT_USD_PER_MILLION", "")),
                pricing_reference=os.environ.get("GEMINI_IMAGE_PRICING_REFERENCE"))
        except (ValueError, InvalidOperation):
            raise GeminiImageConfigError("Ativação de imagem incompleta.", cost_observation=_not_sent()) from None


@dataclass
class GeminiImageProvider:
    config: GeminiImageConfig = field(default_factory=GeminiImageConfig)
    transport: httpx.BaseTransport | None = field(default=None, repr=False)
    timeout_s: float = 30.0
    name: ClassVar[str] = "GEMINI_IMAGE"
    _client: httpx.Client | None = field(init=False, default=None, repr=False)
    _slot: BoundedSemaphore = field(default_factory=lambda: BoundedSemaphore(1), init=False, repr=False)

    def __post_init__(self):
        if type(self.timeout_s) not in (int, float) or not math.isfinite(self.timeout_s) or not 0 < self.timeout_s <= 60:
            raise GeminiImageConfigError("Limite de tempo de imagem inválido.", cost_observation=_not_sent())
        if self.config.enabled:
            self._client = httpx.Client(transport=self.transport, follow_redirects=False,
                trust_env=False, timeout=self.timeout_s, headers={
                    "x-goog-api-key": self.config.api_key, "Content-Type": "application/json",
                    "Accept-Encoding": "identity", "User-Agent": "CampaIA/1.0",
                })

    def supports(self, task):
        return self.config.enabled and task is AITask.GENERATE_IMAGE

    def close(self):
        if self._client is not None:
            self._client.close()

    def _payload(self, request):
        if (not isinstance(request, AIRequest)):
            raise ProviderError("Pedido de imagem inválido antes do envio.", cost_observation=_not_sent())
        if (not self.supports(request.task) or request.output_schema_id != IMAGE_SCHEMA.schema_id
                or not request.tenant_id or not isinstance(request.input, dict) or not request.input
                or type(request.timeout_ms) is not int or request.timeout_ms <= 0
                or not isinstance(request.max_cost_units, Decimal) or not request.max_cost_units.is_finite()
                or request.max_cost_units <= 0):
            raise ProviderError("Pedido de imagem indisponível antes do envio.", cost_observation=_not_sent())
        try:
            assert_no_credentials(request.input)
            clean, _report = sanitize(request.input)
            context = json.dumps(clean, ensure_ascii=False, sort_keys=True, allow_nan=False)
            if len(context.encode("utf-8")) > MAX_CONTEXT_BYTES:
                raise ValueError("context bound")
        except (TypeError, ValueError, UnicodeError, RecursionError, CredentialInPayload):
            raise ProviderError("Contexto de imagem inválido antes do envio.", cost_observation=_not_sent()) from None
        return {"model": self.config.model, "store": False,
            "input": [{"type": "text", "text":
                "Gere exatamente uma proposta visual quadrada com base no contexto abaixo. "
                "Não invente selos, certificações ou promessas comerciais. "
                "O resultado será revisado por uma pessoa. Contexto JSON: " + context}],
            "response_format": {"type": "image", "mime_type": "image/png", "aspect_ratio": "1:1", "image_size": "1K"}}

    def _observation(self, body):
        unknown = CostObservation("UNKNOWN", None, model=self.config.model)
        if not isinstance(body, dict) or not isinstance(body.get("usage"), dict):
            return unknown
        counts = [body["usage"].get("total_input_tokens"), body["usage"].get("total_output_tokens")]
        safe = [value if type(value) is int and 0 <= value <= 10**12 else None for value in counts]
        if any(value is None for value in safe):
            return CostObservation("UNKNOWN", None, input_tokens=safe[0], output_tokens=safe[1], model=self.config.model)
        # One configured worst-case output rate covers both image and text/thinking tokens.
        # This is conservative, explicitly unverified, and cannot certify invoice cost/margin.
        amount = ((Decimal(counts[0]) * self.config.input_usd_per_million
                  + Decimal(counts[1]) * self.config.output_usd_per_million)
                  / Decimal("1000000")).quantize(Decimal("0.000001"), rounding=ROUND_CEILING)
        return CostObservation("UNVERIFIED_ESTIMATE", amount, input_tokens=counts[0], output_tokens=counts[1],
            currency="USD", pricing_reference=self.config.pricing_reference, model=self.config.model)

    @staticmethod
    def _image(body, observation):
        try:
            steps = body["steps"]
            if not isinstance(steps, list):
                raise ValueError("steps")
            images = []
            for step in steps:
                if not isinstance(step, dict):
                    raise ValueError("step")
                if step.get("type") != "model_output":
                    continue  # Never expose thought images or tool outputs as a delivered image.
                content = step.get("content")
                if not isinstance(content, list):
                    raise ValueError("content")
                for block in content:
                    if not isinstance(block, dict):
                        raise ValueError("block")
                    if block.get("type") == "image":
                        images.append(block)
            if len(images) != 1:
                raise ValueError("image count")
            image = images[0]
            encoded = image.get("data")
            if (image.get("mime_type") != "image/png" or not isinstance(encoded, str)
                    or not 1 <= len(encoded) <= 4 * ((MAX_ASSET_BYTES + 2) // 3)):
                raise ValueError("image envelope")
            data = base64.b64decode(encoded, validate=True)
            if (not 0 < len(data) <= MAX_ASSET_BYTES or not data.startswith(PNG_SIGNATURE)
                    or base64.b64encode(data).decode("ascii") != encoded):
                raise ValueError("binary envelope")
            # Same restricted Linux worker used for private assets. No C decoder in this process.
            normalized = normalize_asset_image(data)
            return {"mime_type": "image/png", "data_base64": base64.b64encode(normalized.data).decode("ascii"),
                    "width": normalized.width, "height": normalized.height}
        except (KeyError, TypeError, ValueError, UnicodeError, binascii.Error, AssetImageError):
            raise ProviderOutputInvalid("Imagem não passou na validação de entrega.", cost_observation=observation) from None

    def generate(self, request):
        payload = self._payload(request)
        if self._client is None or self._client.is_closed or not self._slot.acquire(blocking=False):
            raise ProviderError("Geração de imagem indisponível antes do envio.", cost_observation=_not_sent())
        try:
            return self._generate(request, payload)
        finally:
            self._slot.release()

    def _generate(self, request, payload):
        started = time.monotonic()
        timeout = min(self.timeout_s, request.timeout_ms / 1000)
        deadline = started + timeout
        unknown = CostObservation("UNKNOWN", None, model=self.config.model)
        try:
            with self._client.stream("POST", _ENDPOINT, json=payload, timeout=timeout) as response:
                if response.status_code != 200:
                    raise ProviderError("Geração de imagem retornou erro HTTP.", cost_observation=unknown)
                if (response.headers.get("Content-Encoding", "identity").strip().lower() not in ("", "identity")
                        or response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json"):
                    raise ProviderOutputInvalid("Envelope de imagem inválido.", cost_observation=unknown)
                length = response.headers.get("Content-Length")
                if length is not None:
                    safe_length = length.lstrip("0") or "0"
                    if (not length.isascii() or not length.isdecimal() or len(safe_length) > len(str(MAX_RESPONSE_BYTES))
                            or int(safe_length) > MAX_RESPONSE_BYTES):
                        raise ProviderOutputInvalid("Resposta de imagem excede o limite.", cost_observation=unknown)
                raw = bytearray()
                for chunk in response.iter_bytes():
                    if time.monotonic() >= deadline:
                        raise ProviderTimeout("Tempo de imagem esgotado.", cost_observation=unknown)
                    if len(raw) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise ProviderOutputInvalid("Resposta de imagem excede o limite.", cost_observation=unknown)
                    raw.extend(chunk)
            if time.monotonic() >= deadline:
                raise ProviderTimeout("Tempo de imagem esgotado.", cost_observation=unknown)
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeError, RecursionError):
                raise ProviderOutputInvalid("Resposta de imagem não é JSON válido.", cost_observation=unknown) from None
        except httpx.TimeoutException:
            raise ProviderTimeout("Tempo de imagem esgotado.", cost_observation=unknown) from None
        except httpx.HTTPError:
            raise ProviderError("Resultado externo de imagem incerto.", cost_observation=unknown) from None
        observation = self._observation(body)
        if not isinstance(body, dict):
            raise ProviderOutputInvalid("Resposta de imagem inválida.", cost_observation=observation)
        if body.get("status") == "blocked":
            raise ModerationBlocked("Imagem bloqueada pelo provedor.", cost_observation=observation)
        if body.get("status") != "completed":
            raise ProviderError("A operação de imagem ainda não foi confirmada.", cost_observation=unknown)
        if observation.cost_units is None or observation.output_tokens == 0:
            raise ProviderError("Imagem sem evidência utilizável de uso.",
                cost_observation=CostObservation("UNKNOWN", None, input_tokens=observation.input_tokens,
                    output_tokens=observation.output_tokens, model=self.config.model))
        model = body.get("model", self.config.model)
        try:
            _metadata(model, model=True)
        except GeminiImageConfigError:
            raise ProviderOutputInvalid("Identidade de modelo inválida.", cost_observation=observation) from None
        output = self._image(body, observation)
        return ProviderResponse(output=output, cost_units=observation.cost_units,
            latency_ms=int((time.monotonic() - started) * 1000), model=model, cost_observation=observation)


__all__ = ["GeminiImageConfig", "GeminiImageConfigError", "GeminiImageProvider", "IMAGE_SCHEMA"]
