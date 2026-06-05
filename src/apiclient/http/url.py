"""URL parsing and query-string helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from apiclient.exceptions import InvalidUrlError


@dataclass(frozen=True, slots=True)
class ParsedUrl:
    scheme: str
    hostname: str
    port: int
    path: str
    query: str
    target: str
    host_header: str


def require_http_url(url: str) -> str:
    """Validate an absolute http(s) URL and return it unchanged."""

    parse_url(url)
    return url


def parse_url(url: str) -> ParsedUrl:
    split = urlsplit(url)
    if split.scheme not in {"http", "https"}:
        raise InvalidUrlError(f"Unsupported URL scheme in {url!r}; expected http or https")
    if not split.hostname:
        raise InvalidUrlError(f"URL is missing a hostname: {url!r}")
    if split.username is not None or split.password is not None:
        # Silently demoting `user:pass@host` to host-only would leave the user
        # thinking they were authenticated. Force them to use --basic / BasicAuth.
        raise InvalidUrlError(
            "URL must not carry credentials (user:pass@host); "
            "use --basic or BasicAuth instead"
        )

    default_port = 443 if split.scheme == "https" else 80
    port = split.port or default_port
    path = split.path or "/"
    target = path
    if split.query:
        target = f"{target}?{split.query}"

    needs_port = port != default_port
    host = split.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    host_header = f"{host}:{port}" if needs_port else host

    return ParsedUrl(
        scheme=split.scheme,
        hostname=split.hostname,
        port=port,
        path=path,
        query=split.query,
        target=target,
        host_header=host_header,
    )


def merge_query_params(
    url: str,
    params: Mapping[str, object] | Sequence[tuple[str, object]] | None,
) -> str:
    if not params:
        return url
    split = urlsplit(url)
    pairs: list[tuple[str, object]] = list(parse_qsl(split.query, keep_blank_values=True))
    if hasattr(params, "items"):
        pairs.extend((key, value) for key, value in params.items())  # type: ignore[union-attr]
    else:
        pairs.extend(params)
    query = urlencode(pairs, doseq=True)
    return urlunsplit((split.scheme, split.netloc, split.path, query, split.fragment))


def add_query_param(url: str, name: str, value: str) -> str:
    return merge_query_params(url, [(name, value)])


def resolve_redirect_url(current_url: str, location: str) -> str:
    return urljoin(current_url, location)
