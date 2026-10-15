from datetime import datetime, timedelta, timezone
import unittest

from campaia_core.billing_cycles import PaidCycleSchedule, anniversary, period_index


class BillingCycleTests(unittest.TestCase):
    def test_original_day_recovers_and_timezone_is_commercial(self):
        # 31 January at 23:30 in Sao Paulo is 1 February in UTC.
        anchor = datetime(2026, 2, 1, 2, 30, tzinfo=timezone.utc)
        self.assertEqual(anniversary(anchor, 1), datetime(2026, 3, 1, 2, 30, tzinfo=timezone.utc))
        self.assertEqual(anniversary(anchor, 2), datetime(2026, 4, 1, 2, 30, tzinfo=timezone.utc))
        leap = datetime(2028, 1, 31, 15, tzinfo=timezone.utc)
        self.assertEqual(anniversary(leap, 1).day, 29)
        self.assertEqual(anniversary(leap, 2).day, 31)

    def test_half_open_boundaries_and_calendar_gaps(self):
        anchor = datetime(2026, 1, 31, 15, tzinfo=timezone.utc)
        for index in range(36):
            edge = anniversary(anchor, index + 1)
            self.assertEqual(period_index(anchor, edge - timedelta(microseconds=1)), index)
            self.assertEqual(period_index(anchor, edge), index + 1)
        with self.assertRaises(ValueError):
            period_index(anchor, anchor - timedelta(seconds=1))
        with self.assertRaises(ValueError):
            anniversary(anchor.replace(tzinfo=None), 1)
        for invalid in (-1, True, 1.2):
            with self.assertRaises(ValueError):
                anniversary(anchor, invalid)

    def test_payment_anchors_once_replays_and_recovery_keeps_anniversary(self):
        schedule = PaidCycleSchedule('instance-1')
        at = datetime(2026, 1, 31, 15, tzinfo=timezone.utc)
        self.assertIsNone(schedule.current_paid_index(at))
        first = schedule.obligation_id('tenant-a', 0)
        schedule = schedule.confirm_payment('tenant-a', first, 0, at)
        self.assertEqual(schedule, schedule.confirm_payment('tenant-a', first, 0, at + timedelta(days=5)))
        renewal = schedule.obligation_id('tenant-a', 1)
        recovered = schedule.confirm_payment('tenant-a', renewal, 1, at + timedelta(days=31))
        self.assertEqual(recovered.anchor_at, at)
        self.assertEqual(recovered.bounds(1)[0], datetime(2026, 2, 28, 15, tzinfo=timezone.utc))
        self.assertIsNone(schedule.current_paid_index(anniversary(at, 1)))
        self.assertEqual(recovered.current_paid_index(anniversary(at, 1)), 1)

    def test_early_payment_does_not_advance_effective_period(self):
        at = datetime(2026, 1, 15, 15, tzinfo=timezone.utc)
        s = PaidCycleSchedule('instance-1')
        s = s.confirm_payment('a', s.obligation_id('a', 0), 0, at)
        s = s.confirm_payment('a', s.obligation_id('a', 1), 1, at + timedelta(days=10))
        self.assertEqual(s.current_paid_index(at + timedelta(days=10)), 0)
        self.assertEqual(s.current_paid_index(anniversary(at, 1)), 1)

    def test_product_tenant_lifecycle_and_missing_debt_fail_closed(self):
        s = PaidCycleSchedule('instance-1')
        at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assertNotEqual(s.obligation_id('a', 0), s.obligation_id('b', 0))
        self.assertNotEqual(s.obligation_id('a', 0), PaidCycleSchedule('instance-2').obligation_id('a', 0))
        for tenant, identity, index in [('b', s.obligation_id('a', 0), 0),
                                        ('a', s.obligation_id('a', 1), 1)]:
            with self.assertRaises(ValueError):
                s.confirm_payment(tenant, identity, index, at)
        with self.assertRaises(ValueError):
            PaidCycleSchedule('instance-1', anchor_at=at)
