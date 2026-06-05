"""Tests for the retry policy."""

from __future__ import annotations

import unittest

from apiclient.client import ApiClient
from apiclient.exceptions import ConnectionFailure, RetryExhausted
from apiclient.models import CaseInsensitiveHeaders, Request, Response
from apiclient.resilience.retry import RetryPolicy
from apiclient.resilience.timeout import TimeoutConfig
from apiclient.transport.base import Transport


def response(status: int) -> Response:
    return Response(status, "Reason", CaseInsensitiveHeaders({"Content-Length": "0"}), b"", "http://example.test")


class FakeTransport(Transport):
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def send(self, request: Request, timeout: TimeoutConfig) -> Response:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        outcome.request = request
        return outcome


class RetryPolicyTests(unittest.TestCase):
    def test_get_retries_retryable_status(self) -> None:
        transport = FakeTransport([response(503), response(200)])
        client = ApiClient(
            transport=transport,
            retry_policy=RetryPolicy(retries=1, backoff_factor=0, jitter=0),
            sleep_func=lambda _: None,
        )
        result = client.send(Request("GET", "http://example.test"))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(transport.calls, 2)

    def test_post_does_not_retry_by_default(self) -> None:
        transport = FakeTransport([response(503), response(200)])
        client = ApiClient(
            transport=transport,
            retry_policy=RetryPolicy(retries=1, backoff_factor=0, jitter=0),
            sleep_func=lambda _: None,
        )
        result = client.send(Request("POST", "http://example.test"))
        self.assertEqual(result.status_code, 503)
        self.assertEqual(transport.calls, 1)

    def test_retry_exhausted_for_network_failure(self) -> None:
        transport = FakeTransport([ConnectionFailure("nope"), ConnectionFailure("still nope")])
        client = ApiClient(
            transport=transport,
            retry_policy=RetryPolicy(retries=1, backoff_factor=0, jitter=0),
            sleep_func=lambda _: None,
        )
        with self.assertRaises(RetryExhausted):
            client.send(Request("GET", "http://example.test"))


if __name__ == "__main__":
    unittest.main()
