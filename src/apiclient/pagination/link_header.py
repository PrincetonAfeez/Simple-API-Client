"""RFC 8288-style Link header pagination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from apiclient.client import ApiClient
from apiclient.exceptions import PaginationError
from apiclient.pagination.base import Page, extract_items, require_json_object


@dataclass(frozen=True, slots=True)
class LinkHeaderPaginator:
    items_key: str = "results"
    max_pages: int = 10

    def pages(self, client: ApiClient, url: str, **request_kwargs) -> Iterator[Page]:
        next_url: str | None = url
        seen_urls: set[str] = set()
        for page_number in range(1, self.max_pages + 1):
            if next_url is None:
                break
            if next_url in seen_urls:
                raise PaginationError(f"Link paginator revisited URL {next_url!r}")
            seen_urls.add(next_url)
            response = client.request("GET", next_url, **request_kwargs)
            data = require_json_object(response)
            items = extract_items(data, self.items_key)
            yield Page(page_number, response, data, items)

            links = parse_link_header(response.headers.get("Link", "") or "")
            next_url = links.get("next")


def parse_link_header(value: str) -> dict[str, str]:
    links: dict[str, str] = {}
    if not value:
        return links
    for part in _split_link_header(value):
        section = part.strip()
        if not section:
            continue
        if not section.startswith("<") or ">" not in section:
            raise PaginationError(f"Malformed Link header section: {section!r}")
        url, rest = section[1:].split(">", 1)
        rel_value: str | None = None
        for param in rest.split(";"):
            param = param.strip()
            if param.startswith("rel="):
                rel_value = param.split("=", 1)[1].strip('"')
        if rel_value:
            # RFC 8288 §3.3: rel may carry multiple space-separated relation
            # types; expose each so callers can look up "next", "prev", etc.
            for token in rel_value.split():
                links[token] = url
    return links


def _split_link_header(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_quotes = False
    in_angle = False
    for char in value:
        if char == '"' and not in_angle:
            in_quotes = not in_quotes
        elif char == "<" and not in_quotes:
            in_angle = True
        elif char == ">" and not in_quotes:
            in_angle = False
        if char == "," and not in_quotes and not in_angle:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return parts
