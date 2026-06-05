"""Tests for request body encoding and auth strategy validation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apiclient.auth import ApiKeyHeaderAuth, ApiKeyQueryAuth, BasicAuth, BearerTokenAuth
from apiclient.http.encode import encode_body
from apiclient.models import CaseInsensitiveHeaders


class EncodeBodyTests(unittest.TestCase):
    def test_json_body_sets_content_type(self) -> None:
        body, headers = encode_body(json_value={"a": 1})
        self.assertEqual(body, b'{"a":1}')
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_form_body_urlencodes(self) -> None:
        body, headers = encode_body(form=[("a", "1"), ("b", "2")])
        self.assertEqual(body, b"a=1&b=2")
        self.assertIn("application/x-www-form-urlencoded", headers["Content-Type"])

    def test_data_string_and_bytes(self) -> None:
        body_str, _ = encode_body(data="hello")
        body_bytes, _ = encode_body(data=b"hello")
        self.assertEqual(body_str, b"hello")
        self.assertEqual(body_bytes, b"hello")

    def test_binary_file_reads_bytes(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"\x00\x01")
            path = tmp.name
        try:
            body, headers = encode_body(binary_file=path)
            self.assertEqual(body, b"\x00\x01")
            self.assertEqual(headers["Content-Type"], "application/octet-stream")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_binary_file_missing_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            encode_body(binary_file="/no/such/file.bin")

    def test_multiple_body_sources_rejected(self) -> None:
        with self.assertRaises(ValueError):
            encode_body(json_value={}, data="x")

    def test_preserves_existing_headers_copy(self) -> None:
        headers = CaseInsensitiveHeaders({"X-Custom": "1"})
        _, out = encode_body(json_value=[1], headers=headers)
        self.assertEqual(out["X-Custom"], "1")
        self.assertNotIn("Content-Type", headers)


class AuthValidationTests(unittest.TestCase):
    def test_bearer_empty_token_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BearerTokenAuth("   ")

    def test_basic_empty_username_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BasicAuth("", "pass")

    def test_basic_colon_in_username_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BasicAuth("user:name", "pass")

    def test_api_key_header_empty_name(self) -> None:
        with self.assertRaises(ValueError):
            ApiKeyHeaderAuth("  ", "key")

    def test_api_key_header_empty_value(self) -> None:
        with self.assertRaises(ValueError):
            ApiKeyHeaderAuth("X-Key", "  ")

    def test_api_key_query_empty_param(self) -> None:
        with self.assertRaises(ValueError):
            ApiKeyQueryAuth("", "key")

    def test_api_key_query_apply_adds_param(self) -> None:
        auth = ApiKeyQueryAuth("api_key", "secret")
        from apiclient.models import Request

        req = auth.apply(Request("GET", "http://example.test/path"))
        self.assertIn("api_key=secret", req.url)
        self.assertEqual(auth.secrets(), ["secret"])
        self.assertIn("api_key", auth.sensitive_query_params())

    def test_api_key_header_sensitive_names(self) -> None:
        auth = ApiKeyHeaderAuth("X-API-Key", "k")
        self.assertIn("x-api-key", auth.sensitive_header_names())


if __name__ == "__main__":
    unittest.main()
