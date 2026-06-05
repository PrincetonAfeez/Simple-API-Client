"""HTTP Basic authentication."""

from __future__ import annotations

import base64
from dataclasses import dataclass

from apiclient.auth.base import AuthStrategy
from apiclient.models import Request


@dataclass(frozen=True, slots=True)
class BasicAuth(AuthStrategy):
    username: str
    password: str

    def __post_init__(self) -> None:
        if not self.username:
            raise ValueError("BasicAuth requires a non-empty username")
        if ":" in self.username:
            # RFC 7617 §2: the userid cannot contain a colon because the
            # implementation would not be able to recover the boundary.
            raise ValueError("BasicAuth username cannot contain ':'")

    def apply(self, request: Request) -> Request:
        raw = f"{self.username}:{self.password}".encode("utf-8")
        encoded = base64.b64encode(raw).decode("ascii")
        headers = request.headers.copy()
        headers["Authorization"] = f"Basic {encoded}"
        return request.copy_with(headers=headers)

    def secrets(self) -> list[str]:
        return [self.password]

    def sensitive_header_names(self) -> frozenset[str]:
        return frozenset({"authorization"})
