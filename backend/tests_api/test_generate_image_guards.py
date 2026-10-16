"""Image-generation route fails closed before any metered/model/storage dispatch."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from api.errors import ApiError
from api.routes_generated_creatives import generate_campaign_image


class ImageGenerationGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_provider_refuses_before_cost_reservation_or_gcs(self):
        campaign = SimpleNamespace(campaign_id="campaign", plan_version=2,
                                   plan={"output": {}}, business_unit_id="unit")
        fixture = SimpleNamespace(tenant_id="tenant", business_unit_id="unit", user_id="owner")
        state = SimpleNamespace(image_provider=SimpleNamespace(config=SimpleNamespace(enabled=False)),
                                credit_ledger=Mock(), ai_gateway=Mock(), db=Mock())
        body = SimpleNamespace(expected_plan_version=2, prompt="Criativo seguro para anúncio",
                               credit_confirmation=SimpleNamespace(model_dump=lambda **_: {}))
        with patch("api.routes_generated_creatives._scope",
                   return_value=(fixture, state, campaign, Mock())), \
             patch("api.deps.require_idempotency_key", return_value="idem-key-long-enough"), \
             patch("api.bounded_body.parse_bounded_body", new_callable=AsyncMock, return_value=body), \
             patch("campaia_core.gcs_asset_storage.configured_asset_storage") as storage:
            with self.assertRaises(ApiError) as caught:
                await generate_campaign_image(SimpleNamespace())
            self.assertEqual(caught.exception.code, "AI_CAPABILITY_UNAVAILABLE")
            state.credit_ledger.decide.assert_not_called()
            state.ai_gateway.execute.assert_not_called()
            storage.assert_not_called()


if __name__ == "__main__":
    unittest.main()
