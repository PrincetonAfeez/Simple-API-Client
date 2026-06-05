"""Page-number pagination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from apiclient.client import ApiClient
from apiclient.exceptions import PaginationError
from apiclient.pagination.base import Page, extract_items, require_json_object


@dataclass(frozen=True, slots=True)
class PageNumberPaginator:
    page: int = 1
    per_page: int = 25
    page_param: str = "page"
    per_page_param: str = "per_page"
    items_key: str = "results"
    next_page_key: str = "next_page"
    max_pages: int = 10

    def pages(self, client: ApiClient, url: str, **request_kwargs) -> Iterator[Page]:
        base_kwargs = dict(request_kwargs)
        base_params = dict(base_kwargs.pop("params", {}) or {})
        current_page = self.page
        seen_pages: set[int] = set()
        for page_number in range(1, self.max_pages + 1):
            if current_page in seen_pages:
                raise PaginationError(f"Page paginator repeated page {current_page}")
            seen_pages.add(current_page)
            params = dict(base_params)
            params[self.page_param] = current_page
            params[self.per_page_param] = self.per_page
            response = client.request("GET", url, params=params, **base_kwargs)
            data = require_json_object(response)
            items = extract_items(data, self.items_key)
            yield Page(page_number, response, data, items)

            next_page = data.get(self.next_page_key)
            if next_page is None:
                break
            if not isinstance(next_page, int):
                raise PaginationError(f"{self.next_page_key!r} must be an integer or null")
            current_page = next_page
