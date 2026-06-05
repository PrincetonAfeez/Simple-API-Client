"""Offset/limit pagination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from apiclient.client import ApiClient
from apiclient.exceptions import PaginationError
from apiclient.pagination.base import Page, extract_items, require_json_object


@dataclass(frozen=True, slots=True)
class OffsetPaginator:
    limit: int = 25
    start_offset: int = 0
    offset_param: str = "offset"
    limit_param: str = "limit"
    items_key: str = "results"
    next_offset_key: str = "next_offset"
    max_pages: int = 10

    def pages(self, client: ApiClient, url: str, **request_kwargs) -> Iterator[Page]:
        base_kwargs = dict(request_kwargs)
        base_params = dict(base_kwargs.pop("params", {}) or {})
        offset = self.start_offset
        seen_offsets: set[int] = set()
        for page_number in range(1, self.max_pages + 1):
            if offset in seen_offsets:
                raise PaginationError(f"Offset paginator repeated offset {offset}")
            seen_offsets.add(offset)
            params = dict(base_params)
            params[self.offset_param] = offset
            params[self.limit_param] = self.limit
            response = client.request("GET", url, params=params, **base_kwargs)
            data = require_json_object(response)
            items = extract_items(data, self.items_key)
            yield Page(page_number, response, data, items)

            next_offset = data.get(self.next_offset_key)
            if next_offset is None:
                break
            if not isinstance(next_offset, int):
                raise PaginationError(f"{self.next_offset_key!r} must be an integer or null")
            offset = next_offset
