"""Tests for the async client."""

from __future__ import annotations

import asyncio
import unittest

from apiclient.concurrency import fetch_many
from apiclient.models import CaseInsensitiveHeaders, Response


class _FakeClient:
    def __init__(self, behavior) -> None:
        self.behavior = behavior

    def request(self, method, url, **kwargs):  # noqa: ANN001
        outcome = self.behavior(url)
        if isinstance(outcome, Exception):
            raise outcome
        return Response(200, "OK", CaseInsensitiveHeaders(), b"ok", url)


class FetchManyTests(unittest.TestCase):
    def test_collects_all_responses(self) -> None:
        client = _FakeClient(lambda url: "ok")
        result = asyncio.run(
            fetch_many(client, [f"http://x/{i}" for i in range(4)], concurrency=2)
        )
        self.assertEqual(result.succeeded, 4)
        self.assertEqual(result.failed, 0)
        self.assertEqual(len(result.responses), 4)

    def test_aggregates_errors_when_not_fail_fast(self) -> None:
        def behavior(url):
            if url.endswith("/bad"):
                raise RuntimeError("nope")
            return "ok"

        client = _FakeClient(behavior)
        result = asyncio.run(
            fetch_many(
                client,
                ["http://x/ok", "http://x/bad", "http://x/ok"],
                concurrency=2,
            )
        )
        self.assertEqual(result.succeeded, 2)
        self.assertEqual(result.failed, 1)
        self.assertTrue(any("/bad" in err for err in result.errors))

    def test_fail_fast_stops_collecting_after_first_error(self) -> None:
        def behavior(url):
            if url.endswith("/bad"):
                raise RuntimeError("nope")
            return "ok"

        client = _FakeClient(behavior)
        # Sequential one-at-a-time to keep ordering deterministic.
        result = asyncio.run(
            fetch_many(
                client,
                ["http://x/bad", "http://x/ok", "http://x/ok"],
                concurrency=1,
                fail_fast=True,
            )
        )
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.succeeded, 0)


if __name__ == "__main__":
    unittest.main()
