"""Resilience policy objects for retries and timeouts.

* :class:`RetryPolicy` — exponential backoff with jitter, idempotency rules,
  retryable status allow-list, and ``Retry-After`` honoring.
* :class:`TimeoutConfig` — separate connect, read, and total deadlines.

Both are immutable frozen dataclasses; callers replace them by constructing a
new instance, not by mutating.
"""
