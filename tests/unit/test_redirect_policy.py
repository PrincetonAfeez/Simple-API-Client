"""Tests for the redirect policy."""

from __future__ import annotations

import unittest

from apiclient.http.redirects import RedirectPolicy
from apiclient.models import CaseInsensitiveHeaders, Request, Response


def _redirect_response(status: int, location: str) -> Response:
    return Response(
        status_code=status,
        reason="",
        headers=CaseInsensitiveHeaders({"Location": location}),
        body=b"",
        url="http://example.test/from",
    )


class RedirectPolicyTests(unittest.TestCase):
    def test_303_rewrites_post_to_get_and_strips_body(self) -> None:
        original = Request(
            "POST",
            "http://example.test/from",
            headers=CaseInsensitiveHeaders({"Content-Type": "application/json"}),
            body=b'{"x":1}',
        )
        response = _redirect_response(303, "/target")
        next_request, record = RedirectPolicy().next_request(original, response)
        self.assertEqual(next_request.method, "GET")
        self.assertEqual(next_request.body, b"")
        self.assertNotIn("Content-Type", next_request.headers)
        self.assertEqual(record.status_code, 303)
        self.assertEqual(record.location, "http://example.test/target")

    def test_307_preserves_method_and_body(self) -> None:
        original = Request(
            "POST",
            "http://example.test/from",
            headers=CaseInsensitiveHeaders({"Content-Type": "application/json"}),
            body=b'{"x":1}',
        )
        response = _redirect_response(307, "/target")
        next_request, _ = RedirectPolicy().next_request(original, response)
        self.assertEqual(next_request.method, "POST")
        self.assertEqual(next_request.body, b'{"x":1}')
        self.assertEqual(next_request.headers["Content-Type"], "application/json")

    def test_cross_host_strips_authorization(self) -> None:
        original = Request(
            "GET",
            "http://example.test/from",
            headers=CaseInsensitiveHeaders({"Authorization": "Bearer secret"}),
        )
        response = _redirect_response(302, "http://other.test/target")
        next_request, _ = RedirectPolicy().next_request(original, response)
        self.assertNotIn("Authorization", next_request.headers)

    def test_same_host_keeps_authorization(self) -> None:
        original = Request(
            "GET",
            "http://example.test/from",
            headers=CaseInsensitiveHeaders({"Authorization": "Bearer secret"}),
        )
        response = _redirect_response(302, "/target")
        next_request, _ = RedirectPolicy().next_request(original, response)
        self.assertEqual(next_request.headers["Authorization"], "Bearer secret")


if __name__ == "__main__":
    unittest.main()
