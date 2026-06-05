"""Dataclass models used across the client stack."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Iterable, Mapping


class CaseInsensitiveHeaders(dict):
    """Small case-insensitive mapping for HTTP headers.

    The original casing of the most recent assignment is preserved for display,
    while lookups are normalized to lowercase.
    """

    def __init__(self, values: Mapping[str, str] | Iterable[tuple[str, str]] | None = None):
        super().__init__()
        self._keys: dict[str, str] = {}
        if values:
            items = values.items() if hasattr(values, "items") else values
            for key, value in items:
                self[key] = value

    def __setitem__(self, key: str, value: str) -> None:
        normalized = key.lower()
        old_key = self._keys.get(normalized)
        if old_key is not None and old_key != key:
            super().__delitem__(old_key)
        self._keys[normalized] = key
        super().__setitem__(key, value)

    def __getitem__(self, key: str) -> str:
        return super().__getitem__(self._keys[key.lower()])

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key.lower() in self._keys

    def get(self, key: str, default: str | None = None) -> str | None:
        actual = self._keys.get(key.lower())
        if actual is None:
            return default
        return super().get(actual, default)

    def pop(self, key: str, default: str | None = None) -> str | None:
        actual = self._keys.pop(key.lower(), None)
        if actual is None:
            return default
        return super().pop(actual, default)

    def setdefault(self, key: str, default: str) -> str:
        if key in self:
            return self[key]
        self[key] = default
        return default

    def update(self, values: Mapping[str, str] | Iterable[tuple[str, str]], **kwargs: str) -> None:
        items = values.items() if hasattr(values, "items") else values
        for key, value in items:
            self[key] = value
        for key, value in kwargs.items():
            self[key] = value

    def __delitem__(self, key: str) -> None:
        actual = self._keys.pop(key.lower())
        super().__delitem__(actual)

    def copy(self) -> "CaseInsensitiveHeaders":
        return CaseInsensitiveHeaders(self.items())

    def lower_items(self) -> Iterable[tuple[str, str]]:
        for key, value in self.items():
            yield key.lower(), value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CaseInsensitiveHeaders):
            return dict(self.lower_items()) == dict(other.lower_items())
        if isinstance(other, dict):
            return dict(self.lower_items()) == {k.lower(): v for k, v in other.items()}
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]


@dataclass(slots=True)
class TimingInfo:
    dns: float = 0.0
    tcp_connect: float = 0.0
    tls_handshake: float = 0.0
    request_send: float = 0.0
    time_to_first_byte: float = 0.0
    total: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "dns": self.dns,
            "tcp_connect": self.tcp_connect,
            "tls_handshake": self.tls_handshake,
            "request_send": self.request_send,
            "time_to_first_byte": self.time_to_first_byte,
            "total": self.total,
        }


@dataclass(slots=True)
class RedirectRecord:
    url: str
    status_code: int
    location: str
    method: str


@dataclass(slots=True)
class Request:
    method: str
    url: str
    headers: CaseInsensitiveHeaders = field(default_factory=CaseInsensitiveHeaders)
    body: bytes | str | None = b""
    timeout: object | None = None
    trace: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.method = self.method.upper()
        if not isinstance(self.headers, CaseInsensitiveHeaders):
            self.headers = CaseInsensitiveHeaders(self.headers)
        if isinstance(self.body, str):
            self.body = self.body.encode("utf-8")
        elif self.body is None:
            self.body = b""
        elif not isinstance(self.body, (bytes, bytearray)):
            raise TypeError(
                f"Request.body must be bytes, str, or None; got {type(self.body).__name__}"
            )
        elif isinstance(self.body, bytearray):
            self.body = bytes(self.body)

    def copy_with(self, **changes: object) -> "Request":
        return replace(self, **changes)


@dataclass(slots=True)
class Response:
    status_code: int
    reason: str
    headers: CaseInsensitiveHeaders
    body: bytes
    url: str
    elapsed: float = 0.0
    timings: TimingInfo = field(default_factory=TimingInfo)
    history: list[RedirectRecord] = field(default_factory=list)
    request: Request | None = None
    framing: str = "unknown"
    set_cookies: list[str] = field(default_factory=list)
    trailers: CaseInsensitiveHeaders = field(default_factory=CaseInsensitiveHeaders)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    @property
    def text(self) -> str:
        content_type = self.headers.get("Content-Type", "") or ""
        encoding = "utf-8"
        for part in content_type.split(";"):
            part = part.strip()
            if part.lower().startswith("charset="):
                encoding = part.split("=", 1)[1].strip() or "utf-8"
        try:
            return self.body.decode(encoding, errors="replace")
        except LookupError:
            # Server-supplied charset is unknown to Python's codec registry.
            # Fall back to utf-8 with replacement rather than crashing callers.
            return self.body.decode("utf-8", errors="replace")

    def json(self) -> object:
        return json.loads(self.text)

    def raise_for_status(self) -> None:
        """Raise ``HttpStatusError`` if the response is not 2xx/3xx.

        Library convenience that mirrors ``requests.Response.raise_for_status``.
        The CLI uses the ``fail=True`` path on ``ApiClient.request`` instead, so
        this method is intended for callers wiring the client into their own
        Python code.
        """

        from .exceptions import HttpStatusError

        if not (200 <= self.status_code < 400):
            raise HttpStatusError(f"HTTP {self.status_code} {self.reason} for {self.url}")
