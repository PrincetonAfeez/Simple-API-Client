"""Regression tests for Round 5 (T1-T8)."""

from __future__ import annotations

import argparse
import io
import socketserver
import threading
import unittest
from unittest.mock import patch

from apiclient.cli.main import build_parser
from apiclient.cli.main import main as cli_main
from apiclient.exceptions import ConfigError
from apiclient.http.parser import _PrefixedStream
from apiclient.transport.pool import ConnectionPool


class T1PoolValidationTests(unittest.TestCase):
    def test_zero_max_per_host_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ConnectionPool(max_per_host=0)

    def test_negative_max_per_host_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ConnectionPool(max_per_host=-1)

    def test_zero_idle_seconds_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ConnectionPool(max_idle_seconds=0)

    def test_negative_idle_seconds_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ConnectionPool(max_idle_seconds=-5.0)


class T2CliPoolSizeTests(unittest.TestCase):
    def test_pool_size_zero_rejected(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["get", "http://x", "--pool-size", "0"])

    def test_pool_size_negative_rejected(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["get", "http://x", "--pool-size", "-1"])


class T3CliPoolIdleTests(unittest.TestCase):
    def test_pool_idle_zero_rejected(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["get", "http://x", "--pool-idle", "0"])

    def test_pool_idle_negative_rejected(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["get", "http://x", "--pool-idle", "-3.5"])


class T4AuthTestRequiresStrategyTests(unittest.TestCase):
    def test_auth_test_without_flag_raises(self) -> None:
        with patch("sys.stdout", new=io.StringIO()), patch("sys.stderr", new=io.StringIO()):
            rc = cli_main(["auth", "test", "http://127.0.0.1:1/health"])
        # AuthError is exit_code 6 per exceptions.py.
        self.assertEqual(rc, 6)


class T5PrefixedStreamTests(unittest.TestCase):
    class _InnerStream:
        def __init__(self, data: bytes) -> None:
            self.data = bytearray(data)
            self.calls = 0

        def recv(self, size: int) -> bytes:
            self.calls += 1
            chunk = bytes(self.data[:size])
            del self.data[:size]
            return chunk

    def test_returns_prefix_first(self) -> None:
        inner = self._InnerStream(b"WORLD")
        stream = _PrefixedStream(b"hello", inner)
        self.assertEqual(stream.recv(10), b"hello")
        self.assertEqual(inner.calls, 0)

    def test_chunks_prefix_under_requested_size(self) -> None:
        inner = self._InnerStream(b"")
        stream = _PrefixedStream(b"hello", inner)
        self.assertEqual(stream.recv(2), b"he")
        self.assertEqual(stream.recv(2), b"ll")
        self.assertEqual(stream.recv(2), b"o")
        self.assertEqual(inner.calls, 0)

    def test_delegates_to_inner_after_prefix(self) -> None:
        inner = self._InnerStream(b"WORLD")
        stream = _PrefixedStream(b"hi", inner)
        self.assertEqual(stream.recv(2), b"hi")
        self.assertEqual(stream.recv(5), b"WORLD")
        self.assertEqual(inner.calls, 1)

    def test_empty_prefix_just_delegates(self) -> None:
        inner = self._InnerStream(b"abc")
        stream = _PrefixedStream(b"", inner)
        self.assertEqual(stream.recv(10), b"abc")
        self.assertEqual(inner.calls, 1)


def _start_keep_alive_server(handler_cls):
    server = socketserver.TCPServer(("127.0.0.1", 0), handler_cls)
    server.allow_reuse_address = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


class T6CliKeepAliveIntegrationTests(unittest.TestCase):
    def test_cli_keep_alive_reuses_socket(self) -> None:
        served = {"count": 0}

        class _Handler(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                for _ in range(2):
                    data = b""
                    while b"\r\n\r\n" not in data:
                        chunk = self.request.recv(4096)
                        if not chunk:
                            return
                        data += chunk
                    served["count"] += 1
                    self.request.sendall(
                        b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
                    )

        server, thread = _start_keep_alive_server(_Handler)
        try:
            host, port = server.server_address
            # Two separate CLI calls would reach two separate sockets because
            # the CLI creates a fresh client each call. Instead, exercise the
            # pool inside one bench run with --concurrency 1 so the second
            # request reuses the first socket.
            with patch("sys.stdout", new=io.StringIO()):
                rc = cli_main(
                    [
                        "bench",
                        f"http://{host}:{port}/items/{{id}}",
                        "--keep-alive",
                        "--count",
                        "2",
                        "--concurrency",
                        "1",
                    ]
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(rc, 0)
        self.assertEqual(served["count"], 2)


class T7KeepAliveUrllibConflictTests(unittest.TestCase):
    def test_keep_alive_with_urllib_transport_raises_config_error(self) -> None:
        from apiclient.cli.main import make_client
        from apiclient.config import ClientConfig

        ns = argparse.Namespace(
            transport="urllib",
            retries=None,
            retry_non_idempotent=None,
            backoff_factor=None,
            retry_jitter=None,
            retry_max_backoff=None,
            retry_status=[],
            max_redirects=None,
            preserve_auth_across_hosts=None,
            redirect_status=[],
            timeout=None,
            connect_timeout=None,
            read_timeout=None,
            keep_alive=True,
            pool_size=None,
            pool_idle=None,
        )
        with self.assertRaises(ConfigError) as ctx:
            make_client(ns, ClientConfig())
        self.assertIn("urllib", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
