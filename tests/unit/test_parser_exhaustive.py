"""Exhaustive HTTP response parser edge-case tests."""

from __future__ import annotations

import unittest

from apiclient.exceptions import ProtocolError, RequestTimeout
from apiclient.http.parser import (
    DEFAULT_MAX_BODY_SIZE,
    DEFAULT_MAX_CHUNK_SIZE,
    DEFAULT_MAX_HEADER_LINES,
    DEFAULT_MAX_TRAILER_LINES,
    _BufferedReader,
    _PrefixedStream,
    _consume_trailers,
    _parse_header_block,
    _read_chunked_body,
    parse_response_bytes,
    read_response,
)


class TinyStream:
    def __init__(self, data: bytes, chunk_size: int = 4, *, fail_on_recv: Exception | None = None) -> None:
        self.data = bytearray(data)
        self.chunk_size = chunk_size
        self.fail_on_recv = fail_on_recv
        self.recv_calls = 0

    def recv(self, size: int) -> bytes:
        self.recv_calls += 1
        if self.fail_on_recv is not None:
            raise self.fail_on_recv
        count = min(size, self.chunk_size, len(self.data))
        if count == 0:
            return b""
        out = bytes(self.data[:count])
        del self.data[:count]
        return out


class ParserExhaustiveTests(unittest.TestCase):
    def test_skips_1xx_and_returns_final_response(self) -> None:
        raw = (
            b"HTTP/1.1 100 Continue\r\n\r\n"
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"
        )
        parsed = read_response(TinyStream(raw, chunk_size=2))
        self.assertEqual(parsed.status_code, 200)
        self.assertEqual(parsed.body, b"ok")

    def test_1xx_with_immediate_next_response(self) -> None:
        raw = (
            b"HTTP/1.1 100 Continue\r\n\r\n"
            b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nend"
        )
        parsed = read_response(TinyStream(raw, chunk_size=3))
        self.assertEqual(parsed.body, b"end")

    def test_recv_timeout_raises_request_timeout(self) -> None:
        stream = TinyStream(b"HTTP/1.1 200 OK\r\n", fail_on_recv=TimeoutError("timed out"))
        with self.assertRaises(RequestTimeout):
            read_response(stream)

    def test_header_block_timeout_raises_request_timeout(self) -> None:
        class SlowStream:
            def recv(self, size: int) -> bytes:
                raise TimeoutError("header timeout")

        with self.assertRaises(RequestTimeout):
            read_response(SlowStream())

    def test_connection_closed_before_headers(self) -> None:
        with self.assertRaises(ProtocolError):
            read_response(TinyStream(b""))

    def test_missing_status_line(self) -> None:
        with self.assertRaises(ProtocolError):
            _parse_header_block(b"\r\n")

    def test_malformed_status_code(self) -> None:
        with self.assertRaises(ProtocolError):
            _parse_header_block(b"HTTP/1.1 XX OK\r\n\r\n")

    def test_folded_header_rejected(self) -> None:
        with self.assertRaises(ProtocolError):
            _parse_header_block(b"HTTP/1.1 200 OK\r\n X-Folded: value\r\n\r\n")

    def test_malformed_header_line_without_colon(self) -> None:
        with self.assertRaises(ProtocolError):
            _parse_header_block(b"HTTP/1.1 200 OK\r\nBadHeader\r\n\r\n")

    def test_empty_header_name_rejected(self) -> None:
        with self.assertRaises(ProtocolError):
            _parse_header_block(b"HTTP/1.1 200 OK\r\n: value\r\n\r\n")

    def test_header_line_count_limit(self) -> None:
        lines = "HTTP/1.1 200 OK\r\n" + "".join(f"X-{i}: v\r\n" for i in range(5)) + "\r\n"
        with self.assertRaises(ProtocolError):
            _parse_header_block(lines.encode(), max_lines=3)

    def test_duplicate_header_joined(self) -> None:
        version, status, reason, headers, _ = _parse_header_block(
            b"HTTP/1.1 200 OK\r\nX-Multi: a\r\nX-Multi: b\r\n\r\n"
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-Multi"], "a, b")

    def test_set_cookie_kept_separately(self) -> None:
        _, _, _, headers, cookies = _parse_header_block(
            b"HTTP/1.1 200 OK\r\nSet-Cookie: a=1\r\nSet-Cookie: b=2\r\n\r\n"
        )
        self.assertEqual(cookies, ["a=1", "b=2"])
        self.assertEqual(headers["Set-Cookie"], "b=2")

    def test_invalid_content_length_non_digit(self) -> None:
        raw = b"HTTP/1.1 200 OK\r\nContent-Length: abc\r\n\r\n"
        with self.assertRaises(ProtocolError):
            read_response(TinyStream(raw))

    def test_invalid_content_length_empty(self) -> None:
        raw = b"HTTP/1.1 200 OK\r\nContent-Length:   \r\n\r\n"
        with self.assertRaises(ProtocolError):
            read_response(TinyStream(raw))

    def test_content_length_exceeds_max_body(self) -> None:
        raw = b"HTTP/1.1 200 OK\r\nContent-Length: 99\r\n\r\n" + b"x" * 99
        with self.assertRaises(ProtocolError):
            read_response(TinyStream(raw), max_body_size=10)

    def test_connection_close_body_until_eof(self) -> None:
        raw = b"HTTP/1.1 200 OK\r\n\r\npayload"
        parsed = read_response(TinyStream(raw, chunk_size=2))
        self.assertEqual(parsed.body, b"payload")
        self.assertEqual(parsed.framing, "connection-close")

    def test_connection_close_body_limit(self) -> None:
        raw = b"HTTP/1.1 200 OK\r\n\r\n" + b"x" * 20
        with self.assertRaises(ProtocolError):
            read_response(TinyStream(raw), max_body_size=5)

    def test_buffered_reader_connection_closed_during_ensure(self) -> None:
        reader = _BufferedReader(TinyStream(b""))
        with self.assertRaises(ProtocolError):
            reader.read_exact(5)

    def test_buffered_reader_line_too_long(self) -> None:
        reader = _BufferedReader(TinyStream(b"x" * 50))
        with self.assertRaises(ProtocolError):
            reader.read_line(max_line_size=10)

    def test_buffered_reader_closed_before_crlf_line(self) -> None:
        reader = _BufferedReader(TinyStream(b"no newline here"))
        with self.assertRaises(ProtocolError):
            reader.read_line(max_line_size=100)

    def test_chunked_missing_chunk_size_line(self) -> None:
        raw = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n\r\n0\r\n\r\n"
        with self.assertRaises(ProtocolError):
            read_response(TinyStream(raw))

    def test_chunked_body_exceeds_max_decoded_size(self) -> None:
        raw = (
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
            b"5\r\nhello\r\n0\r\n\r\n"
        )
        with self.assertRaises(ProtocolError):
            read_response(TinyStream(raw), max_body_size=3)

    def test_chunked_missing_crlf_after_chunk_data(self) -> None:
        raw = (
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
            b"2\r\nabX\r\n0\r\n\r\n"
        )
        with self.assertRaises(ProtocolError):
            read_response(TinyStream(raw))

    def test_chunked_with_trailers(self) -> None:
        raw = (
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
            b"2\r\nok\r\n0\r\nX-Trail: yes\r\n\r\n"
        )
        parsed = read_response(TinyStream(raw, chunk_size=2))
        self.assertEqual(parsed.body, b"ok")
        self.assertEqual(parsed.trailers["X-Trail"], "yes")

    def test_trailer_malformed_line(self) -> None:
        reader = _BufferedReader(TinyStream(b"bad-trailer\r\n\r\n", chunk_size=64))
        with self.assertRaises(ProtocolError):
            _consume_trailers(reader)

    def test_trailer_empty_name(self) -> None:
        reader = _BufferedReader(TinyStream(b": value\r\n\r\n", chunk_size=64))
        with self.assertRaises(ProtocolError):
            _consume_trailers(reader)

    def test_trailer_count_limit(self) -> None:
        lines = b"".join(f"X-{i}: v\r\n".encode() for i in range(DEFAULT_MAX_TRAILER_LINES + 2))
        reader = _BufferedReader(TinyStream(lines + b"\r\n", chunk_size=64))
        with self.assertRaises(ProtocolError):
            _consume_trailers(reader, max_lines=2)

    def test_trailer_duplicate_joined(self) -> None:
        reader = _BufferedReader(TinyStream(b"X-T: a\r\nX-T: b\r\n\r\n", chunk_size=64))
        trailers = _consume_trailers(reader)
        self.assertEqual(trailers["X-T"], "a, b")

    def test_prefixed_stream_drains_prefix_first(self) -> None:
        inner = TinyStream(b"rest", chunk_size=64)
        stream = _PrefixedStream(b"pre", inner)
        self.assertEqual(stream.recv(10), b"pre")
        self.assertEqual(stream.recv(10), b"rest")

    def test_parse_response_bytes_empty_stream_returns_empty(self) -> None:
        parsed = parse_response_bytes(b"HTTP/1.1 204 No Content\r\n\r\n", recv_chunk_size=1)
        self.assertEqual(parsed.status_code, 204)
        self.assertEqual(parsed.body, b"")

    def test_204_bodyless_framing(self) -> None:
        parsed = parse_response_bytes(b"HTTP/1.1 204 No Content\r\nContent-Length: 5\r\n\r\njunk")
        self.assertEqual(parsed.framing, "bodyless")
        self.assertEqual(parsed.body, b"")

    def test_read_chunked_direct_helper(self) -> None:
        reader = _BufferedReader(
            TinyStream(b"3\r\nfoo\r\n0\r\n\r\n", chunk_size=64),
            initial=b"",
        )
        body, trailers = _read_chunked_body(
            reader, max_body_size=DEFAULT_MAX_BODY_SIZE, max_chunk_size=DEFAULT_MAX_CHUNK_SIZE
        )
        self.assertEqual(body, b"foo")
        self.assertEqual(len(trailers), 0)


if __name__ == "__main__":
    unittest.main()
