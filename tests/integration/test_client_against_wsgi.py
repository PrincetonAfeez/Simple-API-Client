"""Tests for the client against the WSGI server."""

from __future__ import annotations

import unittest

from apiclient.client import ApiClient
from apiclient.transport import RawSocketTransport, UrllibTransport
from tests.helpers import wsgi_server


class ClientAgainstWSGITests(unittest.TestCase):
    def test_raw_transport_get_health(self) -> None:
        with wsgi_server() as base_url:
            response = ApiClient(transport=RawSocketTransport()).request("GET", f"{base_url}/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_urllib_transport_get_health(self) -> None:
        with wsgi_server() as base_url:
            response = ApiClient(transport=UrllibTransport()).request("GET", f"{base_url}/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["server"], "raw-wsgi")


if __name__ == "__main__":
    unittest.main()
