"""Tests for the retry jitter."""

from __future__ import annotations

import unittest

from apiclient.resilience.retry import RetryPolicy


class RetryDelayTests(unittest.TestCase):
    def test_jitter_is_applied_under_max(self) -> None:
        policy = RetryPolicy(retries=1, backoff_factor=0.5, jitter=0.5, max_backoff=10)
        delays = {policy.delay_for(1) for _ in range(50)}
        # backoff is 0.5 + jitter in [0, 0.5]; never exceeds 1.0 and rarely equal.
        for delay in delays:
            self.assertGreaterEqual(delay, 0.5)
            self.assertLessEqual(delay, 1.0)
        self.assertGreater(len(delays), 1)

    def test_max_backoff_clamps_total_not_just_exponential(self) -> None:
        policy = RetryPolicy(retries=1, backoff_factor=10, jitter=5, max_backoff=2)
        delay = policy.delay_for(3)
        self.assertEqual(delay, 2)


if __name__ == "__main__":
    unittest.main()
