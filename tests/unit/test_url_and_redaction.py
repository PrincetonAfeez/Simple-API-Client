"""URL parsing and redaction exhaustive tests."""

from __future__ import annotations

import os
import unittest

from apiclient.exceptions import InvalidUrlError
from apiclient.http.redirects import RedirectPolicy, _strip_sensitive_query_params
from apiclient.http.url import merge_query_params, parse_url, require_http_url
from apiclient.models import CaseInsensitiveHeaders, Request, Response
from apiclient.observability.redaction import (
    redact_headers,
    redact_secret,
    redact_url,
    sensitive_query_param_names,
)


class UrlTests(unittest.TestCase):
    def test_parse_url_ipv6_host_header(self) -> None:
        parsed = parse_url("http://[::1]:8080/path")
        self.assertEqual(parsed.hostname, "::1")
        self.assertIn("[::1]", parsed.host_header)

    def test_parse_url_default_https_port(self) -> None:
        parsed = parse_url("https://example.test/path")
        self.assertEqual(parsed.port, 443)
        self.assertEqual(parsed.host_header, "example.test")

    def test_reject_credentials_in_url(self) -> None:
        with self.assertRaises(InvalidUrlError):
            parse_url("http://user:pass@example.test/")

    def test_reject_missing_hostname(self) -> None:
        with self.assertRaises(InvalidUrlError):
            parse_url("http:///path")

    def test_reject_unsupported_scheme(self) -> None:
        with self.assertRaises(InvalidUrlError):
            parse_url("ftp://example.test/")

    def test_require_http_url_returns_unchanged(self) -> None:
        url = "http://example.test/x"
        self.assertEqual(require_http_url(url), url)

    def test_merge_query_params_sequence(self) -> None:
        url = merge_query_params("http://x/?a=1", [("b", "2")])
        self.assertIn("a=1", url)
        self.assertIn("b=2", url)


class RedactionTests(unittest.TestCase):
    def test_redact_empty_secret(self) -> None:
        self.assertEqual(redact_secret(None), "[redacted]")
        self.assertEqual(redact_secret(""), "[redacted]")

    def test_redact_short_value(self) -> None:
        self.assertEqual(redact_secret("short"), "...redacted")

    def test_redact_basic_header(self) -> None:
        self.assertEqual(redact_secret("Basic abcdef"), "Basic ...redacted")

    def test_redact_url_with_userinfo(self) -> None:
        url = redact_url("http://user:pass@example.test/path?token=secret&ok=1")
        self.assertNotIn("secret", url)
        self.assertIn("<redacted>", url)

    def test_redact_url_fast_path_no_query(self) -> None:
        url = "http://example.test/path"
        self.assertIs(redact_url(url), url)

    def test_sensitive_query_from_env(self) -> None:
        os.environ["APICLIENT_REDACT_PARAMS"] = "custom_secret"
        sensitive_query_param_names.cache_clear()
        try:
            names = sensitive_query_param_names()
            self.assertIn("custom_secret", names)
        finally:
            del os.environ["APICLIENT_REDACT_PARAMS"]
            sensitive_query_param_names.cache_clear()

    def test_redact_headers_masks_authorization(self) -> None:
        headers = CaseInsensitiveHeaders({"Authorization": "Bearer abcdefghij"})
        redacted = redact_headers(headers)
        self.assertNotIn("abcdefghij", redacted["Authorization"])


class RedirectStripTests(unittest.TestCase):
    def test_strip_no_params_returns_url(self) -> None:
        url = "http://a.test/path?token=x"
        self.assertEqual(_strip_sensitive_query_params(url, frozenset()), url)

    def test_redirect_without_location_in_next_request(self) -> None:
        policy = RedirectPolicy()
        request = Request("GET", "http://a.test/")
        response = Response(
            302,
            "Found",
            CaseInsensitiveHeaders(),
            b"",
            "http://a.test/",
        )
        with self.assertRaises(Exception):
            policy.next_request(request, response)


if __name__ == "__main__":
    unittest.main()
