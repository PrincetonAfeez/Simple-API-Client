"""Paginator interface and shared helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Protocol

from apiclient.client import ApiClient
from apiclient.exceptions import PaginationError
from apiclient.models import Response


@dataclass(slots=True)
class Page:
    number: int
    response: Response
    data: dict
    items: list


class Paginator(Protocol):
    def pages(self, client: ApiClient, url: str, **request_kwargs) -> Iterator[Page]:
        ...


def iter_items(pages: Iterable[Page]) -> Iterator[object]:
    for page in pages:
        yield from page.items


def require_json_object(response: Response) -> dict:
    data = response.json()
    if not isinstance(data, dict):
        raise PaginationError("Paginated response must be a JSON object")
    return data


def extract_items(data: dict, items_key: str) -> list:
    value = data.get(items_key)
    if value is None:
        raise PaginationError(f"Paginated response is missing items key {items_key!r}")
    if not isinstance(value, list):
        raise PaginationError(f"Pagination field {items_key!r} must be a list")
    return value
