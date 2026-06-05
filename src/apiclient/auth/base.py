"""Pluggable authentication interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from apiclient.models import Request


class AuthStrategy(ABC):
    @abstractmethod
    def apply(self, request: Request) -> Request:
        """Return a request with authentication data added."""

    @abstractmethod
    def secrets(self) -> list[str]:
        """Return the credential values that must be redacted from logs/traces."""

    def sensitive_header_names(self) -> frozenset[str]:
        """Header names (lowercase) stripped on cross-host redirects."""

        return frozenset()

    def sensitive_query_params(self) -> frozenset[str]:
        """Query parameter names stripped on cross-host redirects."""

        return frozenset()
