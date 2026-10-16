"""Atomic image-delivery credit gate refuses non-stored creative without ledger mutation."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from campaia_core.asset_storage import AssetStorageError
from campaia_core.creative_assets import CreativeIdentity
from api.creative_image_settlement import settle_stored_creative


class SettlementGateTests(unittest.TestCase):
    def test_no_settle_before_storage_verified(self):
        identity = CreativeIdentity("tenant", "unit", "campaign", 1, str(uuid4()))
        state = SimpleNamespace(db=Mock(), credit_ledger=Mock(),
                                idempotency=Mock(), audit=Mock())
        with patch("api.creative_repository.CreativeRepository") as repository:
            repository.return_value.get.return_value = {
                "state": "STORAGE_PENDING", "storage_generation": None}
            def invoke(tenant, key, callback):
                return callback(), False
            state.idempotency.execute.side_effect = invoke
            with self.assertRaises(AssetStorageError):
                settle_stored_creative(state, identity=identity,
                                       operation_id="op", delivery_key="idem",
                                       actor_id="owner")
            state.credit_ledger.decide.assert_not_called()
            state.audit.append.assert_not_called()

    def test_stored_proof_settles_via_one_idempotent_boundary(self):
        identity = CreativeIdentity("tenant", "unit", "campaign", 1, str(uuid4()))
        state = SimpleNamespace(db=Mock(), credit_ledger=Mock(),
                                idempotency=Mock(), audit=Mock())
        state.credit_ledger.decide.return_value.entry.entry_id = "journal-entry"
        with patch("api.creative_repository.CreativeRepository") as repository:
            repository.return_value.get.return_value = {
                "state": "STORED", "storage_generation": "17"}
            def invoke(tenant, key, callback):
                return callback(), False
            state.idempotency.execute.side_effect = invoke
            output, replay = settle_stored_creative(
                state, identity=identity, operation_id="op",
                delivery_key="idem", actor_id="owner")
            self.assertFalse(replay)
            self.assertEqual(output["credit_entry_id"], "journal-entry")
            state.credit_ledger.decide.assert_called_once()
            self.assertEqual(state.credit_ledger.decide.call_args.args,
                             ("tenant", "finish"))
            self.assertEqual(state.credit_ledger.decide.call_args.kwargs["kind"],
                             "SETTLE")
            self.assertEqual(state.idempotency.execute.call_count, 1)


if __name__ == "__main__":
    unittest.main()
