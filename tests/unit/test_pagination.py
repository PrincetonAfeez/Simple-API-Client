"""Tests for the pagination."""

from __future__ import annotations

import json
import unittest

from apiclient.models import CaseInsensitiveHeaders, Response
from apiclient.pagination import LinkHeaderPaginator, OffsetPaginator, iter_items, parse_link_header


class FakeClient:
    def __init__(self) -> None:
        self.calls = []

    def request(self, method, url, **kwargs):  # noqa: ANN001
        self.calls.append((method, url, kwargs))
        offset = kwargs["params"]["offset"]
        limit = kwargs["params"]["limit"]
        next_offset = offset + limit if offset + limit < 5 else None
        items = [{"id": i} for i in range(offset, min(offset + limit, 5))]
        body = json.dumps({"results": items, "next_offset": next_offset}).encode("utf-8")
        return Response(200, "OK", CaseInsensitiveHeaders({"Content-Type": "application/json"}), body, url)


class LinkFakeClient:
    def __init__(self) -> None:
        self.count = 0

    def request(self, method, url, **kwargs):  # noqa: ANN001
        self.count += 1
        headers = CaseInsensitiveHeaders({"Content-Type": "application/json"})
        if self.count == 1:
            headers["Link"] = '<http://example.test/page2>; rel="next"'
        body = json.dumps({"results": [{"page": self.count}]}).encode("utf-8")
        return Response(200, "OK", headers, body, url)


class PaginationTests(unittest.TestCase):
    def test_offset_paginator_is_lazy_and_preserves_filters(self) -> None:
        client = FakeClient()
        paginator = OffsetPaginator(limit=2, max_pages=3)
        pages = paginator.pages(client, "http://example.test/items", params={"kind": "demo"})
        first = next(pages)
        self.assertEqual(first.items, [{"id": 0}, {"id": 1}])
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0][2]["params"]["kind"], "demo")
        rest_items = list(iter_items([first, *pages]))
        self.assertEqual(len(rest_items), 5)

    def test_link_header_parse_and_paginator(self) -> None:
        links = parse_link_header('<http://example.test/next>; rel="next", <x>; rel="last"')
        self.assertEqual(links["next"], "http://example.test/next")
        client = LinkFakeClient()
        pages = list(LinkHeaderPaginator(max_pages=5).pages(client, "http://example.test/items"))
        self.assertEqual(len(pages), 2)


if __name__ == "__main__":
    unittest.main()
