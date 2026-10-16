"""Inventory contracts must not accidentally publish generation or private GCS URLs."""
import unittest
from starlette.routing import Match

from api.main import routes
from api.routes_generated_creatives import _public, _paginate_private_creatives
from api.errors import ApiError
from uuid import UUID


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

    def test_private_cursor_paginates_without_duplicates(self):
        def row(n):
            return {"identity": {"creative_id": str(UUID(int=n + 1))}}
        records = [row(i) for i in reversed(range(105))]
        first, more = _paginate_private_creatives(records, None)
        self.assertEqual(len(first), 50)
        self.assertTrue(more)
        cursor = first[-1]["identity"]["creative_id"]
        second, more = _paginate_private_creatives(records, cursor)
        self.assertEqual(len(second), 50)
        self.assertTrue(more)
        third, more = _paginate_private_creatives(records, second[-1]["identity"]["creative_id"])
        self.assertEqual(len(third), 5)
        self.assertFalse(more)
        combined = first + second + third
        self.assertEqual(len({x["identity"]["creative_id"] for x in combined}), 105)

    def test_cursor_must_belong_to_visible_campaign_scope(self):
        records = [{"identity": {"creative_id": str(UUID(int=1))}}]
        for cursor in ("not-a-uuid", str(UUID(int=2)), str(UUID(int=10)).upper()):
            with self.subTest(cursor=cursor), self.assertRaises(ApiError):
                _paginate_private_creatives(records, cursor)

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
