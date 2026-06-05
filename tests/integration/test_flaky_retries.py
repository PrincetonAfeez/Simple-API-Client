"""Tests for the flaky retries."""

from __future__ import annotations

import unittest

from apiclient.client import ApiClient
from apiclient.resilience.retry import RetryPolicy
from tests.helpers import wsgi_server


class FlakyRetryTests(unittest.TestCase):
    def test_flaky_endpoint_succeeds_after_retry(self) -> None:
        with wsgi_server() as base_url:
            client = ApiClient(
                retry_policy=RetryPolicy(retries=2, backoff_factor=0, jitter=0),
                sleep_func=lambda _: None,
            )
            # Reset shared module-level flaky counters so the test is
            # independent of any prior run inside the same process.
            client.request("GET", f"{base_url}/reset-flaky")
            response = client.request(
                "GET", f"{base_url}/flaky?key=unit&succeed_after=2", trace=True
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["attempt"], 2)
        self.assertTrue(any("Retryable HTTP 503" in event for event in client.last_trace))


if __name__ == "__main__":
    unittest.main()
