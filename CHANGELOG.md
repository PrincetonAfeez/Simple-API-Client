# Changelog

All notable changes to this project are recorded here. Dates are inclusive of
each audit-and-fix round; the project went through 5 rounds of structured
review before initial portfolio release.

## [0.1.0] — Initial portfolio release

### Round 5 — Pool hardening and UX correctness

* `ConnectionPool` validates `max_per_host >= 1` and `max_idle_seconds > 0` at
  construction.
* CLI `--pool-size` / `--pool-idle` reject non-positive values at parse time
  via `_positive_int` / `_positive_float` argparse types.
* `apiclient auth test` now raises `AuthError` when no authentication flag is
  supplied — an unauthenticated request can never test authentication.
* Direct unit tests for `_PrefixedStream` (under-read, exact, over-read, empty
  prefix); CLI integration test for `--keep-alive`; explicit coverage for
  rejection of `--keep-alive --transport urllib`.

### Round 4 — Protocol correctness and CLI completeness

* Parser skips 1xx informational responses per RFC 7230 §3.1.2.
* `Content-Length` parser requires `1*DIGIT`; rejects leading sign / empty
  / non-digit values.
* `Response.text` falls back to utf-8 + `errors="replace"` on unknown charset.
* `redact_url` masks `user[:password]@` userinfo as `<redacted>@host:port`.
* `parse_url` rejects URLs carrying userinfo; users must use `--basic` or
  `BasicAuth` explicitly.
* `fetch_many` rejects `concurrency < 1`; CLI `--concurrency` / `--count`
  validate via `_positive_int`.
* `--keep-alive`, `--pool-size`, `--pool-idle` CLI flags wire through a
  `ConnectionPool` into the raw transport.
* All four CLI handlers wrap the client in `with` so pooled sockets are
  released cleanly.
* `auth.secrets()` is wired into `ApiClient.send`; trace events are masked
  for any plaintext secret occurrence after all redirect hops complete.
* `_can_pool_response` and `keep_alive_requested` narrow their predicates to
  exclude `Connection: upgrade` (hijacked sockets must not be pooled).

### Round 3 — Lifecycle, docs, and tidy

* Empty-credential auth strategies raise `ValueError` at construction.
* Unknown `transport` value (CLI or profile) raises `ConfigError`.
* `ApiClient` is a context manager; `__exit__` calls `transport.close()`.
* Dead code removed: `redact_text`, `TraceLog`, `measure()`.
* `TimingInfo.as_dict()` adopted by `response_summary`.
* `ConfigError.exit_code = 10` (distinct from `InvalidUrlError`).
* All four ADRs gained "Alternatives considered" sections; new
  `docs/architecture.md`; `protocol-mastery-checklist.md` links every
  checkbox to the implementing file and the test that verifies it.

### Round 2 — Re-audit hardening

* `_dump_toml` emits root scalars before tables for correct round-trip.
* `ConnectionPool._looks_alive` treats pending stale bytes as poisoned.
* `RetryPolicy.delay_for` guards against `attempt_number < 1`.
* `Retry-After` accepts decimal seconds in addition to integers and
  HTTP-dates; negative values clamp to zero.
* Async fan-out uses `asyncio.TaskGroup` with `except* CancelledError`
  suppression so fail-fast doesn't leak cancellations.
* `PageNumberPaginator` and `LinkHeaderPaginator` gained cycle guards
  matching the offset / cursor strategies.
* `Request.__post_init__` rejects non-`bytes`/`str`/`None` body at
  construction.

### Round 1 — Foundation pass

* Hand-rolled HTTP/1.1 parser: status line, case-insensitive headers,
  Content-Length and chunked body framing, trailers, 204/205/304/HEAD
  bodyless rules, parser safety limits (header / body / chunk / line / field
  counts).
* `Set-Cookie` is kept separate from comma-joinable headers (RFC 6265 §3).
* Empty-body POST/PUT/PATCH declares `Content-Length: 0` per RFC 7230 §3.3.2.
* `socket_transport` enforces `TimeoutConfig.total` as a hard deadline via
  `_FirstByteSocket`.
* `RedirectPolicy` honors max hops, strips cross-host credentials, and
  rewrites POST → GET on 303 (and 301/302 per common practice).
* `urllib_transport` derives its framing from response headers and captures
  DNS timing pre-flight for parity with the raw transport's trace.
* `Link` header parser handles multi-token `rel` values and commas inside
  angle-bracketed URLs.
* `RetryPolicy` applies jitter once with a final `max_backoff` clamp; never
  zeros the jitter out at the ceiling.
* `pyproject.toml` is stdlib-only at runtime; `pytest` is optional.

### Final polish pass

* Added `LICENSE` (MIT) to match the existing pyproject classifier.
* Added `.gitignore` covering Python build artefacts, test caches, local
  `.apiclient.toml`, and common editor temp files.
* `pyproject.toml` now declares `license = { file = "LICENSE" }` and a
  `[project.urls]` block (Documentation / Source / Changelog).
* Audit-framework polish: project-named `logging` Logger replaces
  `print(file=sys.stderr)` for CLI diagnostics; `--version` flag wired
  through `importlib.metadata`; README gained an "Exit codes" table and
  per-flag examples (`--fail`, `-H`, `--param`, `--output table`); demo
  server query parameters now return `400 Bad Request` on bad input via
  `server.endpoints._BadRequest` / `_int_query`; ADR 0002 gained a Risks
  section covering semaphore starvation, cancellation-vs-thread-work
  asymmetry, and the per-call concurrency cap; README documents the
  query-parameter surface for `/items`, `/flaky`, `/redirect`, `/private`,
  `/echo`.
* Author identity finalised: pyproject.toml + LICENSE now name Princeton
  Afeez; placeholder TODO removed.

## [0.1.1] — 2026-06-04

### Tooling and documentation

* Added root **`requirements.txt`** (`-e .` plus pytest, pytest-cov, ruff).
* **`pyproject.toml`**: version `0.1.1`, Beta classifier, Python 3.13 classifier,
  Issues URL, coverage floor raised to **90%**, `[tool.coverage.run]` for `apiclient`.
* **`.gitignore`**: virtualenvs, `.ruff_cache/`, `.cursor/`, OS junk, `*.log`.
* **README**: install via `requirements.txt`, test counts, `verify_submission.py`,
  ruff command, primary pytest workflow.
* **CI (`.github/workflows/test.yml`)**: `pip install -r requirements.txt`;
  pytest + ruff on Ubuntu and Windows (3.12, 3.14); `verify_submission` job;
  unittest matrix installs editable package only.

### Test expansion

* Suite grew to **350+ tests** (~**96%** coverage): parser/CLI/client/pool/config/
  transport/async/pagination/resilience exhaustive modules; submission docs
  (`docs/SUBMISSION.md`, `demo-questions.md`, `report-outline.md`,
  `windows-testing.md`) and `scripts/verify_submission.py`.

## Unreleased

### Third portfolio audit pass

* ``ApiClient.send`` validates URLs via ``require_http_url``.
* ``ClientConfig`` adds ``no_follow_redirects``, ``fail``, ``retry_statuses``,
  ``redirect_statuses`` (CSV strings) with env overrides.
* ``configure list`` always includes the implicit ``default`` profile name.
* ``HEAD`` requests never send a body on raw or urllib transports.
* Redirect tests for default strip vs ``preserve_auth_across_hosts``.
* CI: Python 3.14 matrix job; ruff checks ``server/``; extra output/parser tests.
* Demo ``FLAKY_COUNTS`` documented as single-process only.

### Second portfolio polish pass

* ``--retry-non-idempotent`` / ``--no-retry-non-idempotent`` use
  ``BooleanOptionalAction`` so CLI can override profile TOML.
* ``ClientConfig`` extended with redirect, retry backoff, and pool settings;
  matching ``APICLIENT_*`` env vars.
* ``--profile default`` allowed when ``[profiles.default]`` is absent.
* ``fetch_many`` returns ``results_by_url`` / ``errors_by_url`` parallel to input.
* ``require_http_url`` validates URLs in ``ApiClient.request`` and ``resolve_url``.
* ``bench`` rejects ``--trace`` with ``--concurrency > 1``; README academic blurb;
  ``[project.urls]``; Python 3.14 classifier; CLI output tests; TE+CL fixture test.
* CLI imports moved to module top (ruff ``E402`` clean).

### Portfolio evaluation fixes

* Unknown ``--profile`` names raise ``ConfigError``; ``configure set`` validates
  keys before writing TOML.
* Cross-host redirects strip auth query parameters and custom API-key header
  names via ``AuthStrategy`` metadata.
* ``UrllibTransport`` rejects URL userinfo like the raw transport.
* ``fetch_many`` returns successful responses in input URL order; warns when
  ``trace=True`` with ``concurrency > 1``.
* Parser skips all 1xx responses including ``101``.
* ``APICLIENT_REDACT_PARAMS`` extends URL redaction; example config at
  ``docs/examples/apiclient.toml.example``.
* README documents out-of-scope features, configure exit semantics, demo
  credentials, and expanded library exports.
* CI: Windows matrix, ``ruff``, ``pytest-cov`` (80% floor).
* ``Content-Length`` is set only in the transport layer.

The project is currently at portfolio-release state; future changes will be
recorded above this line.
