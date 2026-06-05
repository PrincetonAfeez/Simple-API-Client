"""Tests for the chunked test server."""

from __future__ import annotations

import unittest

from apiclient.client import ApiClient
from tests.helpers import chunked_server


class ChunkedServerTests(unittest.TestCase):
    def test_raw_transport_decodes_chunked_response(self) -> None:
        with chunked_server() as base_url:
            response = ApiClient().request("GET", f"{base_url}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.framing, "chunked")
        self.assertEqual(response.json()["message"], "hello from chunks")


if __name__ == "__main__":
    unittest.main()
