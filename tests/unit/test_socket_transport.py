"""Tests for the socket transport."""

from __future__ import annotations

import unittest

from apiclient.exceptions import TransportError
from apiclient.http.url import parse_url
from apiclient.models import CaseInsensitiveHeaders, Request
from apiclient.transport.socket_transport import RawSocketTransport


class SerializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = RawSocketTransport()

    def test_get_request_omits_content_length(self) -> None:
        request = Request("GET", "http://example.test/")
        payload, headers, _keep = self.transport._serialize_request(request, parse_url(request.url))
        self.assertNotIn("Content-Length", headers)
        self.assertIn(b"GET / HTTP/1.1", payload)

    def test_empty_post_declares_zero_content_length(self) -> None:
        request = Request("POST", "http://example.test/echo")
        _payload, headers, _keep = self.transport._serialize_request(request, parse_url(request.url))
        self.assertEqual(headers["Content-Length"], "0")

    def test_post_with_body_sets_content_length(self) -> None:
        request = Request("POST", "http://example.test/echo", body=b'{"a":1}')
        _payload, headers, _keep = self.transport._serialize_request(request, parse_url(request.url))
        self.assertEqual(headers["Content-Length"], "7")

    def test_head_omits_body_on_wire(self) -> None:
        request = Request("HEAD", "http://example.test/", body=b"ignored")
        payload, headers, _ = self.transport._serialize_request(
            request, parse_url(request.url)
        )
        self.assertNotIn(b"ignored", payload)
        self.assertNotIn("Content-Length", headers)

    def test_header_with_crlf_is_rejected(self) -> None:
        request = Request(
            "GET",
            "http://example.test/",
            headers=CaseInsensitiveHeaders({"X-Bad": "value\r\nInjected: yes"}),
        )
        with self.assertRaises(TransportError):
            self.transport._serialize_request(request, parse_url(request.url))


if __name__ == "__main__":
    unittest.main()
