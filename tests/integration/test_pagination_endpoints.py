"""Tests for the pagination endpoints."""

from __future__ import annotations

import unittest

from apiclient.client import ApiClient
from apiclient.pagination import LinkHeaderPaginator, OffsetPaginator, iter_items
from tests.helpers import wsgi_server


class PaginationEndpointTests(unittest.TestCase):
    def test_offset_pagination_against_wsgi(self) -> None:
        with wsgi_server() as base_url:
            pages = OffsetPaginator(limit=10, max_pages=2).pages(ApiClient(), f"{base_url}/items")
            items = list(iter_items(pages))
        self.assertEqual(len(items), 20)
        self.assertEqual(items[0]["id"], 1)

    def test_link_pagination_against_wsgi(self) -> None:
        with wsgi_server() as base_url:
            pages = LinkHeaderPaginator(max_pages=2).pages(
                ApiClient(),
                f"{base_url}/items?pagination=link&limit=5",
            )
            items = list(iter_items(pages))
        self.assertEqual(len(items), 10)


if __name__ == "__main__":
    unittest.main()
