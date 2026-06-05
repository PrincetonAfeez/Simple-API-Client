"""Tests for CLI response formatting helpers."""

from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from apiclient.cli.output import build_curl, print_response, print_table_response
from apiclient.models import CaseInsensitiveHeaders, Request, Response


class CliOutputTests(unittest.TestCase):
    def _response(self, body: bytes, content_type: str = "application/json") -> Response:
        return Response(
            200,
            "OK",
            CaseInsensitiveHeaders({"Content-Type": content_type}),
            body,
            "http://example.test/",
        )

    def test_print_pretty_json(self) -> None:
        response = self._response(b'{"z":1,"a":2}')
        with patch("sys.stdout", new=io.StringIO()) as buf:
            print_response(response, "pretty")
        self.assertIn('"a": 2', buf.getvalue())

    def test_print_raw_bytes(self) -> None:
        response = self._response(b"raw-bytes\n")
        captured: list[bytes] = []

        class _Stdout:
            buffer = type("Buffer", (), {"write": staticmethod(lambda b: captured.append(b))})()

            def write(self, _text: str) -> None:
                return None

        with patch("sys.stdout", _Stdout()):
            print_response(response, "raw")
        self.assertEqual(captured, [b"raw-bytes\n"])

    def test_print_table_from_results_list(self) -> None:
        body = json.dumps({"results": [{"id": 1, "name": "ada"}]}).encode()
        response = self._response(body)
        with patch("sys.stdout", new=io.StringIO()) as buf:
            print_response(response, "table")
        output = buf.getvalue()
        self.assertIn("id", output)
        self.assertIn("name", output)
        self.assertIn("ada", output)

    def test_print_table_falls_back_for_non_tabular_json(self) -> None:
        response = self._response(b'{"message":"hello"}', content_type="application/json")
        with patch("sys.stdout", new=io.StringIO()) as buf:
            print_response(response, "table")
        self.assertIn("message", buf.getvalue())

    def test_print_pretty_non_json_uses_text(self) -> None:
        response = self._response(b"plain text", content_type="text/plain")
        with patch("sys.stdout", new=io.StringIO()) as buf:
            print_response(response, "pretty")
        self.assertEqual(buf.getvalue().strip(), "plain text")

    def test_print_raw_appends_newline_when_body_has_none(self) -> None:
        response = self._response(b"no-trailing-newline", content_type="text/plain")
        captured: list[bytes] = []
        newline_written = False

        class _Stdout:
            buffer = type("Buffer", (), {"write": staticmethod(lambda b: captured.append(b))})()

            def write(self, _text: str) -> None:
                nonlocal newline_written
                newline_written = True

        with patch("sys.stdout", _Stdout()):
            print_response(response, "raw")
        self.assertEqual(captured, [b"no-trailing-newline"])
        self.assertTrue(newline_written)

    def test_print_table_invalid_json_falls_back_to_status_line(self) -> None:
        response = self._response(b"not-json", content_type="application/json")
        with patch("sys.stdout", new=io.StringIO()) as buf:
            print_table_response(response)
        output = buf.getvalue()
        self.assertIn("status\t200", output)
        self.assertIn("body\t", output)

    def test_print_table_items_key(self) -> None:
        body = json.dumps({"items": [{"sku": "A1"}]}).encode()
        response = self._response(body)
        with patch("sys.stdout", new=io.StringIO()) as buf:
            print_response(response, "table")
        self.assertIn("sku", buf.getvalue())

    def test_print_pretty_invalid_json_falls_back_to_text(self) -> None:
        response = self._response(b"{not valid", content_type="application/json")
        with patch("sys.stdout", new=io.StringIO()) as buf:
            print_response(response, "pretty")
        self.assertIn("{not valid", buf.getvalue())

    def test_build_curl_includes_body_and_headers(self) -> None:
        request = Request(
            "POST",
            "http://example.test/echo",
            headers=CaseInsensitiveHeaders({"Content-Type": "application/json"}),
            body=b'{"x":1}',
        )
        curl = build_curl(request)
        self.assertIn("--data", curl)
        self.assertIn("POST", curl)

    def test_build_curl_redacts_bearer(self) -> None:
        request = Request(
            "GET",
            "http://example.test/?token=secret",
            headers=CaseInsensitiveHeaders(
                {"Authorization": "Bearer supersecret-token"}
            ),
        )
        curl = build_curl(request)
        self.assertIn("curl", curl)
        self.assertNotIn("supersecret-token", curl)


if __name__ == "__main__":
    unittest.main()
