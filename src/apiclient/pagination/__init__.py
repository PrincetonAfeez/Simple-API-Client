"""Pagination strategies behind a single :class:`Paginator` protocol.

Each strategy yields :class:`Page` objects lazily so callers can stop iteration
at any point without fetching further pages:

* :class:`OffsetPaginator` — ``offset`` / ``limit`` query params.
* :class:`PageNumberPaginator` — ``page`` / ``per_page`` query params.
* :class:`CursorPaginator` — opaque cursor token returned by the server.
* :class:`LinkHeaderPaginator` — RFC 8288 ``Link`` header with ``rel="next"``.

All four guard against cycles and cap iteration with ``max_pages``. The CLI
``paginate`` subcommand drives them with script-friendly JSON output.
"""

from .base import Page, Paginator, iter_items
from .cursor import CursorPaginator
from .link_header import LinkHeaderPaginator, parse_link_header
from .offset import OffsetPaginator
from .page import PageNumberPaginator

__all__ = [
    "CursorPaginator",
    "LinkHeaderPaginator",
    "OffsetPaginator",
    "Page",
    "PageNumberPaginator",
    "Paginator",
    "iter_items",
    "parse_link_header",
]
