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
        self.assertIsNone(result["content_url"])
        self.assertEqual(result["state"], "STORAGE_PENDING")
        for forbidden in ("tenant_id", "business_unit_id", "sha256", "object_name",
                          "storage.googleapis.com", "storage_generation", "secret"):
            self.assertNotIn(forbidden, str(result))

    def test_image_mutation_is_explicitly_guarded_by_single_post_route(self):
        images = [r for r in routes if getattr(r, "path", "").startswith(
            "/campaigns/{campaignId}/images")]
        self.assertEqual(len(images), 6)
        self.assertEqual(sum("POST" in r.methods for r in images), 2)
        self.assertEqual(sum("GET" in r.methods for r in images), 4)
        self.assertEqual({r.path for r in images}, {
            "/campaigns/{campaignId}/images",
            "/campaigns/{campaignId}/images/quote",
            "/campaigns/{campaignId}/images/{creativeId}",
            "/campaigns/{campaignId}/images/{creativeId}/content",
            "/campaigns/{campaignId}/images/{creativeId}/reconcile",
        })


if __name__ == "__main__":
    unittest.main()
