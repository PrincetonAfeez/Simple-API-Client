"""Bearer token authentication."""

from __future__ import annotations

from dataclasses import dataclass

from apiclient.auth.base import AuthStrategy
from apiclient.models import Request


@dataclass(frozen=True, slots=True)
class BearerTokenAuth(AuthStrategy):
    token: str

    def __post_init__(self) -> None:
        if not self.token or not self.token.strip():
            raise ValueError("BearerTokenAuth requires a non-empty token")

    def apply(self, request: Request) -> Request:
        headers = request.headers.copy()
        headers["Authorization"] = f"Bearer {self.token}"
        return request.copy_with(headers=headers)

    def secrets(self) -> list[str]:
        return [self.token]

    def sensitive_header_names(self) -> frozenset[str]:
        return frozenset({"authorization"})
