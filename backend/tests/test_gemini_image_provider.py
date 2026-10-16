"""Only MockTransport and the existing restricted worker; never a real key or API call."""
import base64
from decimal import Decimal
import json
import os
import unittest
from unittest.mock import patch

import httpx
from PIL import PngImagePlugin

from campaia_core.ai_gateway import (AIGateway, AIRequest, AIStatus, AITask,
    ModerationBlocked, ProviderError, ProviderOutputInvalid, ProviderTimeout)
from campaia_core.asset_images import AssetImageError, verify_normalized_png
from campaia_core.asset_storage import MAX_ASSET_BYTES
from campaia_core.gemini_image_provider import (
    GeminiImageConfig, GeminiImageConfigError, GeminiImageProvider, IMAGE_SCHEMA,
    MAX_CONTEXT_BYTES, MAX_RESPONSE_BYTES,
)
from tests.test_asset_images import encoded


def config(**changes):
    return GeminiImageConfig(**{**dict(enabled=True, api_key="synthetic-image-key", model="gemini-image-fixture",
        input_usd_per_million=Decimal("1.50"), output_usd_per_million=Decimal("30"),
        pricing_reference="image-test-upper-bound-v1"), **changes})


def request(**changes):
    return AIRequest(**{**dict(request_id="image-request-1", tenant_id="tenant-a", task=AITask.GENERATE_IMAGE,
        input={"descricao": "Imagem de calçados", "canal": "META_ADS"}, output_schema_id=IMAGE_SCHEMA.schema_id,
        max_cost_units=Decimal("1")), **changes})


def interaction(data=None, **changes):
    return {**dict(status="completed", model="gemini-image-fixture",
        usage={"total_input_tokens": 3, "total_output_tokens": 1120},
        steps=[{"type": "model_output", "content": [
            {"type": "image", "mime_type": "image/png",
             "data": base64.b64encode(data if data is not None else encoded()).decode("ascii")}]}]), **changes}


class ChunkStream(httpx.SyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
    def __iter__(self):
        yield from self.chunks


class GeminiImageTests(unittest.TestCase):
    def provider(self, handler=None, **options):
        provider = GeminiImageProvider(config=options.pop("config", config()),
            transport=httpx.MockTransport(handler or (lambda _req: httpx.Response(200, json=interaction()))), **options)
        self.addCleanup(provider.close)
        return provider

    def test_default_and_existing_text_key_never_enable_image_transport(self):
        with patch.dict(os.environ, {"GEMINI_IMAGE_ENABLED": "false", "GEMINI_API_KEY": "text-key-must-not-activate",
                                     "GEMINI_IMAGE_MODEL": "ignored-when-disabled"}, clear=True):
            disabled = GeminiImageConfig.from_env()
        self.assertFalse(disabled.enabled)
        self.assertIsNone(disabled.model)
        self.assertIsNone(disabled.api_key)
        provider = self.provider(config=disabled, handler=lambda _req: self.fail("no dispatch"))
        self.assertFalse(provider.supports(AITask.GENERATE_IMAGE))
        with self.assertRaises(ProviderError) as caught:
            provider.generate(request())
        self.assertFalse(caught.exception.details["cost_observation"].dispatched)
        self.assertEqual(caught.exception.details["cost_observation"].cost_units, 0)

    def test_enabled_configuration_requires_explicit_model_key_and_positive_estimates(self):
        for field in ("api_key", "model", "input_usd_per_million", "output_usd_per_million", "pricing_reference"):
            with self.subTest(field=field), self.assertRaises(GeminiImageConfigError):
                config(**{field: None})
        for value in (Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity"), 1, True):
            with self.subTest(value=str(value)), self.assertRaises(GeminiImageConfigError):
                config(output_usd_per_million=value)
        for model in ("https://internal.invalid/model", "model/path", "bad\nmodel", "sk-" + "x" * 32):
            with self.subTest(model_type="invalid"), self.assertRaises(GeminiImageConfigError):
                config(model=model)
        with self.assertRaises(GeminiImageConfigError):
            config(api_key="key\nwith-header-injection")
        with self.assertRaises(GeminiImageConfigError):
            config(enabled="true")

    def test_environment_has_no_default_model_or_rate_and_invalid_flag_is_not_enabled(self):
        with patch.dict(os.environ, {"GEMINI_IMAGE_ENABLED": "true", "GEMINI_IMAGE_API_KEY": "synthetic-image-key"}, clear=True):
            with self.assertRaises(GeminiImageConfigError):
                GeminiImageConfig.from_env()
        values = {"GEMINI_IMAGE_ENABLED": "true", "GEMINI_IMAGE_API_KEY": "synthetic-image-key",
                  "GEMINI_IMAGE_MODEL": "gemini-image-fixture", "GEMINI_IMAGE_INPUT_USD_PER_MILLION": "1.5",
                  "GEMINI_IMAGE_OUTPUT_USD_PER_MILLION": "30", "GEMINI_IMAGE_PRICING_REFERENCE": "image-test-v1"}
        with patch.dict(os.environ, values, clear=True):
            loaded = GeminiImageConfig.from_env()
            self.assertEqual(loaded.output_usd_per_million, Decimal("30"))
            self.assertEqual(loaded.model, "gemini-image-fixture")
        with patch.dict(os.environ, {"GEMINI_IMAGE_ENABLED": "yes"}, clear=True):
            with self.assertRaises(GeminiImageConfigError):
                GeminiImageConfig.from_env()

    def test_repr_never_contains_the_api_key(self):
        provider = self.provider()
        self.assertNotIn("synthetic-image-key", repr(provider))
        self.assertNotIn("synthetic-image-key", repr(provider.config))

    def test_supports_only_the_explicit_image_task(self):
        provider = self.provider()
        for task in AITask:
            self.assertEqual(provider.supports(task), task is AITask.GENERATE_IMAGE)

    def test_exact_request_uses_fixed_origin_inline_image_format_no_history_or_tools(self):
        calls = []
        def handle(req):
            calls.append(req)
            self.assertEqual(str(req.url), "https://generativelanguage.googleapis.com/v1beta/interactions")
            self.assertEqual(req.method, "POST")
            self.assertEqual(req.headers["x-goog-api-key"], "synthetic-image-key")
            self.assertEqual(req.headers["accept-encoding"], "identity")
            body = json.loads(req.content)
            self.assertEqual(set(body), {"model", "input", "store", "response_format"})
            self.assertFalse(body["store"])
            self.assertEqual(body["model"], "gemini-image-fixture")
            self.assertEqual(body["response_format"], {"type": "image", "mime_type": "image/png",
                                                      "aspect_ratio": "1:1", "image_size": "1K"})
            self.assertEqual(len(body["input"]), 1)
            self.assertEqual(body["input"][0]["type"], "text")
            self.assertIn("calçados", body["input"][0]["text"])
            self.assertNotIn("tenant-a", body["input"][0]["text"])
            return httpx.Response(200, json=interaction())
        result = self.provider(handle).generate(request())
        self.assertEqual(len(calls), 1)
        self.assertEqual((result.output["width"], result.output["height"]), (3, 2))
        self.assertEqual(result.output["mime_type"], "image/png")
        self.assertEqual(result.cost_units, Decimal("0.033605"))
        self.assertEqual(result.cost_observation.basis, "UNVERIFIED_ESTIMATE")
        self.assertEqual(result.cost_observation.currency, "USD")
        self.assertEqual(result.cost_observation.input_tokens, 3)
        self.assertIsNone(IMAGE_SCHEMA.validate(result.output))
        verify_normalized_png(base64.b64decode(result.output["data_base64"]))

    def test_transport_also_sanitizes_pii_without_sending_a_rehydration_map(self):
        def handle(req):
            text = json.loads(req.content)["input"][0]["text"]
            self.assertNotIn("cliente@example.com", text)
            self.assertIn("[EMAIL_1]", text)
            self.assertNotIn("_mapping", text)
            return httpx.Response(200, json=interaction())
        self.provider(handle).generate(request(input={"descricao": "contato cliente@example.com"}))

    def test_input_task_schema_tenant_budget_timeout_and_size_reject_before_http(self):
        provider = self.provider(lambda _req: self.fail("preflight must not dispatch"))
        cases = [request(task=AITask.GENERATE_COPY), request(output_schema_id="unknown"),
                 request(tenant_id=""), request(input={}), request(input={"value": "x" * (MAX_CONTEXT_BYTES + 1)}),
                 request(input={"value": float("nan")}), request(input={"value": chr(0xD800)}),
                 request(input={"secret": "sk-" + "x" * 32}), request(max_cost_units=Decimal("0")),
                 request(timeout_ms=True), request(timeout_ms=0)]
        for value in cases:
            with self.subTest(case=value.request_id), self.assertRaises(ProviderError) as caught:
                provider.generate(value)
            self.assertEqual(caught.exception.details["cost_observation"].basis, "NOT_DISPATCHED")
        cyclic = {}; cyclic["cycle"] = cyclic
        with self.assertRaises(ProviderError):
            provider.generate(request(input=cyclic))

    def test_png_metadata_is_removed_by_the_existing_restricted_worker(self):
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("Comment", "private-image-metadata")
        result = self.provider(lambda _req: httpx.Response(200, json=interaction(encoded(pnginfo=metadata)))).generate(request())
        png = base64.b64decode(result.output["data_base64"])
        self.assertNotIn(b"private-image-metadata", png)
        verify_normalized_png(png)

    def test_thought_images_are_ignored_and_never_returned_as_final_output(self):
        body = interaction()
        body["steps"].insert(0, {"type": "thought", "summary": [{"type": "image", "data": "not-an-image"}]})
        result = self.provider(lambda _req: httpx.Response(200, json=body)).generate(request())
        self.assertEqual(result.output["width"], 3)
        thought_only = interaction(steps=[body["steps"][0]])
        with self.assertRaises(ProviderOutputInvalid):
            self.provider(lambda _req: httpx.Response(200, json=thought_only)).generate(request())

    def test_zero_or_multiple_final_images_are_not_a_delivery(self):
        body = interaction()
        for steps in ([], [{"type": "model_output", "content": [{"type": "text", "text": "none"}]}],
                      body["steps"] * 2):
            with self.subTest(kind="image count"), self.assertRaises(ProviderOutputInvalid) as caught:
                self.provider(lambda _req: httpx.Response(200, json=interaction(steps=steps))).generate(request())
            self.assertEqual(caught.exception.details["cost_observation"].cost_units, Decimal("0.033605"))

    def test_url_only_image_and_invalid_base64_mime_or_png_are_rejected_without_fetching(self):
        examples = [{"type": "image", "mime_type": "image/png", "uri": "http://169.254.169.254/"},
                    {"type": "image", "mime_type": "image/svg+xml", "data": base64.b64encode(b"<svg/>").decode()},
                    {"type": "image", "mime_type": "image/png", "data": "%%%"},
                    {"type": "image", "mime_type": "image/png", "data": base64.b64encode(b"bad PNG").decode()},
                    {"type": "image", "mime_type": "image/png", "data": base64.b64encode(encoded()[:-8]).decode()}]
        for block in examples:
            calls = []
            def handle(req):
                calls.append(req)
                return httpx.Response(200, json=interaction(steps=[{"type": "model_output", "content": [block]}]))
            with self.subTest(kind="invalid image"), self.assertRaises(ProviderOutputInvalid):
                self.provider(handle).generate(request())
            self.assertEqual(len(calls), 1)

    def test_decoded_image_bound_is_checked_before_the_worker(self):
        block = {"type": "image", "mime_type": "image/png",
                 "data": base64.b64encode(b"x" * (MAX_ASSET_BYTES + 1)).decode()}
        body = interaction(steps=[{"type": "model_output", "content": [block]}])
        with patch("campaia_core.gemini_image_provider.normalize_asset_image", side_effect=AssertionError("no worker")):
            with self.assertRaises(ProviderOutputInvalid):
                self.provider(lambda _req: httpx.Response(200, json=body)).generate(request())

    def test_worker_unavailable_is_known_no_delivery_with_cost_evidence(self):
        with patch("campaia_core.gemini_image_provider.normalize_asset_image", side_effect=AssetImageError("IMAGE_PROCESSING_UNAVAILABLE")):
            with self.assertRaises(ProviderOutputInvalid) as caught:
                self.provider().generate(request())
        self.assertEqual(caught.exception.details["cost_observation"].cost_units, Decimal("0.033605"))

    def test_missing_boolean_negative_or_fractional_usage_is_unknown_not_free(self):
        for usage in (None, {}, {"total_input_tokens": 3, "total_output_tokens": None},
                      {"total_input_tokens": 3, "total_output_tokens": True},
                      {"total_input_tokens": -1, "total_output_tokens": 1120},
                      {"total_input_tokens": 3, "total_output_tokens": 1.5},
                      {"total_input_tokens": 3, "total_output_tokens": 0}):
            with self.subTest(usage_kind=str(type(usage))), self.assertRaises(ProviderError) as caught:
                self.provider(lambda _req: httpx.Response(200, json=interaction(usage=usage))).generate(request())
            self.assertIsNone(caught.exception.details["cost_observation"].cost_units)
            self.assertEqual(caught.exception.details["cost_observation"].basis, "UNKNOWN")

    def test_partial_valid_usage_is_retained_without_inventing_a_cost(self):
        body = interaction(usage={"total_input_tokens": 3, "total_output_tokens": None})
        with self.assertRaises(ProviderError) as caught:
            self.provider(lambda _req: httpx.Response(200, json=body)).generate(request())
        observation = caught.exception.details["cost_observation"]
        self.assertEqual(observation.input_tokens, 3)
        self.assertIsNone(observation.output_tokens)
        self.assertIsNone(observation.cost_units)

    def test_moderation_block_is_not_turned_into_an_image(self):
        with self.assertRaises(ModerationBlocked) as caught:
            self.provider(lambda _req: httpx.Response(200, json=interaction(status="blocked"))).generate(request())
        self.assertEqual(caught.exception.details["cost_observation"].basis, "UNVERIFIED_ESTIMATE")

    def test_invalid_model_metadata_never_leaks_or_replaces_provenance(self):
        for model in ("http://internal.invalid/", "sk-" + "x" * 32, "x" * 161, None):
            with self.subTest(model_kind="invalid"), self.assertRaises(ProviderOutputInvalid):
                self.provider(lambda _req: httpx.Response(200, json=interaction(model=model))).generate(request())

    def test_http_errors_and_redirects_are_not_followed_retried_or_reported_as_free(self):
        for status in (302, 400, 401, 403, 429, 500, 503):
            calls = []
            def handle(req):
                calls.append(req)
                return httpx.Response(status, headers={"Location": "http://169.254.169.254/"},
                                      content=b"untrusted-secret-error-body")
            with self.subTest(status=status), self.assertRaises(ProviderError) as caught:
                self.provider(handle).generate(request())
            self.assertEqual(len(calls), 1)
            self.assertIsNone(caught.exception.details["cost_observation"].cost_units)
            self.assertNotIn("untrusted-secret-error-body", str(caught.exception))

    def test_compression_content_type_length_and_non_json_envelopes_are_bounded(self):
        examples = [
            httpx.Response(200, stream=ChunkStream([b"{}"]), headers={"Content-Type": "application/json", "Content-Encoding": "gzip"}),
            httpx.Response(200, content=b"{}", headers={"Content-Type": "text/html"}),
            httpx.Response(200, content=b"{}", headers={"Content-Type": "application/json", "Content-Length": str(MAX_RESPONSE_BYTES + 1)}),
            httpx.Response(200, content=b"{}", headers={"Content-Type": "application/json", "Content-Length": "9" * 5000}),
            httpx.Response(200, content=b"{", headers={"Content-Type": "application/json"}),
            httpx.Response(200, json=[]),
        ]
        for response in examples:
            with self.subTest(envelope="invalid"), self.assertRaises(ProviderOutputInvalid):
                self.provider(lambda _req: response).generate(request())

    def test_stream_is_bounded_even_without_content_length(self):
        def handle(_req):
            return httpx.Response(200, headers={"Content-Type": "application/json"},
                                  stream=ChunkStream([b"x" * (1024 * 1024)] * 9))
        with self.assertRaises(ProviderOutputInvalid):
            self.provider(handle).generate(request())

    def test_network_timeout_or_connection_failure_never_retries(self):
        for failure in (httpx.ReadTimeout("private-error"), httpx.ConnectError("private-error")):
            calls = []
            def handle(req):
                calls.append(req); raise failure
            with self.subTest(kind=type(failure).__name__), self.assertRaises(ProviderError if isinstance(failure, httpx.ConnectError) else ProviderTimeout) as caught:
                self.provider(handle).generate(request())
            self.assertEqual(len(calls), 1)
            self.assertNotIn("private-error", str(caught.exception))
            self.assertIsNone(caught.exception.details["cost_observation"].cost_units)

    def test_per_chunk_deadline_stops_a_trickling_response(self):
        provider = self.provider(timeout_s=1)
        ticks = [0]
        def clock():
            ticks[0] += 1
            return 0.0 if ticks[0] == 1 else 2.0
        with patch("campaia_core.gemini_image_provider.time.monotonic", side_effect=clock):
            with self.assertRaises(ProviderTimeout):
                provider.generate(request())
        self.assertTrue(provider._slot.acquire(blocking=False))
        provider._slot.release()

    def test_busy_or_closed_provider_does_not_dispatch(self):
        provider = self.provider(lambda _req: self.fail("no dispatch"))
        provider._slot.acquire()
        try:
            with self.assertRaises(ProviderError) as caught:
                provider.generate(request())
            self.assertEqual(caught.exception.details["cost_observation"].basis, "NOT_DISPATCHED")
        finally:
            provider._slot.release()
        provider.close()
        with self.assertRaises(ProviderError) as caught:
            provider.generate(request())
        self.assertFalse(caught.exception.details["cost_observation"].dispatched)


    def test_incomplete_provider_operation_cannot_become_a_delivered_image(self):
        for status in ("in_progress", "failed", None):
            with self.subTest(status=status), self.assertRaises(ProviderError) as caught:
                self.provider(lambda _req: httpx.Response(200, json=interaction(status=status))).generate(request())
            self.assertEqual(caught.exception.details["cost_observation"].basis, "UNKNOWN")

    def test_gateway_accepts_normalized_schema_and_keeps_unknown_cost_incomplete(self):
        valid = self.provider()
        gateway = AIGateway(providers=[valid], schemas={IMAGE_SCHEMA.schema_id: IMAGE_SCHEMA})
        result = gateway.execute(request())
        self.assertTrue(result.ok)
        self.assertEqual(result.provenance.provider, "GEMINI_IMAGE")
        self.assertEqual(result.provenance.cost_units, Decimal("0.033605"))
        self.assertEqual(gateway.ledger.used("tenant-a"), Decimal("0.033605"))
        calls = []
        def timeout(req):
            calls.append(req); raise httpx.ReadTimeout("unknown")
        pending = AIGateway(providers=[self.provider(timeout)], schemas={IMAGE_SCHEMA.schema_id: IMAGE_SCHEMA})
        failed = pending.execute(request())
        self.assertEqual(failed.status, AIStatus.TIMEOUT)
        self.assertFalse(failed.provenance.cost_complete)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
