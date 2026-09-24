from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from campaia_core.rate_limit import FixedWindowRateLimiter


def _at(seconds: float) -> datetime:
    return datetime(2026, 9, 24, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=seconds)


class FixedWindowRateLimiterTests(unittest.TestCase):
    def test_allows_up_to_the_limit_within_the_window(self) -> None:
        limiter = FixedWindowRateLimiter(max_requests=3, window=timedelta(seconds=60))
        self.assertTrue(limiter.allow("1.2.3.4", now=_at(0)))
        self.assertTrue(limiter.allow("1.2.3.4", now=_at(1)))
        self.assertTrue(limiter.allow("1.2.3.4", now=_at(2)))

    def test_rejects_beyond_the_limit_within_the_same_window(self) -> None:
        limiter = FixedWindowRateLimiter(max_requests=3, window=timedelta(seconds=60))
        for _ in range(3):
            self.assertTrue(limiter.allow("1.2.3.4", now=_at(0)))
        self.assertFalse(limiter.allow("1.2.3.4", now=_at(1)))

    def test_resets_after_the_window_elapses(self) -> None:
        limiter = FixedWindowRateLimiter(max_requests=2, window=timedelta(seconds=60))
        self.assertTrue(limiter.allow("1.2.3.4", now=_at(0)))
        self.assertTrue(limiter.allow("1.2.3.4", now=_at(1)))
        self.assertFalse(limiter.allow("1.2.3.4", now=_at(2)))
        self.assertTrue(limiter.allow("1.2.3.4", now=_at(61)))

    def test_keys_are_independent(self) -> None:
        limiter = FixedWindowRateLimiter(max_requests=1, window=timedelta(seconds=60))
        self.assertTrue(limiter.allow("1.2.3.4", now=_at(0)))
        self.assertFalse(limiter.allow("1.2.3.4", now=_at(0)))
        self.assertTrue(limiter.allow("5.6.7.8", now=_at(0)))

    def test_missing_key_fails_closed(self) -> None:
        limiter = FixedWindowRateLimiter(max_requests=100, window=timedelta(seconds=60))
        self.assertFalse(limiter.allow("", now=_at(0)))


if __name__ == "__main__":
    unittest.main()
