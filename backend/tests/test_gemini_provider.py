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

    def test_request_includes_response_format_with_correct_shape(self) -> None:
        """Forma confirmada por chamada real contra a API (24/09/2026, ver
        docs/evidence/EVIDENCIA_GEMINI_PROVIDER_20260924.md): `type: "text"` +
        `mime_type: "application/json"` + `schema` -- NAO o estilo OpenAI
        (`type: "json_schema"`) nem `type: "object"` no nivel superior, ambos testados
        contra a API real e rejeitados/vazios."""
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.read())
            return httpx.Response(200, json=_interaction_response(_HAPPY_OUTPUT))

        provider = self._provider(handler)
        provider.generate(_request())

        response_format = seen["body"]["response_format"]
        self.assertEqual(response_format["type"], "text")
        self.assertEqual(response_format["mime_type"], "application/json")
        self.assertEqual(response_format["schema"]["type"], "object")
        self.assertEqual(sorted(response_format["schema"]["required"]), sorted(_SCHEMA.required))

    def test_response_format_carries_the_json_type_of_each_field(self) -> None:
        """Achado de verificacao real (24/09/2026): sem imposicao de tipo, o Gemini devolveu
        "canais" como uma frase corrida em vez de array JSON -- o schema real exige `list`,
        entao a resposta teria sido rejeitada como SCHEMA_INVALID por OutputSchema.validate().
        Agora e `response_format.schema.properties`, nao o texto do prompt, quem impoe o
        tipo de cada campo (saida estruturada nativa e a PRIMEIRA barreira)."""
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.read())
            return httpx.Response(200, json=_interaction_response(_HAPPY_OUTPUT))

        provider = self._provider(handler)
        provider.generate(_request())

        properties = seen["body"]["response_format"]["schema"]["properties"]
        # "canais" e do tipo list em _SCHEMA -- precisa virar array JSON com items string.
        self.assertEqual(properties["canais"], {"type": "array", "items": {"type": "string"}})
        # "objetivo"/"funil"/"justificativa" sao do tipo str -- continuam string.
        self.assertEqual(properties["objetivo"], {"type": "string"})

    def test_response_format_maps_bool_int_float_dict_types(self) -> None:
        schema = OutputSchema(
            "kitchen-sink",
            frozenset({"ativo", "quantidade", "peso", "metadados"}),
            {"ativo": bool, "quantidade": int, "peso": float, "metadados": dict},
        )
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.read())
            return httpx.Response(
                200,
                json=_interaction_response(
                    {"ativo": True, "quantidade": 1, "peso": 1.5, "metadados": {}}
                ),
            )

        provider = GeminiProvider(
            config=_config(),
            schemas={"kitchen-sink": schema},
            transport=httpx.MockTransport(handler),
        )
        provider.generate(_request(output_schema_id="kitchen-sink"))

        properties = seen["body"]["response_format"]["schema"]["properties"]
        self.assertEqual(properties["ativo"], {"type": "boolean"})
        self.assertEqual(properties["quantidade"], {"type": "integer"})
        self.assertEqual(properties["peso"], {"type": "number"})
        self.assertEqual(properties["metadados"], {"type": "object"})

    def test_unknown_python_type_in_schema_fails_before_any_network_call(self) -> None:
        class TipoNaoMapeado:
            pass

        schema = OutputSchema(
            "schema-com-tipo-desconhecido",
            frozenset({"campo_esquisito"}),
            {"campo_esquisito": TipoNaoMapeado},
        )

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("nao deveria chamar a rede com um tipo nao mapeavel")

        provider = GeminiProvider(
            config=_config(),
            schemas={"schema-com-tipo-desconhecido": schema},
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaises(ProviderError):
            provider.generate(_request(output_schema_id="schema-com-tipo-desconhecido"))

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




class GeminiCostEvidenceTests(unittest.TestCase):
    def provider(self, body, status=200):
        provider = GeminiProvider(config=_config(), schemas={_SCHEMA.schema_id: _SCHEMA},
            transport=httpx.MockTransport(lambda request: httpx.Response(status, json=body)))
        self.addCleanup(provider._client.close)
        return provider

    def test_invalid_json_still_preserves_reported_usage_and_unverified_estimate(self):
        from campaia_core.ai_gateway import ProviderOutputInvalid
        body = _interaction_response(_HAPPY_OUTPUT)
        body['steps'][-1]['content'][0]['text'] = 'not JSON'
        with self.assertRaises(ProviderOutputInvalid) as caught:
            self.provider(body).generate(_request())
        observation = caught.exception.details['cost_observation']
        self.assertEqual(observation.input_tokens, 120)
        self.assertEqual(observation.output_tokens, 60)
        self.assertEqual(observation.cost_units, Decimal('0.000315'))
        self.assertEqual(observation.basis, 'UNVERIFIED_ESTIMATE')
        self.assertIn('unverified', observation.pricing_reference)

    def test_missing_or_inexact_usage_remains_unknown_instead_of_zero(self):
        for value in (None, True, 1.25, -1, '100'):
            body = _interaction_response(_HAPPY_OUTPUT)
            if value is None:
                del body['usage']
            else:
                body['usage']['total_input_tokens'] = value
            with self.assertRaises(ProviderError) as caught:
                self.provider(body).generate(_request())
            observation = caught.exception.details['cost_observation']
            self.assertIsNone(observation.cost_units)
            self.assertEqual(observation.basis, 'UNKNOWN')

    def test_http_error_does_not_copy_provider_body_or_claim_no_cost(self):
        private = 'private-provider-body-fixture'
        with self.assertRaises(ProviderError) as caught:
            self.provider({'error': private}, status=500).generate(_request())
        self.assertNotIn(private, str(caught.exception))
        self.assertNotIn(private, str(caught.exception.details))

    def test_success_exposes_the_price_basis_as_unverified(self):
        response = self.provider(_interaction_response(_HAPPY_OUTPUT)).generate(_request())
        self.assertEqual(response.cost_observation.basis, 'UNVERIFIED_ESTIMATE')
        self.assertEqual(response.cost_observation.cost_units, response.cost_units)

    def test_contract_rejection_before_network_has_explicit_no_dispatch_evidence(self):
        provider = self.provider({})
        with self.assertRaises(ProviderError) as caught:
            provider.generate(_request(output_schema_id='unknown-fixture-schema'))
        observation = caught.exception.details['cost_observation']
        self.assertFalse(observation.dispatched)
        self.assertEqual(observation.cost_units, Decimal('0'))
        self.assertEqual(observation.basis, 'NOT_DISPATCHED')

if __name__ == "__main__":
    unittest.main()
