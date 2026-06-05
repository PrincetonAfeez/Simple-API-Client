"""Shared transport interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from apiclient.models import Request, Response
from apiclient.resilience.timeout import TimeoutConfig


class Transport(ABC):
    @abstractmethod
    def send(self, request: Request, timeout: TimeoutConfig) -> Response:
        """Send one prepared request and return one response."""

    def close(self) -> None:
        """Release transport resources."""
