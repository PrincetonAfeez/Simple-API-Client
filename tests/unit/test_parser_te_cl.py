"""Parser behavior when Transfer-Encoding and Content-Length both appear."""

from __future__ import annotations

import unittest

from apiclient.http.parser import parse_response_bytes


class TransferEncodingContentLengthTests(unittest.TestCase):
    def test_chunked_wins_when_both_present(self) -> None:
        raw = (
            b"HTTP/1.1 200 OK\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"Content-Length: 999\r\n"
            b"\r\n"
            b"2\r\n"
            b"ok\r\n"
            b"0\r\n"
            b"\r\n"
        )
        parsed = parse_response_bytes(raw)
        self.assertEqual(parsed.framing, "chunked")
        self.assertEqual(parsed.body, b"ok")


if __name__ == "__main__":
    unittest.main()
