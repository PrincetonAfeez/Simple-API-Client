"""Tests for the response summary."""

from __future__ import annotations

import unittest

from apiclient.client import response_summary
from apiclient.models import CaseInsensitiveHeaders, Response


class ResponseSummaryTests(unittest.TestCase):
    def test_json_body_is_decoded(self) -> None:
        body = b'{"name": "Ada"}'
        response = Response(
            200,
            "OK",
            CaseInsensitiveHeaders({"Content-Type": "application/json"}),
            body,
            "http://x",
        )
        summary = response_summary(response)
        self.assertEqual(summary["body"], {"name": "Ada"})

    def test_text_body_is_kept_as_string(self) -> None:
        response = Response(
            200,
            "OK",
            CaseInsensitiveHeaders({"Content-Type": "text/plain"}),
            b"hello",
            "http://x",
        )
        self.assertEqual(response_summary(response)["body"], "hello")

    def test_binary_body_is_summarized(self) -> None:
        body = b"\xff\xd8\xff\xe0\x00\x10"
        response = Response(
            200,
            "OK",
            CaseInsensitiveHeaders({"Content-Type": "image/jpeg"}),
            body,
            "http://x",
        )
        summary = response_summary(response)
        self.assertEqual(summary["body"], f"<{len(body)} binary bytes>")


if __name__ == "__main__":
    unittest.main()
