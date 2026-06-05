# Protocol Mastery Checklist

Each box links to the implementing source file and the test that verifies it.

- [x] Parse URLs into scheme, hostname, port, path, and query —
  [src/apiclient/http/url.py](../src/apiclient/http/url.py),
  [tests/unit/test_url_encoding.py](../tests/unit/test_url_encoding.py)
- [x] Infer default ports for HTTP and HTTPS —
  [src/apiclient/http/url.py](../src/apiclient/http/url.py),
  [tests/unit/test_url_encoding.py](../tests/unit/test_url_encoding.py)
- [x] Resolve hostnames before TCP connect —
  [src/apiclient/transport/socket_transport.py](../src/apiclient/transport/socket_transport.py)
- [x] Open TCP sockets explicitly —
  [src/apiclient/transport/socket_transport.py](../src/apiclient/transport/socket_transport.py),
  [tests/integration/test_client_against_wsgi.py](../tests/integration/test_client_against_wsgi.py)
- [x] Wrap TLS with `ssl` for HTTPS —
  [src/apiclient/transport/socket_transport.py](../src/apiclient/transport/socket_transport.py)
- [x] Serialize HTTP/1.1 request lines and headers with CRLF —
  [src/apiclient/transport/socket_transport.py](../src/apiclient/transport/socket_transport.py),
  [tests/unit/test_socket_transport.py](../tests/unit/test_socket_transport.py)
- [x] Include `Host`, `Connection`, and `Content-Length` deliberately —
  [src/apiclient/transport/socket_transport.py](../src/apiclient/transport/socket_transport.py),
  [tests/unit/test_socket_transport.py](../tests/unit/test_socket_transport.py)
- [x] Read headers across partial `recv()` calls —
  [src/apiclient/http/parser.py](../src/apiclient/http/parser.py),
  [tests/unit/test_http_parser.py](../tests/unit/test_http_parser.py)
- [x] Parse status line and case-insensitive headers —
  [src/apiclient/http/parser.py](../src/apiclient/http/parser.py),
  [src/apiclient/models.py](../src/apiclient/models.py),
  [tests/unit/test_models.py](../tests/unit/test_models.py)
- [x] Decode `Content-Length` bodies —
  [src/apiclient/http/parser.py](../src/apiclient/http/parser.py),
  [tests/unit/test_http_parser.py](../tests/unit/test_http_parser.py)
- [x] Decode `Transfer-Encoding: chunked` bodies —
  [src/apiclient/http/parser.py](../src/apiclient/http/parser.py),
  [tests/unit/test_chunked_parser.py](../tests/unit/test_chunked_parser.py),
  [tests/integration/test_chunked_test_server.py](../tests/integration/test_chunked_test_server.py)
- [x] Capture chunked-body trailers —
  [src/apiclient/http/parser.py](../src/apiclient/http/parser.py),
  [tests/unit/test_parser_fixtures.py](../tests/unit/test_parser_fixtures.py)
- [x] Avoid reading bodies for `HEAD`, `204`, `205`, `304` —
  [src/apiclient/http/parser.py](../src/apiclient/http/parser.py),
  [tests/unit/test_http_parser.py](../tests/unit/test_http_parser.py)
- [x] Enforce parser safety limits (header size, body size, chunk size,
  field count, trailer count) —
  [src/apiclient/http/parser.py](../src/apiclient/http/parser.py),
  [tests/unit/test_http_parser.py](../tests/unit/test_http_parser.py),
  [tests/unit/test_regressions.py](../tests/unit/test_regressions.py)
- [x] Keep `Set-Cookie` separate from comma-joinable headers —
  [src/apiclient/http/parser.py](../src/apiclient/http/parser.py)
- [x] Honor `Connection: close` and the HTTP/1.0 keep-alive convention —
  [src/apiclient/transport/socket_transport.py](../src/apiclient/transport/socket_transport.py),
  [tests/unit/test_regressions.py](../tests/unit/test_regressions.py)
- [x] Connection pool with idle reuse, peek liveness, and broken-fd safety —
  [src/apiclient/transport/pool.py](../src/apiclient/transport/pool.py),
  [tests/unit/test_regressions_nn.py](../tests/unit/test_regressions_nn.py)
- [x] Distinguish network failures, timeouts, and retryable HTTP responses —
  [src/apiclient/resilience/retry.py](../src/apiclient/resilience/retry.py),
  [tests/unit/test_retry_policy.py](../tests/unit/test_retry_policy.py),
  [tests/integration/test_flaky_retries.py](../tests/integration/test_flaky_retries.py)
- [x] Apply exponential backoff with jitter and `Retry-After` —
  [src/apiclient/resilience/retry.py](../src/apiclient/resilience/retry.py),
  [tests/unit/test_retry_jitter.py](../tests/unit/test_retry_jitter.py)
- [x] Follow redirects with cross-host auth stripping and 303 POST→GET —
  [src/apiclient/http/redirects.py](../src/apiclient/http/redirects.py),
  [tests/unit/test_redirect_policy.py](../tests/unit/test_redirect_policy.py),
  [tests/integration/test_redirect_policy.py](../tests/integration/test_redirect_policy.py)
- [x] Redact credentials in trace and curl output —
  [src/apiclient/observability/redaction.py](../src/apiclient/observability/redaction.py),
  [tests/unit/test_auth_redaction.py](../tests/unit/test_auth_redaction.py)
- [x] Implement lazy pagination strategies with cycle guards —
  [src/apiclient/pagination/](../src/apiclient/pagination/),
  [tests/unit/test_pagination.py](../tests/unit/test_pagination.py),
  [tests/unit/test_paginators_extra.py](../tests/unit/test_paginators_extra.py)
- [x] Demonstrate the WSGI app contract —
  [server/wsgi_app.py](../server/wsgi_app.py),
  [tests/integration/test_client_against_wsgi.py](../tests/integration/test_client_against_wsgi.py)
- [x] Provide a library transport behind the same interface —
  [src/apiclient/transport/urllib_transport.py](../src/apiclient/transport/urllib_transport.py),
  [tests/integration/test_urllib_transport.py](../tests/integration/test_urllib_transport.py)
- [x] Asyncio fan-out with cancellation safety —
  [src/apiclient/concurrency/async_client.py](../src/apiclient/concurrency/async_client.py),
  [tests/unit/test_async_client.py](../tests/unit/test_async_client.py)
