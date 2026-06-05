"""Tests for the redirect policy."""

from __future__ import annotations

import unittest

from apiclient.client import ApiClient
from tests.helpers import wsgi_server


class RedirectPolicyTests(unittest.TestCase):
    def test_redirect_is_followed_and_recorded(self) -> None:
        with wsgi_server() as base_url:
            response = ApiClient().request("GET", f"{base_url}/redirect?to=/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(len(response.history), 1)
        self.assertEqual(response.history[0].status_code, 302)


if __name__ == "__main__":
    unittest.main()
