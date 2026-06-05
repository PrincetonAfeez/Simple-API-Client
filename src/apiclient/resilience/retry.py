"""Retry policy for network errors, timeouts, and selected HTTP statuses."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from apiclient.exceptions import ConnectionFailure, RequestTimeout, TransportError
from apiclient.models import Response

_DEFAULT_RETRY_STATUSES: frozenset[int] = frozenset({429, 502, 503, 504})
_DEFAULT_IDEMPOTENT_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS", "DELETE"})


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    retries: int = 0
    retry_statuses: frozenset[int] = field(default_factory=lambda: _DEFAULT_RETRY_STATUSES)
    idempotent_methods: frozenset[str] = field(
        default_factory=lambda: _DEFAULT_IDEMPOTENT_METHODS
    )
    retry_non_idempotent: bool = False
    backoff_factor: float = 0.25
    jitter: float = 0.1
    max_backoff: float = 5.0

    @property
    def max_attempts(self) -> int:
        return max(1, self.retries + 1)

    def method_allows_retry(self, method: str) -> bool:
        return self.retry_non_idempotent or method.upper() in self.idempotent_methods

    def should_retry_response(self, method: str, response: Response) -> bool:
        return self.method_allows_retry(method) and response.status_code in self.retry_statuses

    def should_retry_exception(self, method: str, exc: BaseException) -> bool:
        return self.method_allows_retry(method) and isinstance(
            exc,
            (ConnectionFailure, RequestTimeout, TransportError),
        )

    def delay_for(self, attempt_number: int, response: Response | None = None) -> float:
        if attempt_number < 1:
            raise ValueError(f"attempt_number must be >= 1, got {attempt_number}")
        retry_after = retry_after_seconds(response) if response is not None else None
        if retry_after is not None:
            return min(retry_after, self.max_backoff)
        exponential = self.backoff_factor * (2 ** (attempt_number - 1))
        jitter = random.uniform(0, self.jitter) if self.jitter else 0.0
        return min(exponential + jitter, self.max_backoff)


def retry_after_seconds(response: Response | None) -> float | None:
    if response is None:
        return None
    value = response.headers.get("Retry-After")
    if not value:
        return None
    value = value.strip()
    # RFC 7231 specifies an integer delta-seconds, but many real servers send
    # a decimal value; accept both before falling back to HTTP-date parsing.
    try:
        seconds = float(value)
    except ValueError:
        seconds = None
    if seconds is not None:
        return max(0.0, seconds)
    try:
        retry_date = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if retry_date.tzinfo is None:
        retry_date = retry_date.replace(tzinfo=timezone.utc)
    return max(0.0, (retry_date - datetime.now(timezone.utc)).total_seconds())
