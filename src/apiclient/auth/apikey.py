"""API-key authentication strategies."""

from __future__ import annotations

from dataclasses import dataclass

from apiclient.auth.base import AuthStrategy
from apiclient.http.url import add_query_param
from apiclient.models import Request


@dataclass(frozen=True, slots=True)
class ApiKeyHeaderAuth(AuthStrategy):
    header_name: str
    api_key: str

    def __post_init__(self) -> None:
        if not self.header_name or not self.header_name.strip():
            raise ValueError("ApiKeyHeaderAuth requires a non-empty header_name")
        if not self.api_key or not self.api_key.strip():
            raise ValueError("ApiKeyHeaderAuth requires a non-empty api_key")

    def apply(self, request: Request) -> Request:
        headers = request.headers.copy()
        headers[self.header_name] = self.api_key
        return request.copy_with(headers=headers)

    def secrets(self) -> list[str]:
        return [self.api_key]

    def sensitive_header_names(self) -> frozenset[str]:
        return frozenset({self.header_name.lower()})


@dataclass(frozen=True, slots=True)
class ApiKeyQueryAuth(AuthStrategy):
    param_name: str
    api_key: str

    def __post_init__(self) -> None:
        if not self.param_name or not self.param_name.strip():
            raise ValueError("ApiKeyQueryAuth requires a non-empty param_name")
        if not self.api_key or not self.api_key.strip():
            raise ValueError("ApiKeyQueryAuth requires a non-empty api_key")

    def apply(self, request: Request) -> Request:
        return request.copy_with(url=add_query_param(request.url, self.param_name, self.api_key))

    def secrets(self) -> list[str]:
        return [self.api_key]

    def sensitive_query_params(self) -> frozenset[str]:
        return frozenset({self.param_name.lower()})
