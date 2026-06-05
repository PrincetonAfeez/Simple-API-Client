"""Tests for the HTTP parser."""

from __future__ import annotations

import unittest

from apiclient.exceptions import ProtocolError
from apiclient.http.parser import parse_response_bytes, read_response


class TinyStream:
    def __init__(self, data: bytes, chunk_size: int = 3) -> None:
        self.data = bytearray(data)
        self.chunk_size = chunk_size

    def recv(self, size: int) -> bytes:
        count = min(size, self.chunk_size, len(self.data))
        if count == 0:
            return b""
        out = bytes(self.data[:count])
        del self.data[:count]
        return out


class HttpParserTests(unittest.TestCase):
    def test_parses_content_length_with_partial_reads(self) -> None:
        raw = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: 12\r\n"
            b"\r\n"
            b'{"ok":true}\n'
        )
        parsed = read_response(TinyStream(raw, chunk_size=2))
        self.assertEqual(parsed.status_code, 200)
        self.assertEqual(parsed.headers["content-type"], "application/json")
        self.assertEqual(parsed.body, b'{"ok":true}\n')
        self.assertEqual(parsed.framing, "content-length")

    def test_rejects_malformed_status_line(self) -> None:
        with self.assertRaises(ProtocolError):
            parse_response_bytes(b"NOTHTTP 200 OK\r\nContent-Length: 0\r\n\r\n")

    def test_head_response_is_bodyless(self) -> None:
        parsed = parse_response_bytes(
            b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\nignored-body",
            method="HEAD",
        )
        self.assertEqual(parsed.body, b"")
        self.assertEqual(parsed.framing, "bodyless")

    def test_rejects_headers_over_limit(self) -> None:
        raw = b"HTTP/1.1 200 OK\r\nX-Big: " + b"a" * 100 + b"\r\n\r\n"
        with self.assertRaises(ProtocolError):
            read_response(TinyStream(raw, chunk_size=200), max_header_size=32)


if __name__ == "__main__":
    unittest.main()
