# Simple API Client

An educational command-line HTTP API client built in Python to show what
happens below a convenient `requests.get(...)` call.

## Academic context

This capstone implements HTTP/1.1 from first principles—URL parsing, sockets,
TLS, byte serialization, and response framing—then layers retries, redirects,
authentication, pagination, and a WSGI demo server on top. The goal is to explain
why libraries such as `requests` and `httpx` exist, not to replace them in
production. See [docs/architecture.md](docs/architecture.md) and
[docs/production-reflection.md](docs/production-reflection.md).

The project has two interchangeable transports:

- `raw` — opens TCP sockets, optionally wraps TLS, serializes HTTP/1.1 bytes,
  and parses the response by hand. Supports an optional connection pool for
  keep-alive reuse.
- `urllib` — uses Python's standard library behind the same interface to show
  what a mature client gives you for free.

The CLI and high-level client do not care which transport is underneath. See
[docs/architecture.md](docs/architecture.md) for the layered picture.

## Install

Requires **Python 3.11+**. Runtime dependencies are stdlib-only; dev tools come from
`requirements.txt`, `requirements.lock`, or the `[dev]` extra.

```powershell
# Runtime + CLI
python -m pip install -e .

# Or install everything (editable package + pytest, coverage, ruff):
python -m pip install -r requirements.txt

# Equivalent dev extra:
python -m pip install -e ".[dev]"

# Reproducible dev/CI install (pinned transitive versions):
python -m pip install -r requirements.lock
python -m pip install -e .
```

Regenerate `requirements.lock` after changing dev dependencies in `pyproject.toml`:

```powershell
python -m piptools compile pyproject.toml --extra dev -o requirements.lock
```

## Demo server (not production)

The local WSGI API uses **hard-coded demo credentials** only (`demo-token`,
`demo:secret`, `demo-key`). Use them for labs and traces; never reuse them for
real services.

```powershell
python server/run_server.py --host 127.0.0.1 --port 8000
```

The app in `server/wsgi_app.py` demonstrates the WSGI contract:

- `environ` contains request method, path, query string, headers, and body stream.
- `start_response(status, headers)` sends response metadata.
- The app returns an iterable of response-body bytes.

Endpoints:

- `GET /health`
- `GET /private`
- `GET /items`
- `GET /flaky`
- `GET /redirect`
- `POST /echo`
- `GET /reset-flaky`

Query parameters accepted by the tunable endpoints (defaults in parentheses):

| Endpoint    | Parameters                                                                                  |
|-------------|---------------------------------------------------------------------------------------------|
| `/items`    | `limit` (25), `offset` (0), `page`, `per_page`, `cursor`, `pagination={cursor,link}`, `link={true,false}` |
| `/flaky`    | `key` (REMOTE_ADDR), `succeed_after` (2), `status` (503), `retry_after` (0)                 |
| `/redirect` | `to` (`/health`), `status` (302; honors 301/302/303/307/308 reason phrases)                 |
| `/private`  | `api_key` (alternative to `Authorization` / `X-API-Key`)                                    |
| `/echo`     | Echoes request method, path, query, headers, and body in the JSON response.                 |

Malformed integer query parameters (e.g. `/items?limit=abc`) return `400 Bad Request`
with the offending field name; see `server/endpoints.py::_int_query`.

## CLI Examples

URLs containing `?` and `&` must be quoted on PowerShell, otherwise `&` is
interpreted as a command separator.

```powershell
apiclient get http://127.0.0.1:8000/health --transport raw --trace
apiclient get http://127.0.0.1:8000/health --transport urllib
apiclient post http://127.0.0.1:8000/echo --json '{"name":"Ada"}'
apiclient get http://127.0.0.1:8000/private --bearer-token demo-token --trace
apiclient get 'http://127.0.0.1:8000/flaky?key=demo&succeed_after=2' --retries 2 --trace
apiclient paginate http://127.0.0.1:8000/items --strategy offset --limit 10 --max-pages 3
apiclient bench http://127.0.0.1:8000/items/{id} --count 25 --concurrency 5
apiclient auth test http://127.0.0.1:8000/private --bearer-token demo-token
apiclient --version
```

### Fail-fast, custom headers, query params, output formats

```powershell
# Treat any non-2xx/3xx response as a CLI failure (exits with code 4):
apiclient get http://127.0.0.1:8000/private --bearer-token wrong --fail

# Repeatable -H / --header flags, repeatable --param flags (preserves order):
apiclient get http://127.0.0.1:8000/echo `
  -H 'X-Trace-Id: 123' `
  -H 'X-Request-Id: abc' `
  --param tag=red `
  --param tag=blue

# Table output for list-of-object JSON responses:
apiclient get http://127.0.0.1:8000/items --output table
```

### Trace, curl, and output formats

- `--trace` / `--verbose` print the full URL parsing, DNS, TCP connect, TLS
  handshake, request bytes, response status, response headers, body framing,
  retries, redirects, and timings to stderr.
- `--curl` prints the equivalent `curl` command to stderr (with credentials
  redacted).
- `--output {pretty,raw,table}` chooses the response rendering on stdout.

## Auth

Supported strategies:

- Bearer token: `--bearer-token demo-token`
- Basic auth: `--basic demo:secret`
- API key header: `--api-key-header X-API-Key=demo-key`
- API key query parameter: `--api-key-query api_key=demo-key`

Secrets are redacted in trace output and generated curl commands. Each auth
strategy declares its credential values via ``secrets()`` so the client can
also mask any incidental leakage of those literals in trace events. Add extra
sensitive query parameter names with ``APICLIENT_REDACT_PARAMS`` (comma-separated,
e.g. ``export APICLIENT_REDACT_PARAMS=session_id,MyToken``). Custom param names
not in that list may still appear in trace output.

## Retries

Retries are opt-in with `--retries`. By default, only idempotent methods retry:
`GET`, `HEAD`, `OPTIONS`, `DELETE`. Override with `--retry-non-idempotent`.

- Retryable statuses default to `429`, `502`, `503`, `504`. Override with
  `--retry-status` (repeatable).
- Backoff is exponential with jitter. Tune with `--backoff-factor`,
  `--retry-jitter`, `--retry-max-backoff`.
- `Retry-After` is respected when present (integer, decimal, or HTTP-date).

## Redirects

Redirects are followed by default. Cross-host hops strip auth headers (including
custom API-key header names from the active auth strategy) and sensitive query
parameters (including API-key query auth). POST is rewritten to GET on 303 (or
301/302 for POST per common practice). Override with:

- `--no-follow-redirects`
- `--max-redirects N`
- `--preserve-auth-across-hosts` — **unsafe**: forwards credentials to other
  hosts; only use when you fully trust every redirect target
- `--no-preserve-auth-across-hosts` (default) — strip auth headers and sensitive
  query parameters on cross-host hops
- `--redirect-status N` (repeatable; default `301 302 303 307 308`)

## Pagination

Available strategies:

- `offset`
- `page`
- `cursor`
- `link` (RFC 8288 `Link: <…>; rel="next"`)

In the **library**, paginators expose a lazy ``pages()`` iterator. The
``apiclient paginate`` command **eagerly** collects every page up to
``--max-pages`` for script-friendly JSON output. Use ``--items-only`` to print a
flat list of items rather than per-page metadata.

## Connection pool (keep-alive)

The raw transport supports an optional connection pool for HTTP/1.1
keep-alive reuse. From the CLI:

```powershell
apiclient get http://127.0.0.1:8000/health --transport raw --keep-alive --pool-size 4 --pool-idle 30
```

Or as a library:

```python
from apiclient import ApiClient
from apiclient.transport import ConnectionPool, RawSocketTransport

pool = ConnectionPool(max_per_host=4, max_idle_seconds=30.0)
with ApiClient(transport=RawSocketTransport(pool=pool)) as client:
    client.request("GET", "http://example.test/")
    client.request("GET", "http://example.test/another")
```

The pool rejects HTTP/1.0 responses unless the server explicitly sends
`Connection: keep-alive`, and discards sockets with pending stale bytes. The
pool is **thread-safe** for concurrent ``acquire`` / ``release`` but is intended
for a single process; share one pool per ``ApiClient`` instance.

## Configuration

Profiles live in `~/.apiclient.toml` under `[profiles.NAME]`. Precedence is
CLI flags → environment variables (`APICLIENT_*`) → profile values → defaults.
The `default` profile is auto-applied when `--profile` is omitted. An unknown
``--profile`` name raises ``ConfigError`` at startup. ``configure set`` validates
keys before writing.

Copy [docs/examples/apiclient.toml.example](docs/examples/apiclient.toml.example)
to ``~/.apiclient.toml`` as a starting point.

```powershell
apiclient configure set dev.base_url http://127.0.0.1:8000
apiclient configure get dev.base_url
apiclient configure list
apiclient configure unset dev.base_url
```

``configure list`` on a missing config file exits **0** and prints ``default`` (the
implicit profile name).
``configure get`` on a missing key exits **1** with empty stdout.

Profile settings (including ``max_redirects``, ``keep_alive``, ``pool_size``,
``backoff_factor``, and ``retry_non_idempotent``) can live in TOML or
``APICLIENT_*`` environment variables—see
[docs/examples/apiclient.toml.example](docs/examples/apiclient.toml.example).
CLI flags override profile values when provided (including ``--no-retry-non-idempotent``).
Status-code lists in TOML use comma-separated strings, e.g.
``retry_statuses = "429,503"`` and ``redirect_statuses = "301,302,303"``.

Before publishing, set ``[project.urls]`` in ``pyproject.toml`` to your real GitHub
repository (the template points at ``princetonafeez/simple-api-client``).

## Tests

The suite uses **`unittest`** test cases and runs under **`pytest`** (primary in
CI) or plain `unittest` discovery. Install dev dependencies first:

```powershell
python -m pip install -r requirements.txt
pytest -q
```

Pre-submission gate (compile, pytest, ruff, doc paths, CLI `--version`):

```powershell
python scripts/verify_submission.py
```

Alternate **unittest** runner (no pytest required beyond `pip install -e .`):

```powershell
python -m compileall -q src server tests
python -c "import sys, unittest; sys.path.insert(0, 'src'); r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests')); sys.exit(0 if r.wasSuccessful() else 1)"
```

Lint:

```powershell
ruff check src tests server
```

**Current baseline:** 350+ tests, **~96%** line coverage on `apiclient` (90%
minimum enforced in `pyproject.toml`). Coverage includes response parsing
(Content-Length, chunked, trailers, 1xx skip), connection pool lifecycle,
retries, auth redaction, four pagination strategies, URL/userinfo rules, WSGI
and chunked integration servers, CLI command handlers, async `fetch_many`,
config TOML round-trips, and transport edge cases. See `tests/unit/` and
`tests/integration/`; exhaustive modules are named `test_*_exhaustive.py`.

## Exit codes

Every CLI invocation exits with a stable code so it can be scripted.

| Code | Meaning                              | Raised by                                            |
|------|--------------------------------------|------------------------------------------------------|
| 0    | Success                              | normal completion                                    |
| 1    | Generic client error or interrupted  | `ApiClientError`, `KeyboardInterrupt`                |
| 2    | Invalid URL / argparse usage         | `InvalidUrlError`, argparse, `ValueError`            |
| 3    | Transport failure                    | `TransportError`, `ConnectionFailure`, `RequestTimeout` |
| 4    | HTTP status error (`--fail`)         | `HttpStatusError`                                    |
| 5    | Retries exhausted                    | `RetryExhausted`                                     |
| 6    | Authentication failure               | `AuthError`                                          |
| 7    | Protocol parsing error               | `ProtocolError`                                      |
| 8    | Pagination metadata error            | `PaginationError`                                    |
| 9    | Redirect handling error              | `RedirectError`                                      |
| 10   | Configuration error                  | `ConfigError`                                        |

``configure get`` returns exit code **1** when the key is missing (empty stdout).
``configure list`` returns **0** when the config file does not exist yet.

## Library use

Top-level imports:

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

Example:

```python
from apiclient import ApiClient
from apiclient.auth import BearerTokenAuth

with ApiClient() as client:
    response = client.request(
        "GET", "https://api.example.test/v1/items",
        auth=BearerTokenAuth("…"),
        params={"page": 1, "per_page": 25},
        fail=True,                # raise HttpStatusError on non-2xx/3xx
        trace=True,               # populate client.last_trace
    )
    print(response.json())
```

## Out of scope (by design)

This client is intentionally educational. It does **not** implement:

- Cookie jars (`Set-Cookie` is parsed but not replayed on later requests)
- Multipart form encoding or streaming upload/download APIs
- `Content-Encoding` decompression (gzip/deflate)
- HTTP/2, proxies, or full production-grade pooling
- Request `Transfer-Encoding: chunked` bodies
- Obsolete folded response headers (RFC 7230 legacy syntax)

If both `Transfer-Encoding: chunked` and `Content-Length` are present on a
response, the raw parser follows chunked when ``chunked`` appears in
``Transfer-Encoding`` (see [docs/protocol-notes.md](docs/protocol-notes.md)).

For why mature libraries exist, see
[docs/production-reflection.md](docs/production-reflection.md).

## Portfolio & submission

Before handing in or presenting live, work through
[docs/SUBMISSION.md](docs/SUBMISSION.md) and run:

```powershell
python scripts/verify_submission.py
```

| Resource | Purpose |
|----------|---------|
| [docs/SUBMISSION.md](docs/SUBMISSION.md) | Pre-submission checklist and rubric self-score |
| [docs/demo-script.md](docs/demo-script.md) | Live demo order (8–15 min) |
| [docs/demo-questions.md](docs/demo-questions.md) | Twelve oral-exam questions |
| [docs/report-outline.md](docs/report-outline.md) | Written report skeleton |
| [docs/windows-testing.md](docs/windows-testing.md) | PowerShell test and quoting notes |
| [docs/protocol-mastery-checklist.md](docs/protocol-mastery-checklist.md) | Protocol topics you should be able to explain |

### Submission metadata (fill in before handing in)

| Field | Value |
|-------|--------|
| Student name | Princeton Afeez |
| Course / section | _fill in_ |
| Instructor | _fill in_ |
| Submission date | _fill in_ |
| Repository URL | _update `[project.urls]` in `pyproject.toml` after push_ |

Update GitHub links in `pyproject.toml` when the repository is public so graders
can install with `pip install git+https://…`.
