"""Transport layer edge-case tests."""

from __future__ import annotations

import unittest
from apiclient.exceptions import ConnectionFailure, InvalidUrlError
from apiclient.http.url import parse_url
from apiclient.models import CaseInsensitiveHeaders, Request
from apiclient.resilience.timeout import TimeoutConfig
from apiclient.transport.socket_transport import RawSocketTransport
from apiclient.transport.urllib_transport import UrllibTransport
from tests.helpers import wsgi_server


class UrllibTransportTests(unittest.TestCase):
    def test_rejects_userinfo_in_url(self) -> None:
        transport = UrllibTransport()
        request = Request("GET", "http://user:pass@127.0.0.1/")
        with self.assertRaises(InvalidUrlError):
            transport.send(request, TimeoutConfig())

    def test_head_omits_body_on_wire(self) -> None:
        with wsgi_server() as base:
            request = Request(
                "HEAD",
                f"{base}/health",
                body=b"should-not-send",
            )
            response = UrllibTransport().send(request, TimeoutConfig())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, b"")


class RawSocketTransportTests(unittest.TestCase):
    def test_head_omits_body(self) -> None:
        with wsgi_server() as base:
            request = Request("HEAD", f"{base}/health", body=b"ignored")
            response = RawSocketTransport().send(request, TimeoutConfig())
        self.assertEqual(response.status_code, 200)

    def test_keep_alive_pool_reuse(self) -> None:
        from apiclient.transport.pool import ConnectionPool

        with wsgi_server() as base:
            pool = ConnectionPool(max_per_host=2, max_idle_seconds=30.0)
            transport = RawSocketTransport(pool=pool)
            url = f"{base}/health"
            first = transport.send(Request("GET", url), TimeoutConfig())
            second = transport.send(Request("GET", url), TimeoutConfig())
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        transport.close()

    def test_dns_failure_raises_connection_failure(self) -> None:
        transport = RawSocketTransport()
        request = Request("GET", "http://this-host-definitely-does-not-exist-xyz.invalid/")
        with self.assertRaises(ConnectionFailure):
            transport.send(request, TimeoutConfig(connect=1.0, read=1.0))


class ParseUrlTransportIntegrationTests(unittest.TestCase):
    def test_https_default_port(self) -> None:
        parsed = parse_url("https://example.test/path")
        self.assertEqual(parsed.port, 443)


if __name__ == "__main__":
    unittest.main()
