"""Tests for the urllib transport."""

from __future__ import annotations

import unittest

from apiclient.client import ApiClient
from apiclient.transport import UrllibTransport
from tests.helpers import wsgi_server


class UrllibTransportIntegrationTests(unittest.TestCase):
    def test_urllib_transport_follows_redirect(self) -> None:
        with wsgi_server() as base_url:
            response = ApiClient(transport=UrllibTransport()).request(
                "GET", f"{base_url}/redirect?to=/health"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(len(response.history), 1)

    def test_urllib_transport_returns_404_without_following(self) -> None:
        with wsgi_server() as base_url:
            response = ApiClient(transport=UrllibTransport()).request(
                "GET", f"{base_url}/missing"
            )
        self.assertEqual(response.status_code, 404)

    def test_urllib_transport_framing_is_derived(self) -> None:
        with wsgi_server() as base_url:
            response = ApiClient(transport=UrllibTransport()).request(
                "GET", f"{base_url}/health"
            )
        self.assertIn(response.framing, {"content-length", "chunked"})


if __name__ == "__main__":
    unittest.main()
