"""Retry policy and timeout exhaustive tests."""

from __future__ import annotations

import unittest

from apiclient.exceptions import TransportError
from apiclient.models import CaseInsensitiveHeaders, Response
from apiclient.resilience.retry import RetryPolicy
from apiclient.resilience.timeout import TimeoutConfig


class TimeoutTests(unittest.TestCase):
    def test_from_single_value_none_uses_defaults(self) -> None:
        cfg = TimeoutConfig.from_single_value(None)
        self.assertEqual(cfg.connect, 5.0)
        self.assertEqual(cfg.read, 10.0)

    def test_from_single_value_sets_all(self) -> None:
        cfg = TimeoutConfig.from_single_value(3.5)
        self.assertEqual(cfg.connect, 3.5)
        self.assertEqual(cfg.total, 3.5)


class RetryPolicyExhaustiveTests(unittest.TestCase):
    def test_should_retry_response_respects_method(self) -> None:
        policy = RetryPolicy(retries=1, retry_statuses=frozenset({503}))
        response = Response(
            503,
            "Unavailable",
            CaseInsensitiveHeaders(),
            b"",
            "http://x",
        )
        self.assertTrue(policy.should_retry_response("GET", response))
        self.assertFalse(policy.should_retry_response("POST", response))

    def test_should_retry_response_when_non_idempotent_allowed(self) -> None:
        policy = RetryPolicy(
            retries=1,
            retry_non_idempotent=True,
            retry_statuses=frozenset({503}),
        )
        response = Response(503, "X", CaseInsensitiveHeaders(), b"", "http://x")
        self.assertTrue(policy.should_retry_response("POST", response))

    def test_should_retry_exception(self) -> None:
        policy = RetryPolicy(retries=1)
        self.assertTrue(policy.should_retry_exception("GET", TransportError("x")))

    def test_delay_for_with_retry_after_header(self) -> None:
        policy = RetryPolicy(retries=2, backoff_factor=1.0, jitter=0.0)
        response = Response(
            503,
            "X",
            CaseInsensitiveHeaders({"Retry-After": "2"}),
            b"",
            "http://x",
        )
        delay = policy.delay_for(2, response)
        self.assertGreaterEqual(delay, 2.0)

    def test_max_attempts_includes_initial(self) -> None:
        policy = RetryPolicy(retries=3)
        self.assertEqual(policy.max_attempts, 4)


if __name__ == "__main__":
    unittest.main()
