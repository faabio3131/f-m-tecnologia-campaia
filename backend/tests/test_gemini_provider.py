from __future__ import annotations

import json
import os
import unittest
from decimal import Decimal

import httpx

from campaia_core.ai_gateway import (
    AIRequest,
    AITask,
    ModerationBlocked,
    OutputSchema,
    Prefer,
    ProviderError,
    ProviderTimeout,
)
from campaia_core.gemini_provider import (
    API_BASE_URL,
    GeminiConfig,
    GeminiConfigError,
    GeminiProvider,
)

_SCHEMA = OutputSchema(
    "campaign-plan",
    frozenset({"objetivo", "funil", "canais", "justificativa"}),
    {"objetivo": str, "funil": str, "canais": list, "justificativa": str},
)

_HAPPY_OUTPUT = {
    "objetivo": "Gerar demanda qualificada.",
    "funil": "TOPO_MEIO",
    "canais": ["GOOGLE_ADS"],
    "justificativa": "Publico definido e orcamento compativel com o canal.",
}


def _config(**overrides) -> GeminiConfig:
    base = dict(api_key="fake-gemini-key", model="gemini-3.8-flash")
    base.update(overrides)
    return GeminiConfig(**base)


def _request(output_schema_id: str = "campaign-plan") -> AIRequest:
    return AIRequest(
        request_id="req-1",
        tenant_id="tenant-1",
        task=AITask.PLAN_CAMPAIGN,
        input={"objetivo": "Vender mais", "orcamento": "5000", "publico": "corredores", "regiao": "BR"},
        output_schema_id=output_schema_id,
        max_cost_units=Decimal("10"),
        prefer=Prefer.QUALITY,
    )


def _interaction_response(
    output: dict, *, input_tokens: int = 120, output_tokens: int = 60, status: str = "completed"
) -> dict:
    return {
        "id": "v1_fake",
        "status": status,
        "usage": {
            "total_tokens": input_tokens + output_tokens,
            "total_input_tokens": input_tokens,
            "total_output_tokens": output_tokens,
        },
        "steps": [
            {"type": "thought", "signature": "fake"},
            {
                "type": "model_output",
                "content": [{"type": "text", "text": json.dumps(output)}],
            },
        ],
        "object": "interaction",
        "model": "gemini-3.8-flash",
    }


class GeminiConfigTests(unittest.TestCase):
    def test_from_env_reads_api_key_and_default_model(self) -> None:
        old = os.environ.get("GEMINI_API_KEY")
        os.environ["GEMINI_API_KEY"] = "env-key"
        os.environ.pop("GEMINI_MODEL", None)
        try:
            cfg = GeminiConfig.from_env()
            self.assertEqual(cfg.api_key, "env-key")
            self.assertEqual(cfg.model, "gemini-3.8-flash")
        finally:
            if old is None:
                os.environ.pop("GEMINI_API_KEY", None)
            else:
                os.environ["GEMINI_API_KEY"] = old

    def test_missing_api_key_fails_closed_on_construction(self) -> None:
        with self.assertRaises(GeminiConfigError):
            GeminiProvider(config=_config(api_key=None), schemas={"campaign-plan": _SCHEMA})


class GeminiProviderRequestShapeTests(unittest.TestCase):
    """Verifica a forma da requisicao e o parsing da resposta contra um transporte HTTP
    falso -- nunca uma chamada de rede real (nenhuma credencial existe nesta sandbox)."""

    def _provider(self, handler) -> GeminiProvider:
        transport = httpx.MockTransport(handler)
        return GeminiProvider(
            config=_config(), schemas={"campaign-plan": _SCHEMA}, transport=transport
        )

    def test_supports_every_task_except_generate_image(self) -> None:
        provider = self._provider(lambda r: httpx.Response(200, json={}))
        self.assertTrue(provider.supports(AITask.PLAN_CAMPAIGN))
        self.assertTrue(provider.supports(AITask.GENERATE_COPY))
        self.assertFalse(provider.supports(AITask.GENERATE_IMAGE))

    def test_unknown_output_schema_id_is_rejected_before_any_network_call(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("nao deveria chamar a rede sem saber que JSON pedir")

        provider = self._provider(handler)
        with self.assertRaises(ProviderError):
            provider.generate(_request(output_schema_id="schema-inexistente"))

    def test_sends_expected_request_shape(self) -> None:
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["headers"] = dict(request.headers)
            seen["body"] = json.loads(request.read())
            return httpx.Response(200, json=_interaction_response(_HAPPY_OUTPUT))

        provider = self._provider(handler)
        provider.generate(_request())

        self.assertTrue(seen["url"].startswith(f"{API_BASE_URL}/interactions"))
        self.assertEqual(seen["headers"]["x-goog-api-key"], "fake-gemini-key")
        self.assertEqual(seen["body"]["model"], "gemini-3.8-flash")
        self.assertIs(seen["body"]["store"], False)
        self.assertIn("PLAN_CAMPAIGN", seen["body"]["input"])
        self.assertIn("objetivo", seen["body"]["input"])

    def test_prompt_tells_the_model_the_json_type_of_each_field(self) -> None:
        """Achado de verificacao real (24/09/2026): sem isto, o Gemini devolveu "canais"
        como uma frase corrida em vez de array JSON -- o schema real exige `list`, entao a
        resposta teria sido rejeitada como SCHEMA_INVALID por OutputSchema.validate(). O
        prompt precisa dizer o TIPO de cada campo, nao so o nome."""
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.read())
            return httpx.Response(200, json=_interaction_response(_HAPPY_OUTPUT))

        provider = self._provider(handler)
        provider.generate(_request())

        prompt = seen["body"]["input"]
        # "canais" e do tipo list em _SCHEMA -- o prompt precisa deixar claro que e um
        # array JSON, nao uma string com itens separados por virgula.
        self.assertIn("canais", prompt)
        self.assertIn("array", prompt)
        # "objetivo" e do tipo str -- continua pedido como string.
        self.assertIn("objetivo", prompt)
        self.assertIn("string", prompt)

    def test_happy_path_parses_output_and_computes_cost(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json=_interaction_response(_HAPPY_OUTPUT, input_tokens=1_000_000, output_tokens=1_000_000)
            )

        provider = self._provider(handler)
        result = provider.generate(_request())

        self.assertEqual(result.output, _HAPPY_OUTPUT)
        self.assertEqual(result.model, "gemini-3.8-flash")
        # 1M tokens de entrada (US$0.75) + 1M de saida (US$3.75) = US$4.50 nesta chamada.
        self.assertEqual(result.cost_units, Decimal("4.500000"))

    def test_non_json_output_is_rejected_not_repaired(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = _interaction_response({})
            body["steps"][-1]["content"][0]["text"] = "isto nao e JSON"
            return httpx.Response(200, json=body)

        provider = self._provider(handler)
        with self.assertRaises(ProviderError):
            provider.generate(_request())

    def test_blocked_status_raises_moderation_blocked(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = _interaction_response(_HAPPY_OUTPUT, status="blocked")
            return httpx.Response(200, json=body)

        provider = self._provider(handler)
        with self.assertRaises(ModerationBlocked):
            provider.generate(_request())

    def test_missing_usage_is_rejected_not_assumed_free(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = _interaction_response(_HAPPY_OUTPUT)
            del body["usage"]
            return httpx.Response(200, json=body)

        provider = self._provider(handler)
        with self.assertRaises(ProviderError):
            provider.generate(_request())

    def test_missing_steps_is_rejected(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            body = _interaction_response(_HAPPY_OUTPUT)
            del body["steps"]
            return httpx.Response(200, json=body)

        provider = self._provider(handler)
        with self.assertRaises(ProviderError):
            provider.generate(_request())

    def test_rate_limited_raises_provider_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": "rate limited"})

        provider = self._provider(handler)
        with self.assertRaises(ProviderError):
            provider.generate(_request())

    def test_server_error_raises_provider_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="internal error")

        provider = self._provider(handler)
        with self.assertRaises(ProviderError):
            provider.generate(_request())

    def test_timeout_raises_provider_timeout(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timed out")

        provider = self._provider(handler)
        with self.assertRaises(ProviderTimeout):
            provider.generate(_request())


if __name__ == "__main__":
    unittest.main()
