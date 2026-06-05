"""Regression tests for Round 4 (S1-S16)."""

from __future__ import annotations

import asyncio
import socketserver
import threading
import time
import unittest
from time import monotonic

from apiclient.client import ApiClient
from apiclient.concurrency import fetch_many
from apiclient.exceptions import (
    InvalidUrlError,
    ProtocolError,
    RequestTimeout,
)
from apiclient.http.parser import parse_response_bytes
from apiclient.http.url import parse_url
from apiclient.models import CaseInsensitiveHeaders, Response
from apiclient.observability.redaction import redact_url
from apiclient.resilience.timeout import TimeoutConfig
from apiclient.transport import ConnectionPool, RawSocketTransport
from apiclient.transport.socket_transport import _can_pool_response


class S1ConcurrencyValidationTests(unittest.TestCase):
    def test_fetch_many_rejects_zero(self) -> None:
        class _C:
            def request(self, m, u, **kw):  # noqa: ANN001
                return None

        with self.assertRaises(ValueError):
            asyncio.run(fetch_many(_C(), ["http://x/1"], concurrency=0))

    def test_cli_concurrency_argument_rejects_zero(self) -> None:
        from apiclient.cli.main import build_parser

        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["bench", "http://x", "--concurrency", "0"])


class S2BadCharsetTests(unittest.TestCase):
    def test_text_falls_back_to_utf8_for_unknown_codec(self) -> None:
        response = Response(
            200,
            "OK",
            CaseInsensitiveHeaders({"Content-Type": "text/plain; charset=not-a-codec"}),
            b"hello",
            "http://x",
        )
        self.assertEqual(response.text, "hello")


class S3ContentLengthSignTests(unittest.TestCase):
    def test_leading_plus_rejected(self) -> None:
        with self.assertRaises(ProtocolError):
            parse_response_bytes(b"HTTP/1.1 200 OK\r\nContent-Length: +5\r\n\r\nhello")

    def test_empty_value_rejected(self) -> None:
        with self.assertRaises(ProtocolError):
            parse_response_bytes(b"HTTP/1.1 200 OK\r\nContent-Length: \r\n\r\n")

    def test_alphabetic_rejected(self) -> None:
        with self.assertRaises(ProtocolError):
            parse_response_bytes(b"HTTP/1.1 200 OK\r\nContent-Length: abc\r\n\r\n")


class S4SkipInformationalTests(unittest.TestCase):
    def test_100_continue_is_skipped(self) -> None:
        raw = (
            b"HTTP/1.1 100 Continue\r\n\r\n"
            b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello"
        )
        parsed = parse_response_bytes(raw)
        self.assertEqual(parsed.status_code, 200)
        self.assertEqual(parsed.body, b"hello")

    def test_multiple_1xx_are_all_skipped(self) -> None:
        raw = (
            b"HTTP/1.1 102 Processing\r\n\r\n"
            b"HTTP/1.1 103 Early Hints\r\nLink: </styles.css>\r\n\r\n"
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"
        )
        parsed = parse_response_bytes(raw)
        self.assertEqual(parsed.status_code, 200)
        self.assertEqual(parsed.body, b"ok")


class S5UserinfoRedactionTests(unittest.TestCase):
    def test_full_userinfo_masked(self) -> None:
        result = redact_url("https://user:supersecret@example.test/api")
        self.assertNotIn("supersecret", result)
        self.assertNotIn("user", result.split("@", 1)[0])
        self.assertIn("<redacted>@example.test", result)

    def test_user_only_masked(self) -> None:
        result = redact_url("http://user@host/p")
        self.assertIn("<redacted>@host", result)

    def test_no_userinfo_unchanged(self) -> None:
        self.assertEqual(redact_url("http://host/p"), "http://host/p")

    def test_redaction_preserves_port(self) -> None:
        result = redact_url("http://u:p@host:8080/p?token=x")
        self.assertIn("host:8080", result)


class S8AuthSecretsTraceMaskingTests(unittest.TestCase):
    def test_secret_in_trace_is_masked(self) -> None:
        from apiclient.auth import BearerTokenAuth
        from apiclient.transport.base import Transport

        # A fake auth strategy whose token sneaks into a trace event via the URL.
        class _LeakyTransport(Transport):
            def send(self, request, timeout):  # noqa: ANN001
                request.trace.append(f"Sending to {request.url} with secret-token-xyz")
                return Response(200, "OK", CaseInsensitiveHeaders(), b"", request.url, request=request)

        client = ApiClient(transport=_LeakyTransport())
        response = client.request(
            "GET",
            "http://example.test/",
            auth=BearerTokenAuth("secret-token-xyz"),
            trace=True,
        )
        joined = "\n".join(response.request.trace)
        self.assertNotIn("secret-token-xyz", joined)


class S9URLUserinfoTests(unittest.TestCase):
    def test_user_pass_in_url_rejected(self) -> None:
        with self.assertRaises(InvalidUrlError):
            parse_url("http://user:pass@host/")

    def test_user_only_in_url_rejected(self) -> None:
        with self.assertRaises(InvalidUrlError):
            parse_url("http://user@host/")


class S13PoolKeepAlivePredicateTests(unittest.TestCase):
    def test_upgrade_is_not_keep_alive(self) -> None:
        self.assertFalse(
            _can_pool_response(
                "HTTP/1.1", CaseInsensitiveHeaders({"Connection": "upgrade"})
            )
        )

    def test_plain_keep_alive_value_is_kept(self) -> None:
        self.assertTrue(
            _can_pool_response(
                "HTTP/1.1", CaseInsensitiveHeaders({"Connection": "keep-alive"})
            )
        )


def _start_server(handler_cls):
    server = socketserver.TCPServer(("127.0.0.1", 0), handler_cls)
    server.allow_reuse_address = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


class S14TotalTimeoutEndToEndTests(unittest.TestCase):
    def test_total_timeout_fires_against_slow_server(self) -> None:
        class _Slow(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                time.sleep(1.5)

        server, thread = _start_server(_Slow)
        try:
            host, port = server.server_address
            client = ApiClient(
                timeout=TimeoutConfig(connect=10, read=10, total=0.3),
            )
            start = monotonic()
            with self.assertRaises(RequestTimeout):
                client.request("GET", f"http://{host}:{port}/")
            elapsed = monotonic() - start
            self.assertLess(elapsed, 1.0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class S15ContextManagerClosesPoolTests(unittest.TestCase):
    def test_exit_drains_pool_buckets(self) -> None:
        class _KeepAlive(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                for _ in range(2):
                    data = b""
                    while b"\r\n\r\n" not in data:
                        chunk = self.request.recv(4096)
                        if not chunk:
                            return
                        data += chunk
                    self.request.sendall(
                        b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
                    )

        server, thread = _start_server(_KeepAlive)
        try:
            host, port = server.server_address
            pool = ConnectionPool()
            with ApiClient(transport=RawSocketTransport(pool=pool)) as client:
                client.request("GET", f"http://{host}:{port}/a")
                client.request("GET", f"http://{host}:{port}/b")
                # While inside the context, the bucket should hold a socket.
            # After __exit__, the pool's buckets must be empty.
            total = sum(len(b) for b in pool._idle.values())
            self.assertEqual(total, 0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
