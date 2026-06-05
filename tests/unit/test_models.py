"""Tests for the models."""

from __future__ import annotations

import unittest

from apiclient.models import CaseInsensitiveHeaders, Request, Response


class CaseInsensitiveHeadersTests(unittest.TestCase):
    def test_eq_normalises_keys(self) -> None:
        a = CaseInsensitiveHeaders({"Content-Type": "application/json"})
        b = CaseInsensitiveHeaders({"content-type": "application/json"})
        self.assertEqual(a, b)
        self.assertEqual(a, {"CONTENT-TYPE": "application/json"})

    def test_eq_different_values_is_not_equal(self) -> None:
        self.assertNotEqual(
            CaseInsensitiveHeaders({"Content-Type": "application/json"}),
            CaseInsensitiveHeaders({"Content-Type": "text/plain"}),
        )


class RequestTests(unittest.TestCase):
    def test_string_body_is_encoded(self) -> None:
        request = Request("POST", "http://x", body="hello")
        self.assertEqual(request.body, b"hello")

    def test_none_body_becomes_empty(self) -> None:
        request = Request("POST", "http://x", body=None)
        self.assertEqual(request.body, b"")


class ResponseTests(unittest.TestCase):
    def test_json_propagates_decode_error(self) -> None:
        response = Response(
            200, "OK", CaseInsensitiveHeaders(), b"not json", "http://x",
        )
        with self.assertRaises(ValueError):
            response.json()


if __name__ == "__main__":
    unittest.main()
