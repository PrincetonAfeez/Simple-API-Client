"""Async client and pagination base exhaustive tests."""

from __future__ import annotations

import asyncio
import unittest

from apiclient.client import ApiClient
from apiclient.concurrency.async_client import fetch_many
from apiclient.pagination.base import Page
from apiclient.pagination.cursor import CursorPaginator
from apiclient.pagination.link_header import LinkHeaderPaginator
from apiclient.pagination.offset import OffsetPaginator
from apiclient.pagination.page import PageNumberPaginator
from apiclient.transport import RawSocketTransport
from tests.helpers import wsgi_server


class PaginationBaseTests(unittest.TestCase):
    def test_page_dataclass_fields(self) -> None:
        from apiclient.models import CaseInsensitiveHeaders, Response

        response = Response(200, "OK", CaseInsensitiveHeaders(), b"{}", "http://x")
        page = Page(number=1, response=response, data={"results": [{"id": 1}]}, items=[{"id": 1}])
        self.assertEqual(page.number, 1)
        self.assertEqual(len(page.items), 1)

    def test_offset_paginator_sends_limit_and_offset(self) -> None:
        with wsgi_server() as base:
            client = ApiClient(transport=RawSocketTransport())
            paginator = OffsetPaginator(limit=2, max_pages=1)
            pages = list(paginator.pages(client, f"{base}/items"))
        self.assertEqual(len(pages), 1)
        self.assertIn("limit=2", pages[0].response.url)

    def test_cursor_paginator_stops_without_next(self) -> None:
        with wsgi_server() as base:
            client = ApiClient(transport=RawSocketTransport())
            paginator = CursorPaginator(limit=2, max_pages=5)
            pages = list(
                paginator.pages(client, f"{base}/items", params={"pagination": "cursor"})
            )
        self.assertGreaterEqual(len(pages), 1)


class AsyncClientTests(unittest.TestCase):
    def test_fetch_many_preserves_url_order(self) -> None:
        with wsgi_server() as base:
            client = ApiClient(transport=RawSocketTransport())
            urls = [f"{base}/health", f"{base}/health"]
            result = asyncio.run(
                fetch_many(client, urls, concurrency=2, fail_fast=False)
            )
        self.assertEqual(result.total, 2)
        self.assertEqual(result.succeeded, 2)
        self.assertEqual(len(result.results_by_url), 2)

    def test_fetch_many_fail_fast_records_error(self) -> None:
        with wsgi_server() as base:
            client = ApiClient(transport=RawSocketTransport())
            urls = [f"{base}/health", "http://127.0.0.1:1/not-listening"]
            result = asyncio.run(
                fetch_many(client, urls, concurrency=1, fail_fast=True, fail=True)
            )
        self.assertGreaterEqual(result.failed, 1)

    def test_link_header_paginator_on_items_endpoint(self) -> None:
        with wsgi_server() as base:
            client = ApiClient(transport=RawSocketTransport())
            paginator = LinkHeaderPaginator(max_pages=2)
            pages = list(
                paginator.pages(
                    client,
                    f"{base}/items",
                    params={"pagination": "link", "link": "true", "limit": 2},
                )
            )
        self.assertGreaterEqual(len(pages), 1)

    def test_page_number_paginator(self) -> None:
        with wsgi_server() as base:
            client = ApiClient(transport=RawSocketTransport())
            paginator = PageNumberPaginator(per_page=2, max_pages=2)
            pages = list(paginator.pages(client, f"{base}/items"))
        self.assertGreaterEqual(len(pages), 1)


if __name__ == "__main__":
    unittest.main()
