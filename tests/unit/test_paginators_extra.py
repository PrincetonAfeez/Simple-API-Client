"""Tests for the paginators extra."""

from __future__ import annotations

import json
import unittest

from apiclient.exceptions import PaginationError
from apiclient.models import CaseInsensitiveHeaders, Response
from apiclient.pagination import CursorPaginator, PageNumberPaginator


def _resp(payload: dict) -> Response:
    body = json.dumps(payload).encode("utf-8")
    return Response(200, "OK", CaseInsensitiveHeaders({"Content-Type": "application/json"}), body, "http://x")


class _Recorder:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)
        self.calls: list[tuple[str, str, dict]] = []

    def request(self, method, url, **kwargs):  # noqa: ANN001
        self.calls.append((method, url, kwargs))
        return _resp(self.payloads.pop(0))


class CursorPaginatorTests(unittest.TestCase):
    def test_follows_next_cursor_until_null(self) -> None:
        client = _Recorder(
            [
                {"results": [{"id": 1}], "next_cursor": "abc"},
                {"results": [{"id": 2}], "next_cursor": None},
            ]
        )
        pages = list(CursorPaginator(limit=1).pages(client, "http://x/items"))
        self.assertEqual([p.number for p in pages], [1, 2])
        self.assertEqual([call[2]["params"].get("cursor") for call in client.calls], [None, "abc"])

    def test_repeated_cursor_raises_error(self) -> None:
        client = _Recorder(
            [
                {"results": [{"id": 1}], "next_cursor": "abc"},
                {"results": [{"id": 2}], "next_cursor": "abc"},
            ]
        )
        with self.assertRaises(PaginationError):
            list(CursorPaginator(limit=1).pages(client, "http://x/items"))


class PageNumberPaginatorTests(unittest.TestCase):
    def test_follows_next_page_until_null(self) -> None:
        client = _Recorder(
            [
                {"results": [{"id": 1}], "next_page": 2},
                {"results": [{"id": 2}], "next_page": None},
            ]
        )
        pages = list(PageNumberPaginator(per_page=1).pages(client, "http://x/items"))
        self.assertEqual([p.number for p in pages], [1, 2])

    def test_cycle_detection(self) -> None:
        client = _Recorder(
            [
                {"results": [{"id": 1}], "next_page": 1},
            ]
        )
        with self.assertRaises(PaginationError):
            list(PageNumberPaginator(per_page=1).pages(client, "http://x/items"))


if __name__ == "__main__":
    unittest.main()
