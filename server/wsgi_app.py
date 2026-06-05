"""Raw WSGI app: environ in, start_response out, iterable of bytes back."""

from __future__ import annotations

try:
    from .endpoints import dispatch
except ImportError:  # pragma: no cover - allows running this file directly
    from endpoints import dispatch


def application(environ, start_response):
    """The exact interface Django also speaks behind a WSGI server."""

    status, headers, body = dispatch(environ)
    start_response(status, headers)
    return [body]
