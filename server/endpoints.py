"""Endpoint handlers for the raw WSGI demo app."""

from __future__ import annotations

import base64
import json
from collections import defaultdict
from urllib.parse import parse_qs, urlencode

ITEMS = [{"id": i, "name": f"item-{i}"} for i in range(1, 101)]
# Demo-only in-memory counter for /flaky (not thread-safe across WSGI workers).
FLAKY_COUNTS: defaultdict[str, int] = defaultdict(int)


class _BadRequest(Exception):
    """Raised by endpoint handlers when a query value cannot be parsed."""


def _int_query(query: dict[str, list[str]], key: str, default: int) -> int:
    """Parse a query parameter as int, returning ``default`` when absent/empty.

    Raises :class:`_BadRequest` for non-integer values so the dispatcher can
    surface a 400 instead of a 500.
    """

    raw = first(query, key, None)
    if not raw:
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise _BadRequest(
            f"query parameter {key!r} must be an integer; got {raw!r}"
        ) from exc


def dispatch(environ) -> tuple[str, list[tuple[str, str]], bytes]:
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET")
    query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)

    try:
        if path == "/health":
            return json_response({"status": "ok", "server": "raw-wsgi", "method": method})
        if path == "/private":
            return private_endpoint(environ, query)
        if path == "/items" or path.startswith("/items/"):
            return items_endpoint(environ, path, query)
        if path == "/flaky":
            return flaky_endpoint(environ, query)
        if path == "/redirect":
            return redirect_endpoint(query)
        if path == "/echo":
            return echo_endpoint(environ, query)
        if path == "/reset-flaky":
            FLAKY_COUNTS.clear()
            return json_response({"reset": True})
        return json_response({"error": "not found", "path": path}, status="404 Not Found")
    except _BadRequest as exc:
        return json_response({"error": str(exc)}, status="400 Bad Request")


def private_endpoint(environ, query: dict[str, list[str]]) -> tuple[str, list[tuple[str, str]], bytes]:
    auth = environ.get("HTTP_AUTHORIZATION", "")
    api_key = environ.get("HTTP_X_API_KEY", "")
    query_key = first(query, "api_key")
    expected_basic = "Basic " + base64.b64encode(b"demo:secret").decode("ascii")
    allowed = {
        auth == "Bearer demo-token",
        auth == expected_basic,
        api_key == "demo-key",
        query_key == "demo-key",
    }
    if any(allowed):
        return json_response({"authenticated": True})
    return json_response(
        {"authenticated": False, "error": "missing or invalid credentials"},
        status="401 Unauthorized",
        extra_headers=[("WWW-Authenticate", "Bearer")],
    )


def items_endpoint(environ, path: str, query: dict[str, list[str]]) -> tuple[str, list[tuple[str, str]], bytes]:
    if path.startswith("/items/"):
        try:
            item_id = int(path.rsplit("/", 1)[1])
        except ValueError:
            return json_response({"error": "invalid item id"}, status="400 Bad Request")
        for item in ITEMS:
            if item["id"] == item_id:
                return json_response(item)
        return json_response({"error": "item not found"}, status="404 Not Found")

    limit = _int_query(query, "limit", _int_query(query, "per_page", 25))
    if "cursor" in query or first(query, "pagination") == "cursor":
        start = _int_query(query, "cursor", 0)
        results = ITEMS[start : start + limit]
        next_cursor = str(start + limit) if start + limit < len(ITEMS) else None
        return json_response({"results": results, "next_cursor": next_cursor})

    if "page" in query:
        page = _int_query(query, "page", 1)
        per_page = _int_query(query, "per_page", limit)
        start = (page - 1) * per_page
        results = ITEMS[start : start + per_page]
        next_page = page + 1 if start + per_page < len(ITEMS) else None
        return json_response({"results": results, "page": page, "next_page": next_page})

    offset = _int_query(query, "offset", 0)
    results = ITEMS[offset : offset + limit]
    next_offset = offset + limit if offset + limit < len(ITEMS) else None
    headers: list[tuple[str, str]] = []
    if first(query, "pagination") == "link" or first(query, "link") == "true":
        if next_offset is not None:
            headers.append(("Link", f"<{build_items_url(environ, query, next_offset, limit)}>; rel=\"next\""))
        next_offset_payload = None
    else:
        next_offset_payload = next_offset
    return json_response(
        {"results": results, "offset": offset, "limit": limit, "next_offset": next_offset_payload},
        extra_headers=headers,
    )


_STATUS_REASONS = {
    301: "Moved Permanently",
    302: "Found",
    303: "See Other",
    307: "Temporary Redirect",
    308: "Permanent Redirect",
    429: "Too Many Requests",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}


def _status_line(code: int, fallback: str) -> str:
    return f"{code} {_STATUS_REASONS.get(code, fallback)}"


def flaky_endpoint(environ, query: dict[str, list[str]]) -> tuple[str, list[tuple[str, str]], bytes]:
    key = first(query, "key", environ.get("REMOTE_ADDR", "default"))
    succeed_after = _int_query(query, "succeed_after", 2)
    status_code = _int_query(query, "status", 503)
    FLAKY_COUNTS[key] += 1
    attempt = FLAKY_COUNTS[key]
    if attempt < succeed_after:
        return json_response(
            {"ok": False, "attempt": attempt, "succeed_after": succeed_after},
            status=_status_line(status_code, "Service Unavailable"),
            extra_headers=[("Retry-After", first(query, "retry_after", "0"))],
        )
    return json_response({"ok": True, "attempt": attempt})


def redirect_endpoint(query: dict[str, list[str]]) -> tuple[str, list[tuple[str, str]], bytes]:
    location = first(query, "to", "/health")
    status_code = _int_query(query, "status", 302)
    return json_response(
        {"redirect": location},
        status=_status_line(status_code, "Found"),
        extra_headers=[("Location", location)],
    )


def echo_endpoint(environ, query: dict[str, list[str]]) -> tuple[str, list[tuple[str, str]], bytes]:
    raw_length = environ.get("CONTENT_LENGTH") or "0"
    try:
        length = int(raw_length)
    except (TypeError, ValueError) as exc:
        raise _BadRequest(
            f"CONTENT_LENGTH must be an integer; got {raw_length!r}"
        ) from exc
    body = environ["wsgi.input"].read(length) if length else b""
    headers = {
        key[5:].replace("_", "-").title(): value
        for key, value in environ.items()
        if key.startswith("HTTP_")
    }
    return json_response(
        {
            "method": environ.get("REQUEST_METHOD"),
            "path": environ.get("PATH_INFO"),
            "query": query,
            "headers": headers,
            "body": body.decode("utf-8", errors="replace"),
        }
    )


def json_response(
    payload: object,
    *,
    status: str = "200 OK",
    extra_headers: list[tuple[str, str]] | None = None,
) -> tuple[str, list[tuple[str, str]], bytes]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
    ]
    if extra_headers:
        headers.extend(extra_headers)
    return status, headers, body


def first(query: dict[str, list[str]], key: str, default: str | None = None) -> str | None:
    values = query.get(key)
    if not values:
        return default
    return values[0]


def build_items_url(environ, query: dict[str, list[str]], offset: int, limit: int) -> str:
    scheme = environ.get("wsgi.url_scheme", "http")
    host = environ.get("HTTP_HOST") or f"{environ.get('SERVER_NAME')}:{environ.get('SERVER_PORT')}"
    pairs = []
    for key, values in query.items():
        if key in {"offset", "limit"}:
            continue
        for value in values:
            pairs.append((key, value))
    pairs.extend([("offset", str(offset)), ("limit", str(limit))])
    return f"{scheme}://{host}/items?{urlencode(pairs)}"
