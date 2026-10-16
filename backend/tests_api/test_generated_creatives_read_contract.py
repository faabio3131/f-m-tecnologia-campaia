"""Inventory contracts must not accidentally publish generation or private GCS URLs."""
import unittest
from starlette.routing import Match

from api.main import routes
from api.routes_generated_creatives import _public


class GeneratedCreativeReadContractTests(unittest.TestCase):
    def test_inventory_is_private_and_does_not_leak_storage_paths(self):
        row = {
            "identity": {"creative_id": "id", "campaign_id": "campaign",
                         "campaign_version": 1, "business_unit_id": "unit",
                         "tenant_id": "tenant"},
            "manifest": {"width": 512, "height": 512, "sha256": "x" * 64},
            "state": "STORAGE_PENDING", "revision": 2,
        }
        result = _public(row)
        self.assertFalse(result["available"])
        self.assertEqual(result["state"], "STORAGE_PENDING")
        for forbidden in ("tenant_id", "business_unit_id", "sha256", "object_name",
                          "url", "storage_generation", "secret"):
            self.assertNotIn(forbidden, str(result))

    def test_image_mutations_are_not_exposed_before_cost_and_delivery_gates(self):
        images = [r for r in routes if getattr(r, "path", "").startswith(
            "/campaigns/{campaignId}/images")]
        self.assertEqual(len(images), 3)
        self.assertTrue(all(r.methods == {"GET", "HEAD"} or r.methods == {"GET"}
                            for r in images))
        self.assertEqual({r.path for r in images}, {
            "/campaigns/{campaignId}/images",
            "/campaigns/{campaignId}/images/quote",
            "/campaigns/{campaignId}/images/{creativeId}",
        })


if __name__ == "__main__":
    unittest.main()
