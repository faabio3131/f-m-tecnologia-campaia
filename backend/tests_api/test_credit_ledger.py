"""Commercial accounting: durable reservations, replay, caps and immutable evidence."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from api.credit_store import PersistentCreditLedger
from api.db import Database
from campaia_core.credit_ledger import CreditCycle, CreditLedgerError, CreditLimitExceeded

NOW = datetime(2026, 10, 15, tzinfo=timezone.utc)
WEIGHTS = (('strategy', 5), ('copy', 3), ('audience', 2), ('text_revision', 1),
           ('performance', 5), ('image_standard', 15))


def cycle(tenant='a', **changes):
    return replace(CreditCycle(tenant, 'cycle-1', NOW, NOW + timedelta(days=30),
                              'commercial-v1-20261015', 10, Decimal('1.00'), WEIGHTS), **changes)


class CreditLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / 'credits.db')
        self.databases = []
        self.ledger = self.worker()
        self.open()

    def tearDown(self):
        for db in self.databases:
            db._conn.close()
        self.tmp.cleanup()

    def worker(self):
        db = Database(self.path)
        self.databases.append(db)
        return PersistentCreditLedger(db.table('credit_journal'))

    def open(self, tenant='a', **changes):
        return self.ledger.decide(tenant, 'open_cycle', cycle=cycle(tenant, **changes), at=NOW)

    def reserve(self, op='op', action='strategy', tenant='a'):
        return self.ledger.decide(tenant, 'reserve', cycle_id='cycle-1',
                                  operation_id=op, action=action, at=NOW)

    def finish(self, op='op', kind='SETTLE', ref='delivery', tenant='a'):
        return self.ledger.decide(tenant, 'finish', operation_id=op, kind=kind,
                                  reference=ref, at=NOW + timedelta(seconds=1))

    def consent(self, cap='5.00', ref='consent', tenant='a'):
        return self.ledger.decide(tenant, 'consent', cycle_id='cycle-1',
                                  cap=Decimal(cap), actor='owner', reference=ref, at=NOW)

    def test_reserve_settle_restart_replay(self):
        self.assertFalse(self.reserve().replayed)
        self.assertEqual(self.ledger.balance('a', 'cycle-1').reserved_credits, 5)
        self.assertEqual(self.ledger.balance('a', 'cycle-1').consumed_credits, 0)
        self.assertTrue(self.reserve().replayed)
        settled = self.finish()
        fresh = self.worker()
        self.assertEqual(fresh.balance('a', 'cycle-1').consumed_credits, 5)
        replay = fresh.decide('a', 'finish', operation_id='op', kind='SETTLE',
                              reference='delivery', at=NOW + timedelta(days=40))
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.entry, settled.entry)
        self.assertEqual(self.reserve().entry.kind, 'SETTLE')
        self.assertEqual(len(fresh.entries('a')), 3)

    def test_uncertain_reservation_survives_restart_without_expiring(self):
        self.reserve('1'); self.reserve('2')
        fresh = self.worker()
        with self.assertRaises(CreditLimitExceeded):
            fresh.decide('a', 'reserve', cycle_id='cycle-1', operation_id='next',
                          action='text_revision', at=NOW)
        replay = fresh.decide('a', 'reserve', cycle_id='cycle-1', operation_id='1',
                              action='strategy', at=NOW + timedelta(days=40))
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.entry.kind, 'RESERVE')

    def test_failure_release_and_reversal_never_erase_history(self):
        self.reserve()
        self.finish(kind='RELEASE', ref='invalid-output')
        self.assertTrue(self.finish(kind='RELEASE', ref='invalid-output').replayed)
        self.assertEqual(self.ledger.balance('a', 'cycle-1').included_available, 10)
        with self.assertRaises(CreditLedgerError):
            self.finish()
        self.assertEqual(self.reserve().entry.kind, 'RELEASE')
        self.reserve('2'); self.finish('2')
        self.finish('2', kind='REVERSE', ref='correction')
        self.assertTrue(self.finish('2', kind='REVERSE', ref='correction').replayed)
        self.assertEqual(self.ledger.balance('a', 'cycle-1').consumed_credits, 0)
        self.assertEqual([e.kind for e in self.ledger.entries('a')],
                         ['OPEN', 'RESERVE', 'RELEASE', 'RESERVE', 'SETTLE', 'REVERSE'])

    def test_default_no_extras_full_operation_cap_and_revocation(self):
        self.reserve('1'); self.reserve('2')
        with self.assertRaises(CreditLimitExceeded):
            self.reserve('3')
        self.consent(); self.reserve('3')
        b = self.ledger.balance('a', 'cycle-1')
        self.assertEqual(b.extra_committed_amount, Decimal('5.00'))
        self.assertEqual(b.extra_consumed_amount, Decimal('0.00'))
        with self.assertRaises(CreditLimitExceeded):
            self.reserve('4', 'text_revision')
        self.consent('0.00', 'revoke')
        for op in ('1', '2', '3'):
            self.finish(op, ref='delivery-' + op)
        self.assertEqual(self.ledger.balance('a', 'cycle-1').extra_consumed_amount,
                         Decimal('5.00'))
        with self.assertRaises(CreditLimitExceeded):
            self.reserve('4', 'text_revision')

    def test_trial_and_tenant_isolation(self):
        self.open('b', trial=True, included_credits=30)
        with self.assertRaises(CreditLedgerError):
            self.consent(tenant='b')
        self.reserve()
        self.assertEqual(self.ledger.balance('b', 'cycle-1').reserved_credits, 0)
        with self.assertRaises(CreditLedgerError):
            self.finish(tenant='b')
        with self.assertRaises(CreditLedgerError):
            self.ledger.decide('a', 'open_cycle', cycle=cycle('b'), at=NOW)
        self.assertEqual(self.ledger.entries('missing'), ())
        self.reserve(tenant='b')
        self.finish(tenant='b')
        self.assertEqual(self.ledger.balance('b', 'cycle-1').consumed_credits, 5)
        self.assertEqual(self.ledger.balance('a', 'cycle-1').consumed_credits, 0)

    def test_conflicting_replays_and_duplicate_delivery_fail_closed(self):
        self.reserve()
        with self.assertRaises(CreditLedgerError):
            self.reserve(action='copy')
        with self.assertRaises(CreditLedgerError):
            self.open(included_credits=700)
        self.consent()
        with self.assertRaises(CreditLedgerError):
            self.consent('10.00')
        self.finish(); self.reserve('2')
        with self.assertRaises(CreditLedgerError):
            self.finish('2')
        with self.assertRaises(CreditLedgerError):
            self.ledger.decide('a', 'finish', operation_id='2', kind='RELEASE',
                              reference='failure', at=NOW-timedelta(seconds=1))

    def test_half_open_cycle_no_rollover_and_global_operation_identity(self):
        end = cycle().ends_at
        with self.assertRaises(CreditLedgerError):
            self.ledger.decide('a', 'reserve', cycle_id='cycle-1', operation_id='late',
                              action='strategy', at=end)
        self.reserve()
        self.ledger.decide('a', 'open_cycle', cycle=cycle(cycle_id='cycle-2',
                           starts_at=end, ends_at=end+timedelta(days=30)), at=end)
        self.assertEqual(self.ledger.balance('a', 'cycle-2').included_available, 10)
        self.assertEqual(self.ledger.balance('a', 'cycle-2').extra_cap, 0)
        with self.assertRaises(CreditLedgerError):
            self.ledger.decide('a', 'reserve', cycle_id='cycle-2', operation_id='op',
                              action='strategy', at=end)
        self.ledger.decide('a', 'finish', operation_id='op', kind='SETTLE',
                          reference='delivery', at=end)
        self.assertEqual(self.ledger.balance('a', 'cycle-1').consumed_credits, 5)

    def test_concurrent_workers_cannot_over_reserve_or_duplicate(self):
        workers = [self.worker() for _ in range(8)]
        def attempt(item):
            i, worker = item
            try:
                return worker.decide('a', 'reserve', cycle_id='cycle-1',
                                     operation_id=str(i), action='strategy', at=NOW)
            except CreditLimitExceeded:
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, enumerate(workers)))
        self.assertEqual(sum(r is not None for r in results), 2)
        winner = next(r.entry.operation_id for r in results if r)
        with ThreadPoolExecutor(max_workers=8) as pool:
            replays = list(pool.map(lambda w: w.decide('a', 'reserve', cycle_id='cycle-1',
                                operation_id=winner, action='strategy', at=NOW), workers))
        self.assertTrue(all(r.replayed for r in replays))
        self.assertEqual(self.ledger.balance('a', 'cycle-1').reserved_credits, 10)

    def test_atomic_rollback_and_database_append_only(self):
        db = self.databases[0]
        with self.assertRaises(RuntimeError):
            with db.transaction():
                self.reserve()
                raise RuntimeError('rollback')
        self.assertEqual(self.ledger.balance('a', 'cycle-1').reserved_credits, 0)
        entry = self.reserve().entry
        table = db.table('credit_journal')
        key = self.ledger._key('a', entry.entry_id)
        for mutation in (lambda: table.put(key, 'a', entry), lambda: table.delete(key)):
            with self.assertRaises(Exception):
                with db.transaction():
                    mutation()
        self.assertEqual(len(self.ledger.entries('a')), 2)

    def test_invalid_snapshots_and_nonbillable_actions(self):
        for changes in ({'included_credits': -1}, {'extra_credit_price': Decimal('NaN')},
                        {'extra_credit_price': Decimal('0.001')},
                        {'action_weights': (('x', 1), ('x', 2))},
                        {'starts_at': NOW.replace(tzinfo=None)}):
            with self.subTest(changes=changes), self.assertRaises(CreditLedgerError):
                cycle(**changes)
        for action in ('kill_switch', 'policy', 'publish', 'bundle'):
            with self.assertRaises(CreditLedgerError):
                self.reserve(action=action)
        self.assertEqual(self.ledger.balance('a', 'cycle-1').included_available, 10)
