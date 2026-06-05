# ADR 0002: Sync Core, Async Layer

## Status

Accepted.

## Context

One reliable request is easier to explain and test than many concurrent
requests. Async support should demonstrate I/O concurrency after the synchronous
path is correct.

## Decision

The core client is synchronous. Async fan-out uses `asyncio.to_thread` with a
semaphore cap.

## Alternatives considered

- **Async-first client.** Cleanest in theory, but doubles the protocol code
  paths (read-coroutine vs read-sync) and would have required `aiohttp`-style
  parsing of partial reads in an async generator. Out of scope for the
  educational story.
- **`asyncio.subprocess` to fork curl.** Trivially concurrent, but the goal
  is to show what concurrency does on top of *our* protocol path, not curl's.
- **Thread pool with `concurrent.futures.ThreadPoolExecutor`.** Equivalent
  capability, but `asyncio.TaskGroup` gives proper structured concurrency and
  `except*` for cancellation handling.

## Consequences

The protocol implementation stays readable, while the `bench` command can still
show concurrent I/O behavior and report success, failure, elapsed time, and
average latency. Threads sharing one `ApiClient` mean `last_trace` /
`last_request` are documented as overwritten in the async path; the trace
contract is "per-request" not "per-batch".

## Risks

* **Semaphore starvation under a long-running blocking call.** Workers use
  `asyncio.to_thread`, so a single hung request occupies one OS thread until
  it returns; the remaining `concurrency - 1` slots stay productive. There is
  no deadlock window — the semaphore is acquired *inside* `fetch_one` and
  never held across tasks — but the user-perceived throughput tail is bounded
  by the slowest in-flight request.
* **Cancellation does not abort thread work.** `TaskGroup` cancels pending
  awaitables when `fail_fast` raises, and the surrounding
  `except* asyncio.CancelledError` swallows those cancellations cleanly, but
  the worker thread inside `to_thread` continues until the underlying request
  completes. A module-level `stop_event` prevents those late completions
  from mutating the result lists. This trade-off is documented in
  `apiclient/concurrency/async_client.py`.
* **Concurrency cap is per-call, not global.** Calling `fetch_many` twice in
  parallel produces `2 * concurrency` concurrent workers. The CLI `bench`
  command makes exactly one call so the cap holds there; library users
  running multiple fan-outs in parallel should size accordingly or share a
  semaphore explicitly.
