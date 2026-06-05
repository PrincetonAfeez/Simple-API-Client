"""Tests for the parser fixtures."""

from __future__ import annotations

import unittest
from pathlib import Path

from apiclient.exceptions import ProtocolError
from apiclient.http.parser import parse_response_bytes

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str) -> bytes:
    """Load a fixture and normalise the line endings to CRLF."""

    raw = (FIXTURES / name).read_bytes()
    return raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


class ParserFixtureTests(unittest.TestCase):
    def test_chunked_response_fixture(self) -> None:
        parsed = parse_response_bytes(_load("chunked_response.txt"))
        self.assertEqual(parsed.status_code, 200)
        self.assertEqual(parsed.framing, "chunked")
        self.assertEqual(parsed.body, b"hello world")

    def test_malformed_status_line_fixture(self) -> None:
        with self.assertRaises(ProtocolError):
            parse_response_bytes(_load("malformed_status_line.txt"))

    def test_duplicate_headers_fixture(self) -> None:
        parsed = parse_response_bytes(_load("duplicate_headers.txt"))
        self.assertEqual(parsed.headers["X-Demo"], "one, two")
        self.assertEqual(parsed.framing, "content-length")


if __name__ == "__main__":
    unittest.main()
