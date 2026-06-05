"""Asyncio fan-out built on top of the synchronous client.

:func:`fetch_many` issues many requests concurrently with a semaphore cap. The
synchronous :class:`ApiClient` is invoked from worker threads via
:func:`asyncio.to_thread`, so the protocol path stays a single, testable
implementation. ``fail_fast`` stops collection at the first error and lets
sibling tasks be cancelled by the surrounding :class:`asyncio.TaskGroup`.
"""

from .async_client import BatchResult, fetch_many

__all__ = ["BatchResult", "fetch_many"]
