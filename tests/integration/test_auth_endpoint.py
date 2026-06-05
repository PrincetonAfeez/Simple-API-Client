"""Tests for the authentication endpoint."""

from __future__ import annotations

import unittest

from apiclient.auth import BearerTokenAuth
from apiclient.client import ApiClient
from tests.helpers import wsgi_server


class AuthEndpointTests(unittest.TestCase):
    def test_bearer_auth_success(self) -> None:
        with wsgi_server() as base_url:
            response = ApiClient().request(
                "GET",
                f"{base_url}/private",
                auth=BearerTokenAuth("demo-token"),
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["authenticated"])

    def test_missing_auth_fails(self) -> None:
        with wsgi_server() as base_url:
            response = ApiClient().request("GET", f"{base_url}/private")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
