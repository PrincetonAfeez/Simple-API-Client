"""Exhaustive model and header tests."""

from __future__ import annotations

import unittest

from apiclient.exceptions import HttpStatusError
from apiclient.models import CaseInsensitiveHeaders, Request, Response, TimingInfo


class ModelsExhaustiveTests(unittest.TestCase):
    def test_headers_case_change_removes_old_key(self) -> None:
        h = CaseInsensitiveHeaders()
        h["Content-Type"] = "a"
        h["content-type"] = "b"
        self.assertEqual(len(h), 1)
        self.assertEqual(h["Content-Type"], "b")

    def test_headers_pop_missing_returns_default(self) -> None:
        h = CaseInsensitiveHeaders({"A": "1"})
        self.assertIsNone(h.pop("missing"))
        self.assertEqual(h.pop("A"), "1")

    def test_headers_setdefault_existing(self) -> None:
        h = CaseInsensitiveHeaders({"A": "1"})
        self.assertEqual(h.setdefault("a", "2"), "1")

    def test_headers_update_with_kwargs(self) -> None:
        h = CaseInsensitiveHeaders()
        h.update({"A": "1"}, B="2")
        self.assertEqual(h["B"], "2")

    def test_headers_delitem(self) -> None:
        h = CaseInsensitiveHeaders({"A": "1"})
        del h["a"]
        self.assertNotIn("A", h)

    def test_headers_copy_is_independent(self) -> None:
        h = CaseInsensitiveHeaders({"A": "1"})
        c = h.copy()
        c["B"] = "2"
        self.assertNotIn("B", h)

    def test_headers_lower_items(self) -> None:
        items = dict(CaseInsensitiveHeaders({"X": "y"}).lower_items())
        self.assertEqual(items, {"x": "y"})

    def test_headers_eq_not_implemented_for_other_types(self) -> None:
        h = CaseInsensitiveHeaders()
        self.assertIs(h.__eq__("nope"), NotImplemented)

    def test_request_bytearray_body(self) -> None:
        req = Request("GET", "http://x", body=bytearray(b"ab"))
        self.assertEqual(req.body, b"ab")

    def test_request_invalid_body_type(self) -> None:
        with self.assertRaises(TypeError):
            Request("GET", "http://x", body=1)  # type: ignore[arg-type]

    def test_request_headers_coerced(self) -> None:
        req = Request("GET", "http://x", headers={"X": "1"})
        self.assertIsInstance(req.headers, CaseInsensitiveHeaders)

    def test_response_ok_property(self) -> None:
        self.assertTrue(Response(200, "OK", CaseInsensitiveHeaders(), b"", "http://x").ok)
        self.assertFalse(Response(404, "NF", CaseInsensitiveHeaders(), b"", "http://x").ok)
        self.assertTrue(Response(302, "Found", CaseInsensitiveHeaders(), b"", "http://x").ok)

    def test_response_text_unknown_charset_falls_back(self) -> None:
        response = Response(
            200,
            "OK",
            CaseInsensitiveHeaders({"Content-Type": "text/plain; charset=does-not-exist-xyz"}),
            b"\xff\xfe",
            "http://x",
        )
        self.assertIsInstance(response.text, str)

    def test_timing_info_as_dict(self) -> None:
        info = TimingInfo(dns=1.0, total=2.0)
        d = info.as_dict()
        self.assertEqual(d["dns"], 1.0)
        self.assertEqual(d["total"], 2.0)

    def test_response_history_default_empty(self) -> None:
        response = Response(200, "OK", CaseInsensitiveHeaders(), b"", "http://x")
        self.assertEqual(response.history, [])


if __name__ == "__main__":
    unittest.main()
