# Architecture Decision Record
## App — Simple API Client
**HTTP Protocol Systems Group | Document 1 of 5**
**Status: Accepted**

---

## Context

The HTTP Protocol Systems group requires an educational Python API client that demonstrates what happens below a convenient `requests.get(...)` call. The app shows URL parsing, HTTP/1.1 request serialization, TCP sockets, optional TLS wrapping, response framing, redirects, retries, authentication, pagination, configuration profiles, connection reuse, and a local WSGI demonstration server.

The project is explicitly a capstone and learning tool, not a production replacement for `requests`, `httpx`, or `curl`. Its value is that the network and protocol layers are visible. The design therefore favors readability, traceability, and testability over maximum performance or full HTTP feature coverage.

The app ships as a Python library centered on `ApiClient`, a CLI command named `apiclient`, and a local WSGI demo server under `server/`.

The central architectural principle is transport independence: the high-level client should not care whether the request is sent through the raw socket transport or a standard-library `urllib` transport.

---

## Decisions

### Decision 1 — Implement a raw socket HTTP/1.1 transport

**Chosen:** Provide `RawSocketTransport`, which performs DNS lookup, TCP connect, optional TLS wrapping, byte-level HTTP request serialization, and manual response parsing.

**Rejected:** Using `requests`, `httpx`, or only `urllib`.

**Reason:** The capstone goal is protocol mastery. Delegating the core request path to a mature client would hide the exact concepts the project is meant to demonstrate.

---

### Decision 2 — Provide a `urllib` transport behind the same interface

**Chosen:** Support both raw and standard-library transports through the same high-level client API.

**Rejected:** Making the raw transport the only implementation.

**Reason:** The second transport is a teaching comparison. It shows what a mature client stack handles automatically while proving the high-level client is decoupled from the transport implementation.

---

### Decision 3 — Keep runtime dependencies standard-library only

**Chosen:** Runtime package has no third-party dependencies.

**Rejected:** Adding external packages for HTTP, CLI, config, retry, or table rendering.

**Reason:** A standard-library runtime reinforces the educational goal and keeps the project portable. Dev tools such as pytest, coverage, and Ruff remain optional development dependencies.

---

### Decision 4 — Model requests and responses with dataclasses

**Chosen:** Use explicit `Request`, `Response`, `TimingInfo`, `RedirectRecord`, and `CaseInsensitiveHeaders` models.

**Rejected:** Passing loose dictionaries through the stack.

**Reason:** HTTP behavior has many moving parts: headers, body bytes, URL, timings, redirects, cookies, trailers, and framing. Explicit models make boundaries testable and readable.

---

### Decision 5 — Keep request body encoding outside the transport

**Chosen:** `ApiClient.request()` prepares JSON/form/raw/binary request bodies before calling `send()`.

**Rejected:** Having every transport decide how to encode request bodies.

**Reason:** Encoding is a client concern. Transports should send a prepared request and own only wire-level concerns such as Host, Content-Length, Connection, socket I/O, and parsing.

---

### Decision 6 — Let the transport own `Content-Length`

**Chosen:** The raw transport computes and sets `Content-Length` from the final byte body.

**Rejected:** Letting high-level body encoders set `Content-Length`.

**Reason:** The transport is closest to the actual bytes written to the socket. It can guarantee the header matches the body after all request preparation.

---

### Decision 7 — Parse response framing manually

**Chosen:** Implement HTTP response parsing for status lines, headers, repeated non-cookie headers, multiple `Set-Cookie` headers, 1xx informational response skipping, bodyless responses, `Transfer-Encoding: chunked`, `Content-Length`, read-until-close fallback, and trailers.

**Rejected:** Using `http.client` as the parser for raw mode.

**Reason:** Response framing is one of the main learning objectives. The parser makes the protocol mechanics explicit.

---

### Decision 8 — Prefer chunked framing over Content-Length when both appear

**Chosen:** If `Transfer-Encoding` contains `chunked`, the raw parser reads the chunked body path.

**Rejected:** Failing every response that includes both `Transfer-Encoding` and `Content-Length`.

**Reason:** The README documents this behavior as the project’s protocol policy. It keeps behavior explicit and lets tests define the edge case.

---

### Decision 9 — Use explicit safety limits

**Chosen:** The parser enforces maximum header size, body size, chunk size, header line count, and trailer line count.

**Rejected:** Reading unbounded data from a socket.

**Reason:** Even an educational client must not accidentally consume unlimited memory. Safety limits are part of responsible protocol work.

---

### Decision 10 — Make retries opt-in

**Chosen:** `--retries` enables retries. By default, only idempotent methods retry.

**Rejected:** Retrying every failed request automatically.

**Reason:** Retrying non-idempotent methods can duplicate side effects. The app requires an explicit `--retry-non-idempotent` override.

---

### Decision 11 — Separate retry and redirect policy from transport

**Chosen:** `ApiClient` owns redirect and retry orchestration. Transports send one prepared request and return one response.

**Rejected:** Having the transport follow redirects or retry internally.

**Reason:** Redirect and retry logic are HTTP client policies, not socket primitives. Keeping them above transport makes behavior shared across raw and `urllib` transport.

---

### Decision 12 — Strip credentials on cross-host redirects by default

**Chosen:** Cross-host redirects remove auth headers and sensitive query parameters unless an unsafe preserve-auth option is enabled.

**Rejected:** Forwarding credentials across every redirect.

**Reason:** Redirects can cross trust boundaries. Credentials must not leak to a different host by default.

---

### Decision 13 — Add a small connection pool for keep-alive reuse

**Chosen:** Raw transport optionally accepts a `ConnectionPool` for HTTP/1.1 keep-alive reuse.

**Rejected:** Opening a fresh socket for every request only.

**Reason:** Connection reuse is central to HTTP/1.1. Implementing a small pool teaches reuse, stale socket handling, HTTP/1.0 behavior, and lifecycle cleanup.

---

### Decision 14 — Use stable CLI exit codes

**Chosen:** CLI maps major failure classes to stable exit codes.

**Rejected:** Returning only `0` or `1`.

**Reason:** API clients are often scripted. Stable exit codes make failure modes machine-readable.

---

### Decision 15 — Include a local WSGI demo server

**Chosen:** Ship a demo server with `/health`, `/private`, `/items`, `/flaky`, `/redirect`, `/echo`, and `/reset-flaky`.

**Rejected:** Requiring external services for all demos.

**Reason:** A local server makes the capstone reproducible. It also demonstrates the WSGI contract: `environ`, `start_response`, and byte iterable responses.

---

## Consequences

**Positive:**

- Protocol behavior is visible and explainable.
- High-level request logic is independent of transport.
- The raw transport demonstrates DNS, TCP, TLS, serialization, parsing, and timings.
- Tests can exercise parser behavior without live network calls.
- Credentials are redacted in traces and generated curl commands.
- Redirects and retries are explicit policies.
- The CLI is script-friendly.
- The WSGI demo server provides deterministic endpoints for labs.

**Negative / Trade-offs:**

- The client is not production-grade.
- HTTP/2, proxies, compression, cookies, streaming uploads/downloads, multipart forms, and chunked request bodies are out of scope.
- Manual parsing increases maintenance responsibility.
- Full-featured connection pooling is hard; this project intentionally keeps it limited.
- Trace output must be carefully redacted.
- `urllib` and raw transports may expose small behavioral differences because one uses mature standard-library internals and one is educational.

---

## Alternatives Not Explored

- `requests` or `httpx` implementation.
- HTTP/2.
- Proxy support.
- Cookie jar replay.
- Multipart uploads.
- Streaming response bodies.
- Transparent gzip/deflate decompression.
- Full certificate customization.
- Async socket transport.
- Persistent disk cache.
- Production-grade service discovery.
- Django API server.

---

*Constitution reference: Article 1 (Python fundamentals and architectural thinking), Article 3.3 (scope discipline), Article 4 (quality proportional to scope), Article 5 (trade-off documentation), Article 6 (behavior verification), and Article 7 (progressive complexity).*

---


# Technical Design Document
## App — Simple API Client
**HTTP Protocol Systems Group | Document 2 of 5**

---

## Overview

Simple API Client is a Python library and CLI for making HTTP API requests while exposing the underlying HTTP mechanics. The stack is layered so each concern has a clear home.

**Package:** `apiclient`  
**Distribution:** `simple-api-client`  
**CLI:** `apiclient`  
**Python:** `>=3.11`  
**Runtime dependencies:** none  
**Development tools:** pytest, pytest-cov, Ruff  
**Primary client:** `ApiClient`  
**Default transport:** `RawSocketTransport`  
**Demo server:** local WSGI server under `server/`

---

## System Architecture

```text
CLI / library caller
  │
  ▼
ApiClient.request()
  ├── normalize headers
  ├── merge query params
  ├── encode JSON/form/raw/binary body
  ├── validate absolute HTTP(S) URL
  └── build Request
        │
        ▼
ApiClient.send()
  ├── apply auth strategy
  ├── redact trace secrets
  ├── follow redirects
  ├── apply retry policy
  └── call Transport.send()
        │
        ├── RawSocketTransport
        │     ├── parse URL
        │     ├── DNS lookup
        │     ├── TCP connect
        │     ├── optional TLS
        │     ├── serialize request bytes
        │     ├── read/parse response bytes
        │     └── optionally release keep-alive socket
        │
        └── UrllibTransport
              └── standard-library HTTP implementation
```

---

## Raw Transport Flow

```text
Request
  │
  ▼
parse_url()
  │
  ▼
ConnectionPool.acquire() or socket.getaddrinfo()
  │
  ▼
socket.connect()
  │
  ▼
ssl.wrap_socket() when scheme is https
  │
  ▼
_serialize_request()
  ├── Host
  ├── User-Agent
  ├── Accept
  ├── Connection
  ├── Content-Length
  └── CRLF request bytes
  │
  ▼
sock.sendall(payload)
  │
  ▼
read_response()
  ├── read status/header block
  ├── skip informational 1xx
  ├── parse headers and Set-Cookie
  ├── choose body framing
  ├── read body
  └── parse trailers if chunked
  │
  ▼
Response
```

---

## Main Package Areas

```text
src/apiclient/
  __init__.py
  client.py
  models.py
  exceptions.py
  concurrency.py
  config.py
  auth/
    base.py
    ...
  cli/
    main.py
    ...
  http/
    encode.py
    parser.py
    redirects.py
    url.py
  observability/
    redaction.py
    timing.py
  pagination/
    ...
  resilience/
    retry.py
    timeout.py
  transport/
    base.py
    socket_transport.py
    urllib_transport.py
    pool.py
server/
  run_server.py
  wsgi_app.py
  endpoints.py
tests/
  unit/
  integration/
```

---

## Core Data Structures

### `CaseInsensitiveHeaders`

A small header mapping that preserves latest original casing for display while normalizing lookups to lowercase.

Purpose:

- HTTP headers are case-insensitive.
- Display and trace output can preserve readable casing.

---

### `TimingInfo`

Tracks request timing:

- DNS lookup
- TCP connect
- TLS handshake
- request send
- time to first byte
- total

Used for trace output and response summaries.

---

### `RedirectRecord`

Records one redirect hop:

- URL
- status code
- `Location`
- method used for next request

---

### `Request`

Fields:

- method
- URL
- headers
- body
- timeout
- trace events

Behavior:

- method is uppercased
- headers become `CaseInsensitiveHeaders`
- string body becomes UTF-8 bytes
- `None` body becomes empty bytes
- invalid body types raise `TypeError`

---

### `Response`

Fields:

- status code
- reason
- headers
- body
- URL
- elapsed
- timings
- redirect history
- originating request
- framing
- `Set-Cookie` values
- trailers

Convenience:

- `ok`
- `text`
- `json()`
- `raise_for_status()`

---

### `ParsedUrl`

Fields:

- scheme
- hostname
- port
- path
- query
- target
- host header

Rules:

- only `http` and `https`
- hostname required
- URL userinfo rejected
- default port 80/443
- IPv6 host header bracket handling
- target includes query string

---

### `ParsedResponse`

Internal parser result:

- version
- status code
- reason
- headers
- body
- framing
- set cookies
- trailers

---

## Key Components

### `ApiClient`

Public synchronous client.

Responsibilities:

1. Prepare request data.
2. Apply auth.
3. Handle redirects.
4. Handle retries.
5. Call the active transport.
6. Expose `last_trace` and `last_request`.
7. Raise status errors when `fail=True`.
8. Close transport resources.

Important note:

- `last_trace` and `last_request` reflect the most recent call and are not safe to read concurrently while using batch fetching.

---

### `Transport`

Interface for sending one prepared `Request` and returning one `Response`.

Implementations:

- `RawSocketTransport`
- `UrllibTransport`

---

### `RawSocketTransport`

Responsibilities:

- parse URL
- perform DNS lookup
- connect TCP socket
- wrap TLS for HTTPS
- serialize HTTP/1.1 request bytes
- set `Host`, `User-Agent`, `Accept`, `Connection`, `Content-Length`
- send request bytes
- parse response with `read_response`
- record timings
- return or close socket depending on keep-alive eligibility

Safety:

- rejects CR/LF in header names or values
- applies read/connect/total timeout bounds
- wraps socket/TLS failures in client exceptions
- closes poisoned sockets

---

### HTTP Response Parser

Responsibilities:

- read until CRLFCRLF header boundary
- parse status line
- decode headers with ISO-8859-1
- reject obsolete folded headers
- combine repeat headers except `Set-Cookie`
- preserve each `Set-Cookie`
- skip 1xx informational responses
- enforce bodyless status/method rules
- handle chunked transfer coding
- handle `Content-Length`
- fallback to read-until-close
- parse trailers
- enforce safety limits

Framing result:

- `bodyless`
- `chunked`
- `content-length`
- `connection-close`

---

### Retry Policy

Responsibilities:

- define retry count
- restrict retries to idempotent methods by default
- support retryable status codes
- support retryable transport exceptions
- calculate exponential backoff with jitter
- respect `Retry-After` when present
- raise `RetryExhausted` after configured attempts

---

### Redirect Policy

Responsibilities:

- identify redirect status codes
- resolve relative `Location`
- rewrite POST to GET for 303 and common 301/302 behavior
- preserve method for 307/308
- enforce max redirect count
- strip auth on cross-host redirects by default
- append redirect trace/history

---

### Auth Strategies

Shared interface:

- `apply(request) -> Request`
- `secrets() -> list[str]`
- `sensitive_header_names()`
- `sensitive_query_params()`

Supported strategies documented by the README:

- bearer token
- basic auth
- API key header
- API key query parameter

Purpose:

- centralize credential insertion
- allow trace/curl redaction
- allow redirect stripping of sensitive material

---

### Pagination

Strategies documented by the README:

- offset
- page
- cursor
- RFC 8288 `Link` header

Library:

- lazy `pages()` iterator

CLI:

- eager collection up to `--max-pages`
- optional `--items-only` flattened output

---

### Configuration Profiles

Config file:

```text
~/.apiclient.toml
```

Precedence:

```text
CLI flags > APICLIENT_* environment variables > profile values > defaults
```

Important behavior:

- default profile auto-applies when `--profile` omitted
- unknown profile raises `ConfigError`
- `configure set` validates keys
- missing config file for `configure list` exits 0 and prints `default`
- missing key for `configure get` exits 1 with empty stdout

---

### WSGI Demo Server

Purpose:

- deterministic local server for demos and integration tests
- teaches WSGI contract

Contract:

- `environ` contains method, path, query string, headers, and body stream
- `start_response(status, headers)` sends response metadata
- app returns iterable of response bytes

Endpoints:

- `GET /health`
- `GET /private`
- `GET /items`
- `GET /flaky`
- `GET /redirect`
- `POST /echo`
- `GET /reset-flaky`

---

## Error Handling Strategy

The CLI maps exception families to stable exit codes.

Error categories:

- invalid URL / usage
- transport failure
- timeout
- HTTP status failure under `--fail`
- retries exhausted
- authentication failure
- protocol parsing error
- pagination metadata error
- redirect handling error
- configuration error

The library exposes typed exceptions so callers can handle errors directly.

---

## Concurrency Model

The core `ApiClient` is synchronous.

Additional behavior:

- `fetch_many` provides async batch-style fetching for multiple URLs.
- Connection pool acquire/release is thread-safe.
- `last_trace` and `last_request` are not concurrency-safe.
- Pool is intended for one process and one owning client instance.

---

## Known Limits

The project intentionally does not implement:

- cookie jar replay
- multipart form encoding
- streaming upload/download APIs
- gzip/deflate content decoding
- HTTP/2
- proxies
- request chunked transfer bodies
- obsolete folded response headers
- production-grade pooling

---

## Verification Summary

The README documents:

- 350+ tests
- about 96% line coverage on `apiclient`
- coverage gate of 90%
- unit and integration suites
- parser tests for `Content-Length`, chunked, trailers, 1xx, and bodyless responses
- connection pool lifecycle tests
- retries and redirect tests
- auth redaction tests
- pagination strategy tests
- URL/userinfo validation tests
- WSGI and chunked integration tests
- CLI command tests
- async `fetch_many` tests
- config TOML round-trip tests
- transport edge-case tests

---

*Constitution reference: Article 4 (engineering quality), Article 6 (behavior verification), Article 7 (progressive complexity), and Article 8 (valid learner work).*

---


# Interface Design Specification
## App — Simple API Client
**HTTP Protocol Systems Group | Document 3 of 5**

---

## Public CLI Interface

### Console script

```powershell
apiclient <command> [arguments] [options]
```

### Version

```powershell
apiclient --version
```

---

## Primary Commands

### `get`

```powershell
apiclient get URL [options]
```

Sends a GET request.

---

### `post`

```powershell
apiclient post URL [options]
```

Sends a POST request with optional JSON/form/raw/binary body.

---

### `paginate`

```powershell
apiclient paginate URL --strategy offset --limit 10 --max-pages 3
```

Eagerly collects pages up to `--max-pages`.

Strategies:

- `offset`
- `page`
- `cursor`
- `link`

---

### `bench`

```powershell
apiclient bench http://127.0.0.1:8000/items/{id} --count 25 --concurrency 5
```

Runs a small request benchmark.

---

### `auth test`

```powershell
apiclient auth test http://127.0.0.1:8000/private --bearer-token demo-token
```

Checks whether credentials work against a target endpoint.

---

### `configure`

```powershell
apiclient configure set dev.base_url http://127.0.0.1:8000
apiclient configure get dev.base_url
apiclient configure list
apiclient configure unset dev.base_url
```

Manages `~/.apiclient.toml`.

---

## Common Request Options

| Option | Description |
|---|---|
| `--transport raw` | Use raw socket transport |
| `--transport urllib` | Use standard-library transport |
| `-H`, `--header` | Repeatable header in `Name: value` format |
| `--param` | Repeatable query param in `key=value` format |
| `--json` | JSON request body |
| `--form` | Form body |
| `--data` | Raw string/bytes style body |
| `--binary-file` | File body |
| `--output pretty` | Human-readable JSON/text output |
| `--output raw` | Raw body output |
| `--output table` | Table rendering for list-of-object JSON |
| `--trace`, `--verbose` | Print trace events to stderr |
| `--curl` | Print equivalent redacted curl command |
| `--fail` | Non-2xx/3xx response exits as HTTP status error |
| `--profile NAME` | Load named config profile |
| `--timeout` options | Apply connect/read/total timeout settings |

---

## Auth Options

| Strategy | CLI option |
|---|---|
| Bearer token | `--bearer-token TOKEN` |
| Basic auth | `--basic user:password` |
| API key header | `--api-key-header Name=value` |
| API key query | `--api-key-query name=value` |

Redaction:

- credential values are masked in trace output
- credential values are masked in generated curl commands
- extra sensitive query parameter names can be supplied with `APICLIENT_REDACT_PARAMS`

---

## Retry Options

| Option | Description |
|---|---|
| `--retries N` | Enables retry attempts |
| `--retry-non-idempotent` | Allows retrying POST/PUT/PATCH-like methods |
| `--no-retry-non-idempotent` | Keeps non-idempotent retry disabled |
| `--retry-status CODE` | Repeatable retry status override |
| `--backoff-factor N` | Exponential backoff base |
| `--retry-jitter N` | Jitter amount |
| `--retry-max-backoff N` | Backoff cap |

Default retryable statuses:

```text
429, 502, 503, 504
```

Default retryable methods:

```text
GET, HEAD, OPTIONS, DELETE
```

---

## Redirect Options

| Option | Description |
|---|---|
| `--no-follow-redirects` | Disable redirect following |
| `--max-redirects N` | Maximum redirect hops |
| `--preserve-auth-across-hosts` | Unsafe: forwards credentials cross-host |
| `--no-preserve-auth-across-hosts` | Default: strip credentials cross-host |
| `--redirect-status N` | Repeatable redirect status override |

Default redirect statuses:

```text
301, 302, 303, 307, 308
```

---

## Connection Pool Options

| Option | Description |
|---|---|
| `--keep-alive` | Enable raw transport connection reuse |
| `--pool-size N` | Max idle sockets per host |
| `--pool-idle SECONDS` | Idle timeout |

Library equivalent:

```python
from apiclient import ApiClient
from apiclient.transport import ConnectionPool, RawSocketTransport

pool = ConnectionPool(max_per_host=4, max_idle_seconds=30.0)
with ApiClient(transport=RawSocketTransport(pool=pool)) as client:
    client.request("GET", "http://example.test/")
```

---

## CLI Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Success |
| `1` | Generic client error or interrupted |
| `2` | Invalid URL / argparse usage / value error |
| `3` | Transport failure |
| `4` | HTTP status error under `--fail` |
| `5` | Retries exhausted |
| `6` | Authentication failure |
| `7` | Protocol parsing error |
| `8` | Pagination metadata error |
| `9` | Redirect handling error |
| `10` | Configuration error |

Special cases:

- `configure get` returns `1` when key missing
- `configure list` returns `0` when config file does not exist yet

---

## Public Library Interface

### Top-level imports

```python
from apiclient import (
    ApiClient,
    BearerTokenAuth,
    BatchResult,
    fetch_many,
    HttpStatusError,
    Request,
    Response,
)
```

---

### Basic request

```python
from apiclient import ApiClient

with ApiClient() as client:
    response = client.request(
        "GET",
        "https://api.example.test/v1/items",
        params={"page": 1, "per_page": 25},
        fail=True,
        trace=True,
    )
    print(response.json())
```

---

### Auth request

```python
from apiclient import ApiClient
from apiclient.auth import BearerTokenAuth

with ApiClient() as client:
    response = client.request(
        "GET",
        "https://api.example.test/private",
        auth=BearerTokenAuth("token"),
    )
```

---

### `ApiClient.request()`

```python
request(
    method,
    url,
    *,
    headers=None,
    params=None,
    json=None,
    form=None,
    data=None,
    binary_file=None,
    auth=None,
    timeout=None,
    follow_redirects=True,
    fail=False,
    trace=False,
) -> Response
```

Responsibilities:

- encode body
- merge params
- validate URL
- build request
- delegate to `send()`

---

### `ApiClient.send()`

```python
send(
    request,
    *,
    auth=None,
    timeout=None,
    follow_redirects=True,
    fail=False,
    trace=False,
) -> Response
```

Responsibilities:

- validate URL
- copy request
- apply auth
- run redirects
- run retries
- call transport
- redact secrets
- raise `HttpStatusError` when `fail=True` and response is not ok

---

### `Request`

```python
Request(method, url, headers=..., body=...)
```

Contract:

- method normalized to uppercase
- headers become `CaseInsensitiveHeaders`
- body converted to bytes
- invalid body types raise `TypeError`

---

### `Response`

Important fields:

- `status_code`
- `reason`
- `headers`
- `body`
- `url`
- `elapsed`
- `timings`
- `history`
- `request`
- `framing`
- `set_cookies`
- `trailers`

Important methods/properties:

- `ok`
- `text`
- `json()`
- `raise_for_status()`

---

## URL Contract

Valid:

```text
http://example.com/path
https://example.com/path?x=1
```

Invalid:

```text
ftp://example.com
http:///missing-host
http://user:pass@example.com
```

Rules:

- only `http` and `https`
- host required
- credentials in URL userinfo are rejected
- use BasicAuth / `--basic` for credentials

---

## Response Parsing Contract

Body framing priority:

1. bodyless response when method/status forbids body
2. `Transfer-Encoding` containing `chunked`
3. `Content-Length`
4. read until connection close

Parser rejects:

- missing/malformed status line
- invalid `Content-Length`
- obsolete folded headers
- malformed header lines
- oversized headers/body/chunks/trailers
- malformed chunk sizes
- malformed trailer headers
- early connection close before expected bytes

---

## Trace Contract

Trace may include:

- URL parse components
- DNS lookup count and timing
- TCP connect timing
- TLS handshake timing
- request line
- request headers with credentials redacted
- request body byte count
- response status
- response headers with credentials redacted
- response framing
- retry events
- redirect events
- timing summary

Trace goes to stderr in CLI and `client.last_trace` in library usage.

---

## WSGI Demo Server Interface

Run:

```powershell
python server/run_server.py --host 127.0.0.1 --port 8000
```

Endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Health check |
| `/private` | GET | Auth demo |
| `/items` | GET | Pagination demo |
| `/flaky` | GET | Retry demo |
| `/redirect` | GET | Redirect demo |
| `/echo` | POST | Request echo demo |
| `/reset-flaky` | GET | Reset retry state |

Demo credentials:

- bearer token: `demo-token`
- basic: `demo:secret`
- API key: `demo-key`

These credentials are for local labs only.

---

*Constitution reference: Article 4 (input/output boundaries), Article 6 (verification), and Article 8 (understandable and verifiable work).*

---


# Runbook
## App — Simple API Client
**HTTP Protocol Systems Group | Document 4 of 5**

---

## Requirements

### Runtime

- Python 3.11 or newer
- No third-party runtime dependencies

### Development

- pytest
- pytest-cov
- Ruff

---

## Installation

### Runtime and CLI

```powershell
python -m pip install -e .
```

### Dev install

```powershell
python -m pip install -r requirements.txt
```

or:

```powershell
python -m pip install -e ".[dev]"
```

---

## Start Demo Server

```powershell
python server/run_server.py --host 127.0.0.1 --port 8000
```

Expected:

- server binds to localhost
- WSGI endpoints are available

---

## Smoke Tests

### Health check using raw transport

```powershell
apiclient get http://127.0.0.1:8000/health --transport raw --trace
```

Expected:

- exit code `0`
- response body from `/health`
- trace printed to stderr

---

### Health check using urllib transport

```powershell
apiclient get http://127.0.0.1:8000/health --transport urllib
```

Expected:

- same high-level behavior through alternate transport

---

### POST echo

```powershell
apiclient post http://127.0.0.1:8000/echo --json '{"name":"Ada"}'
```

Expected:

- server echoes method, path, query, headers, and body

---

### Auth check

```powershell
apiclient get http://127.0.0.1:8000/private --bearer-token demo-token --trace
```

Expected:

- success
- token redacted in trace

---

### Retry demo

```powershell
apiclient get 'http://127.0.0.1:8000/flaky?key=demo&succeed_after=2' --retries 2 --trace
```

Expected:

- first attempt or attempts may fail
- retry trace events appear
- final request succeeds if retry count is sufficient

---

### Pagination demo

```powershell
apiclient paginate http://127.0.0.1:8000/items --strategy offset --limit 10 --max-pages 3
```

Expected:

- JSON output for up to three pages

---

## Standard Operating Procedures

### Compare raw vs urllib behavior

```powershell
apiclient get http://127.0.0.1:8000/health --transport raw --trace
apiclient get http://127.0.0.1:8000/health --transport urllib --trace
```

Use this to explain what the raw transport performs manually.

---

### Generate curl equivalent

```powershell
apiclient get http://127.0.0.1:8000/private --bearer-token demo-token --curl
```

Expected:

- stderr contains redacted curl command

---

### Fail on HTTP status

```powershell
apiclient get http://127.0.0.1:8000/private --bearer-token wrong --fail
```

Expected:

- exit code `4`
- HTTP status error

---

### Use custom headers and params

```powershell
apiclient get http://127.0.0.1:8000/echo `
  -H 'X-Trace-Id: 123' `
  --param tag=red `
  --param tag=blue
```

PowerShell note:

- quote URLs containing `?` and `&`

---

### Enable keep-alive pool

```powershell
apiclient get http://127.0.0.1:8000/health --transport raw --keep-alive --pool-size 4 --pool-idle 30
```

---

### Manage config profile

```powershell
apiclient configure set dev.base_url http://127.0.0.1:8000
apiclient configure get dev.base_url
apiclient configure list
apiclient configure unset dev.base_url
```

---

## Running Tests

### Pytest

```powershell
pytest -q
```

### Coverage

```powershell
pytest --cov=apiclient --cov-report=term-missing --cov-fail-under=90
```

### Submission gate

```powershell
python scripts/verify_submission.py
```

### Compile check

```powershell
python -m compileall -q src server tests
```

### Ruff

```powershell
ruff check src tests server
```

---

## Health Checks

### Package import

```powershell
python -c "from apiclient import ApiClient, Request, Response; print('ok')"
```

Expected:

```text
ok
```

---

### CLI version

```powershell
apiclient --version
```

Expected:

- version output
- exit code `0`

---

### URL validation

```powershell
apiclient get ftp://example.com
```

Expected:

- invalid URL error
- exit code `2`

---

### Transport failure

```powershell
apiclient get http://127.0.0.1:1/health
```

Expected:

- connection failure
- exit code `3`

---

### Parser safety

Use tests rather than live servers to validate:

- invalid `Content-Length`
- malformed status line
- oversized body
- chunked parsing
- trailers
- folded header rejection

---

## Expected Failure Modes

### Invalid URL

Cause:

- unsupported scheme
- missing hostname
- embedded username/password

Exit:

```text
2
```

Resolution:

- use absolute `http` or `https`
- pass credentials through auth options

---

### Transport failure

Cause:

- server down
- DNS failure
- refused connection
- TLS failure

Exit:

```text
3
```

Resolution:

- check server URL
- check network
- retry with `--transport urllib` to compare behavior

---

### Timeout

Cause:

- connect/read/total timeout exceeded

Exit:

```text
3
```

Resolution:

- increase timeout
- inspect trace
- check server responsiveness

---

### HTTP status error

Cause:

- `--fail` enabled and response status is outside 2xx/3xx

Exit:

```text
4
```

Resolution:

- inspect status/body without `--fail`
- fix auth or endpoint

---

### Retries exhausted

Cause:

- retryable status or exception continued past attempts

Exit:

```text
5
```

Resolution:

- increase `--retries`
- inspect `Retry-After`
- inspect server behavior

---

### Auth failure

Cause:

- incorrect bearer/basic/API key credential

Exit:

```text
6
```

Resolution:

- use demo credentials only for local WSGI server
- verify auth strategy

---

### Protocol parsing error

Cause:

- malformed HTTP response
- invalid headers
- invalid chunked encoding
- body exceeds safety limits

Exit:

```text
7
```

Resolution:

- inspect trace
- reproduce with parser unit test
- compare `urllib` behavior

---

### Pagination error

Cause:

- missing expected metadata
- bad cursor/page/offset shape
- bad `Link` header

Exit:

```text
8
```

Resolution:

- inspect first page response
- confirm selected strategy matches API

---

### Redirect error

Cause:

- too many redirects
- invalid `Location`
- unsafe cross-host credential policy conflict

Exit:

```text
9
```

Resolution:

- lower or raise `--max-redirects`
- inspect redirect chain
- avoid preserving credentials cross-host

---

### Config error

Cause:

- unknown profile
- invalid config key
- malformed TOML
- invalid env value

Exit:

```text
10
```

Resolution:

- run `apiclient configure list`
- inspect `~/.apiclient.toml`
- override with CLI flags

---

## Troubleshooting Decision Tree

```text
Request failed
  ├── Exit code 2?
  │     └── validate URL, CLI syntax, and userinfo rules
  ├── Exit code 3?
  │     ├── is demo server running?
  │     ├── can urllib transport connect?
  │     └── inspect DNS/TCP/TLS trace
  ├── Exit code 4?
  │     └── remove --fail and inspect response body/status
  ├── Exit code 5?
  │     └── increase retries or inspect Retry-After/server behavior
  ├── Exit code 6?
  │     └── verify auth strategy and credential
  ├── Exit code 7?
  │     └── inspect raw response framing/parser tests
  ├── Exit code 8?
  │     └── match paginator strategy to API response metadata
  ├── Exit code 9?
  │     └── inspect redirect chain and credential stripping policy
  └── Exit code 10?
        └── inspect profile/env/default precedence
```

---

## Maintenance Notes

- Keep raw transport readable.
- Do not hide protocol behavior behind a third-party HTTP library.
- Keep high-level client transport-independent.
- Add tests before changing parser framing rules.
- Add tests before changing redirect auth-stripping.
- Preserve stable exit codes.
- Keep credential redaction applied to trace and curl output.
- Do not add production claims without adding production-grade behaviors.
- Keep WSGI demo credentials clearly marked as local/demo only.
- Keep runtime dependencies empty unless a new ADR justifies otherwise.

---

*Constitution reference: Article 6 (behavior verification), Article 5 (constraints and trade-offs), and Article 8 (verifiable learner work).*

---


# Lessons Learned
## App — Simple API Client
**HTTP Protocol Systems Group | Document 5 of 5**

---

## Why This Design Was Chosen

This design was chosen because the point of the project is to expose HTTP, not hide it. A mature library would be better for production, but it would skip the learning. The raw transport makes the network stack tangible: DNS, sockets, TLS, request bytes, CRLF headers, response framing, and timeouts are all visible.

The high-level client still matters because real API clients are not only sockets. They need auth, retries, redirects, pagination, output formatting, config profiles, error classes, trace logs, and stable CLI behavior. Separating `ApiClient` from the transport allowed the project to show both layers clearly.

The WSGI server completes the learning loop. The same project demonstrates the client side of HTTP and the server-side WSGI contract.

---

## What Was Intentionally Omitted

**Production-grade HTTP:** Out of scope because the goal is education.

**HTTP/2:** Would require a different protocol model.

**Proxies:** Deferred because proxy behavior adds another network hop and CONNECT semantics.

**Cookie jar:** The parser captures `Set-Cookie`, but replaying cookies is stateful and out of scope.

**Multipart uploads:** Deferred because form-data encoding is its own protocol-like topic.

**Streaming upload/download:** Deferred because the project reads/writes whole bodies.

**Compression:** `Content-Encoding` decompression is not implemented.

**Chunked request bodies:** The client parses chunked responses but does not send chunked request bodies.

**Obsolete folded response headers:** Rejected rather than supported.

---

## Biggest Weakness

The biggest weakness is that manual HTTP implementation is fragile compared with mature clients. Edge cases are numerous: transfer coding, TLS behavior, connection reuse, redirects, malformed headers, cookies, compression, proxy tunneling, and streaming. The project handles a useful subset, but it should not be presented as production-complete.

The second weakness is connection pooling. The pool is intentionally small and educational. Production pooling needs deeper lifecycle control, socket health checks, concurrency strategy, SSL session behavior, DNS refresh, and limits across many hosts.

The third weakness is body handling. Whole-body reads are simple and testable, but streaming would be required for large uploads/downloads.

---

## Scaling Considerations

**If the client became production-oriented:**

- switch default transport to a mature library
- keep raw transport as educational/debug mode
- add proxy support
- add decompression
- add cookie jar
- add streaming APIs
- add cert/custom TLS configuration
- add structured logging/metrics
- add stronger connection pool management

**If large payloads matter:**

- expose streaming response iterator
- support file download target
- support chunked upload or known-length streaming upload
- enforce configurable memory limits

**If concurrency grows:**

- avoid shared `last_trace`
- create per-request trace objects
- define client/thread ownership
- isolate pool state more explicitly

---

## What the Next Refactor Would Be

1. **Per-request trace object** — avoid shared `last_trace` state and make concurrency safer.

2. **Streaming response API** — read large responses incrementally while preserving parser safety.

3. **Structured trace output** — expose trace as events instead of strings.

4. **Transport conformance tests** — run the same behavioral suite against raw and `urllib` transports.

5. **Explicit redirect history object** — make redirect/cross-host stripping easier to inspect.

---

## What This Project Taught

- **HTTP is byte-oriented.** Request lines, headers, CRLFs, and body framing must be exact.

- **A client is more than a socket.** Real API clients need auth, retry, redirects, pagination, config, output, and errors.

- **Parsing is defensive work.** Safety limits and malformed input handling are core protocol concerns.

- **Credentials leak easily.** Redaction must cover trace events, curl output, URLs, headers, and query params.

- **Redirects are security-sensitive.** Cross-host redirects can leak auth unless explicitly stripped.

- **Timeouts have layers.** Connect, read, and total deadlines need clear behavior.

- **WSGI clarifies server boundaries.** The demo server reinforces how Python web apps receive HTTP through `environ` and `start_response`.

- **Mature libraries exist for a reason.** Building this subset makes it clear why `requests` and `httpx` are valuable.

---

*Constitution v2.0 checklist: This document satisfies Article 5 (trade-off documentation), Article 6 (verification), and Article 7 (progressive complexity) for Simple API Client.*
