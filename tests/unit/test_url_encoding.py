"""Tests for the URL encoding."""

from __future__ import annotations

import unittest

from apiclient.http.url import merge_query_params, parse_url


class UrlEncodingTests(unittest.TestCase):
    def test_parse_url_infers_default_ports_and_target(self) -> None:
        parsed = parse_url("https://example.test/path?q=hello")
        self.assertEqual(parsed.port, 443)
        self.assertEqual(parsed.target, "/path?q=hello")
        self.assertEqual(parsed.host_header, "example.test")

    def test_merge_query_params_percent_encodes(self) -> None:
        url = merge_query_params("http://example.test/search?q=old", {"name": "Ada Lovelace", "tag": "a&b"})
        self.assertIn("name=Ada+Lovelace", url)
        self.assertIn("tag=a%26b", url)


if __name__ == "__main__":
    unittest.main()
