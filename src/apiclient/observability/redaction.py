"""Credential redaction utilities used by trace, logs, curl, and output."""

from __future__ import annotations

import os
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from apiclient.models import CaseInsensitiveHeaders

SENSITIVE_HEADER_NAMES = {
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "api-key",
    "apikey",
}

SENSITIVE_QUERY_NAMES = {
    "api_key",
    "apikey",
    "access_token",
    "token",
    "key",
}


@lru_cache(maxsize=1)
def sensitive_query_param_names() -> frozenset[str]:
    """Built-in sensitive query names plus ``APICLIENT_REDACT_PARAMS`` (comma-separated)."""

    names = set(SENSITIVE_QUERY_NAMES)
    extra = os.environ.get("APICLIENT_REDACT_PARAMS", "").strip()
    if extra:
        names.update(part.strip().lower() for part in extra.split(",") if part.strip())
    return frozenset(names)


def redact_secret(value: str | None) -> str:
    if not value:
        return "[redacted]"
    if value.lower().startswith("bearer "):
        token = value[7:]
        prefix = token[:4] if len(token) >= 4 else ""
        return f"Bearer {prefix}...redacted"
    if value.lower().startswith("basic "):
        return "Basic ...redacted"
    if len(value) <= 8:
        return "...redacted"
    return f"{value[:4]}...redacted"


def redact_headers(headers: CaseInsensitiveHeaders | dict[str, str]) -> CaseInsensitiveHeaders:
    redacted = CaseInsensitiveHeaders()
    items = headers.items()
    for key, value in items:
        if key.lower() in SENSITIVE_HEADER_NAMES:
            redacted[key] = redact_secret(value)
        else:
            redacted[key] = value
    return redacted


def redact_url(url: str) -> str:
    split = urlsplit(url)
    needs_userinfo_redaction = split.username is not None or split.password is not None
    if not split.query and not needs_userinfo_redaction:
        # Fast path: nothing to redact; preserve the original byte-for-byte
        # (including any trailing "?" that urlunsplit would otherwise drop).
        return url
    netloc = _redact_netloc(split)
    if not split.query:
        return urlunsplit((split.scheme, netloc, split.path, "", split.fragment))
    pairs = []
    for key, value in parse_qsl(split.query, keep_blank_values=True):
        if key.lower() in sensitive_query_param_names():
            pairs.append((key, redact_secret(value)))
        else:
            pairs.append((key, value))
    return urlunsplit((split.scheme, netloc, split.path, urlencode(pairs), split.fragment))


def _redact_netloc(split) -> str:  # noqa: ANN001
    """Replace any ``user[:password]@`` prefix with ``<redacted>@``."""

    if split.username is None and split.password is None:
        return split.netloc
    host = split.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if split.port is not None:
        host = f"{host}:{split.port}"
    return f"<redacted>@{host}"


