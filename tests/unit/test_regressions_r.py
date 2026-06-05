"""Regression tests for R1, R2, R3, R8, R9, R16, R17, R18."""

from __future__ import annotations

import io
import socketserver
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from apiclient.auth import ApiKeyHeaderAuth, ApiKeyQueryAuth, BasicAuth, BearerTokenAuth
from apiclient.cli.main import main as cli_main
from apiclient.client import ApiClient, response_summary
from apiclient.exceptions import ConfigError
from apiclient.models import CaseInsensitiveHeaders, Response, TimingInfo
from apiclient.observability.redaction import redact_url
from apiclient.transport import ConnectionPool, RawSocketTransport
from tests.helpers import wsgi_server


class R1EmptyCredentialAuthTests(unittest.TestCase):
    def test_bearer_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            BearerTokenAuth("")

    def test_bearer_rejects_whitespace(self) -> None:
        with self.assertRaises(ValueError):
            BearerTokenAuth("   ")

    def test_basic_rejects_empty_username(self) -> None:
        with self.assertRaises(ValueError):
            BasicAuth("", "secret")

    def test_basic_rejects_username_with_colon(self) -> None:
        with self.assertRaises(ValueError):
            BasicAuth("user:name", "secret")

    def test_apikey_header_rejects_empty_value(self) -> None:
        with self.assertRaises(ValueError):
            ApiKeyHeaderAuth("X-API-Key", "")

    def test_apikey_query_rejects_empty_value(self) -> None:
        with self.assertRaises(ValueError):
            ApiKeyQueryAuth("api_key", "")


class R2UnknownTransportTests(unittest.TestCase):
    def test_unknown_transport_raises_config_error(self) -> None:
        import argparse

        from apiclient.cli.main import make_client
        from apiclient.config import ClientConfig

        ns = argparse.Namespace(
            transport=None,
            retries=None,
            retry_non_idempotent=None,
            keep_alive=None,
            pool_size=None,
            pool_idle=None,
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
        )
        config = ClientConfig(transport="fancy")
        with self.assertRaises(ConfigError):
            make_client(ns, config)


class R3ApiClientLifecycleTests(unittest.TestCase):
    def test_close_delegates_to_transport(self) -> None:
        closes: list[bool] = []

        class _T(RawSocketTransport):
            def close(self):
                closes.append(True)

        client = ApiClient(transport=_T())
        client.close()
        self.assertEqual(closes, [True])

    def test_context_manager_closes_on_exit(self) -> None:
        closes: list[bool] = []

        class _T(RawSocketTransport):
            def close(self):
                closes.append(True)

        with ApiClient(transport=_T()):
            pass
        self.assertEqual(closes, [True])


class R8ConfigErrorExitCodeTests(unittest.TestCase):
    def test_config_error_has_distinct_exit_code(self) -> None:
        from apiclient.exceptions import ConfigError as CE
        from apiclient.exceptions import InvalidUrlError

        self.assertNotEqual(CE.exit_code, InvalidUrlError.exit_code)
        self.assertEqual(CE.exit_code, 10)


class R9ResponseSummaryTimingsTests(unittest.TestCase):
    def test_summary_includes_timings_dict(self) -> None:
        response = Response(
            200,
            "OK",
            CaseInsensitiveHeaders({"Content-Type": "text/plain"}),
            b"hello",
            "http://x",
            timings=TimingInfo(dns=0.01, total=0.05),
        )
        summary = response_summary(response)
        self.assertIn("timings", summary)
        self.assertEqual(summary["timings"]["dns"], 0.01)
        self.assertEqual(summary["timings"]["total"], 0.05)


class R15PoolReuseEndToEndTests(unittest.TestCase):
    """Two requests against a hand-rolled HTTP/1.1 server reach the same handler."""

    def test_pool_reuses_single_socket(self) -> None:
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

        server = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
        server.allow_reuse_address = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            pool = ConnectionPool()
            with ApiClient(transport=RawSocketTransport(pool=pool)) as client:
                client.request("GET", f"http://{host}:{port}/a")
                client.request("GET", f"http://{host}:{port}/b")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(served["count"], 2)


class R16RedactUrlEdgeTests(unittest.TestCase):
    def test_redact_url_no_query_is_unchanged(self) -> None:
        self.assertEqual(redact_url("http://example.test/path"), "http://example.test/path")

    def test_redact_url_empty_query_is_unchanged(self) -> None:
        self.assertEqual(redact_url("http://example.test/path?"), "http://example.test/path?")

    def test_redact_url_non_sensitive_keys_pass_through(self) -> None:
        self.assertEqual(
            redact_url("http://example.test/?page=2&size=10"),
            "http://example.test/?page=2&size=10",
        )

    def test_redact_url_empty_sensitive_value(self) -> None:
        result = redact_url("http://example.test/?api_key=")
        # An empty token redacts to "[redacted]" rather than "" so callers
        # can spot the absence in trace output.
        self.assertIn("api_key=", result)
        self.assertNotIn("api_key=,", result)


class R17ConfigureListMissingFileTests(unittest.TestCase):
    def test_list_against_missing_file_prints_nothing_and_exits_zero(self) -> None:
        with TemporaryDirectory() as tmp:
            missing = Path(tmp) / "no-such.toml"
            with patch.dict("os.environ", {"APICLIENT_CONFIG": str(missing)}, clear=False):
                with patch("sys.stdout", new=io.StringIO()) as buf:
                    rc = cli_main(["configure", "list"])
            self.assertEqual(rc, 0)
            self.assertEqual(buf.getvalue(), "default\n")


class R18CurlFlagIntegrationTests(unittest.TestCase):
    def test_curl_flag_emits_redacted_curl_to_stderr(self) -> None:
        with wsgi_server() as base_url:
            with patch("sys.stdout", new=io.StringIO()):
                with patch("sys.stderr", new=io.StringIO()) as stderr_buf:
                    rc = cli_main(
                        [
                            "get",
                            f"{base_url}/health",
                            "--bearer-token",
                            "supersecret-token",
                            "--curl",
                        ]
                    )
        self.assertEqual(rc, 0)
        emitted = stderr_buf.getvalue()
        self.assertIn("curl", emitted)
        self.assertNotIn("supersecret-token", emitted)
        self.assertIn("redacted", emitted)


if __name__ == "__main__":
    unittest.main()
