"""Cursor-based pagination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from apiclient.client import ApiClient
from apiclient.exceptions import PaginationError
from apiclient.pagination.base import Page, extract_items, require_json_object


@dataclass(frozen=True, slots=True)
class CursorPaginator:
    cursor: str | None = None
    cursor_param: str = "cursor"
    limit: int = 25
    limit_param: str = "limit"
    items_key: str = "results"
    next_cursor_key: str = "next_cursor"
    max_pages: int = 10

    def pages(self, client: ApiClient, url: str, **request_kwargs) -> Iterator[Page]:
        base_kwargs = dict(request_kwargs)
        base_params = dict(base_kwargs.pop("params", {}) or {})
        current_cursor = self.cursor
        seen_cursors: set[str | None] = set()
        for page_number in range(1, self.max_pages + 1):
            if current_cursor in seen_cursors:
                raise PaginationError(f"Cursor paginator repeated cursor {current_cursor!r}")
            seen_cursors.add(current_cursor)
            params = dict(base_params)
            params[self.limit_param] = self.limit
            if current_cursor is not None:
                params[self.cursor_param] = current_cursor
            response = client.request("GET", url, params=params, **base_kwargs)
            data = require_json_object(response)
            items = extract_items(data, self.items_key)
            yield Page(page_number, response, data, items)

            next_cursor = data.get(self.next_cursor_key)
            if next_cursor in {None, ""}:
                break
            if not isinstance(next_cursor, str):
                raise PaginationError(f"{self.next_cursor_key!r} must be a string or null")
            current_cursor = next_cursor
