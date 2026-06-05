"""Tests for the auth redaction."""

from __future__ import annotations

import base64
import unittest

from apiclient.auth import ApiKeyHeaderAuth, ApiKeyQueryAuth, BasicAuth, BearerTokenAuth
from apiclient.cli.output import build_curl
from apiclient.models import Request
from apiclient.observability.redaction import redact_headers, redact_url


class AuthRedactionTests(unittest.TestCase):
    def test_bearer_auth_header_and_redaction(self) -> None:
        request = BearerTokenAuth("sk_test_secret").apply(Request("GET", "http://example.test"))
        self.assertEqual(request.headers["Authorization"], "Bearer sk_test_secret")
        self.assertEqual(redact_headers(request.headers)["Authorization"], "Bearer sk_t...redacted")

    def test_basic_auth_is_base64_encoded(self) -> None:
        request = BasicAuth("demo", "secret").apply(Request("GET", "http://example.test"))
        expected = base64.b64encode(b"demo:secret").decode("ascii")
        self.assertEqual(request.headers["Authorization"], f"Basic {expected}")

    def test_api_key_header_and_query_redact(self) -> None:
        request = ApiKeyHeaderAuth("X-API-Key", "demo-key").apply(Request("GET", "http://example.test"))
        self.assertEqual(redact_headers(request.headers)["X-API-Key"], "...redacted")
        query_request = ApiKeyQueryAuth("api_key", "demo-key").apply(Request("GET", "http://example.test/path"))
        self.assertIn("api_key=...redacted", redact_url(query_request.url))

    def test_curl_export_redacts_auth(self) -> None:
        request = BearerTokenAuth("sk_test_secret").apply(Request("GET", "http://example.test"))
        curl = build_curl(request)
        self.assertNotIn("sk_test_secret", curl)
        self.assertIn("Bearer sk_t...redacted", curl)


if __name__ == "__main__":
    unittest.main()
