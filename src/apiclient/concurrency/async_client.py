"""Async fan-out built on top of the reliable synchronous client."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from time import monotonic

from apiclient.client import ApiClient
from apiclient.models import Response

logger = logging.getLogger("apiclient")


@dataclass(slots=True)
class BatchResult:
    total: int
    succeeded: int
    failed: int
    total_elapsed: float
    average_latency: float
    responses: list[Response] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    results_by_url: list[Response | None] = field(default_factory=list)
    errors_by_url: list[str | None] = field(default_factory=list)


async def fetch_many(
    client: ApiClient,
    urls: list[str],
    *,
    method: str = "GET",
    concurrency: int = 10,
    fail_fast: bool = False,
    **request_kwargs,
) -> BatchResult:
    """Fan out HTTP requests onto a worker pool.

    Notes
    -----
    The shared ``client`` is invoked from worker threads via ``asyncio.to_thread``.
    ``ApiClient.last_trace`` / ``last_request`` are overwritten by concurrent
    calls and are unreliable when ``concurrency > 1`` (including ``trace=True``).

    ``responses`` lists successful :class:`~apiclient.models.Response` objects in
    the same order as ``urls``. ``results_by_url`` and ``errors_by_url`` are
    parallel to ``urls`` (``None`` where a slot did not succeed / had no error).

    With ``fail_fast=True`` the first error triggers ``stop_event``; pending
    workers exit before doing further work and the surrounding ``TaskGroup``
    cancels still-waiting tasks. Threads already inside ``client.request`` will
    finish in the background, but their results are discarded.
    """

    if concurrency < 1:
        raise ValueError(f"concurrency must be >= 1, got {concurrency}")
    if concurrency > 1 and request_kwargs.get("trace"):
        logger.warning(
            "fetch_many with trace=True and concurrency>1: last_trace reflects "
            "arbitrary concurrent requests, not each URL."
        )
    semaphore = asyncio.Semaphore(concurrency)
    stop_event = asyncio.Event()
    completed: list[tuple[int, Response]] = []
    errors_indexed: list[tuple[int, str]] = []
    latencies: list[float] = []
    start = monotonic()

    async def fetch_one(index: int, url: str) -> None:
        if stop_event.is_set():
            return
        async with semaphore:
            if stop_event.is_set():
                return
            one_start = monotonic()
            try:
                response = await asyncio.to_thread(
                    client.request, method, url, **request_kwargs
                )
            except Exception as exc:
                if not stop_event.is_set():
                    errors_indexed.append((index, f"{url}: {exc}"))
                if fail_fast:
                    stop_event.set()
                    raise
                return
            if not stop_event.is_set():
                completed.append((index, response))
                latencies.append(monotonic() - one_start)

    try:
        async with asyncio.TaskGroup() as group:
            for index, url in enumerate(urls):
                group.create_task(fetch_one(index, url))
    except* asyncio.CancelledError:
        pass
    except* Exception:
        if not fail_fast:
            raise

    completed.sort(key=lambda item: item[0])
    errors_indexed.sort(key=lambda item: item[0])
    results_by_url: list[Response | None] = [None] * len(urls)
    errors_by_url: list[str | None] = [None] * len(urls)
    for index, response in completed:
        results_by_url[index] = response
    for index, message in errors_indexed:
        errors_by_url[index] = message
    elapsed = monotonic() - start
    return BatchResult(
        total=len(urls),
        succeeded=len(completed),
        failed=len(errors_indexed),
        total_elapsed=elapsed,
        average_latency=(sum(latencies) / len(latencies)) if latencies else 0.0,
        responses=[response for _, response in completed],
        errors=[message for _, message in errors_indexed],
        results_by_url=results_by_url,
        errors_by_url=errors_by_url,
    )
