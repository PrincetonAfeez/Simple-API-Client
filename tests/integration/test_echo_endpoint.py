"""Tests for the echo endpoint."""

from __future__ import annotations

import unittest

from apiclient.client import ApiClient
from tests.helpers import wsgi_server


class EchoEndpointTests(unittest.TestCase):
    def test_post_echoes_method_path_headers_and_json_body(self) -> None:
        with wsgi_server() as base_url:
            response = ApiClient().request(
                "POST",
                f"{base_url}/echo",
                json={"name": "Ada"},
                headers=["X-Trace-Id: 123"],
            )
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["method"], "POST")
        self.assertEqual(body["path"], "/echo")
        self.assertIn("X-Trace-Id", body["headers"])
        self.assertEqual(body["headers"]["X-Trace-Id"], "123")
        self.assertEqual(body["body"], '{"name":"Ada"}')

    def test_get_with_query_is_echoed_as_dict(self) -> None:
        with wsgi_server() as base_url:
            response = ApiClient().request(
                "GET",
                f"{base_url}/echo",
                params=[("k", "v"), ("k", "v2")],
            )
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["method"], "GET")
        self.assertEqual(body["query"], {"k": ["v", "v2"]})


class WebInputValidationTests(unittest.TestCase):
    def test_items_with_non_integer_limit_returns_400(self) -> None:
        with wsgi_server() as base_url:
            response = ApiClient().request("GET", f"{base_url}/items?limit=abc")
        self.assertEqual(response.status_code, 400)
        self.assertIn("limit", response.json()["error"])

    def test_flaky_with_non_integer_succeed_after_returns_400(self) -> None:
        with wsgi_server() as base_url:
            response = ApiClient().request(
                "GET", f"{base_url}/flaky?key=t&succeed_after=soon"
            )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
