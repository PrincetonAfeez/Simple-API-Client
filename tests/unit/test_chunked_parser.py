"""Tests for the chunked parser."""

from __future__ import annotations

import unittest

from apiclient.exceptions import ProtocolError
from apiclient.http.parser import read_response


class TinyStream:
    def __init__(self, data: bytes, chunk_size: int = 4) -> None:
        self.data = bytearray(data)
        self.chunk_size = chunk_size

    def recv(self, size: int) -> bytes:
        count = min(size, self.chunk_size, len(self.data))
        if count == 0:
            return b""
        out = bytes(self.data[:count])
        del self.data[:count]
        return out


class ChunkedParserTests(unittest.TestCase):
    def test_decodes_chunked_body(self) -> None:
        raw = (
            b"HTTP/1.1 200 OK\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"\r\n"
            b"5\r\nhello\r\n6\r\n world\r\n0\r\n\r\n"
        )
        parsed = read_response(TinyStream(raw, chunk_size=3))
        self.assertEqual(parsed.body, b"hello world")
        self.assertEqual(parsed.framing, "chunked")

    def test_rejects_invalid_chunk_size(self) -> None:
        raw = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nZ\r\nboom\r\n0\r\n\r\n"
        with self.assertRaises(ProtocolError):
            read_response(TinyStream(raw))

    def test_rejects_chunk_over_limit(self) -> None:
        raw = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nA\r\n0123456789\r\n0\r\n\r\n"
        with self.assertRaises(ProtocolError):
            read_response(TinyStream(raw), max_chunk_size=4)


if __name__ == "__main__":
    unittest.main()
