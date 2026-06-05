"""ApiClient and helper exhaustive tests."""

from __future__ import annotations

import unittest
from dataclasses import replace

from apiclient.auth import BearerTokenAuth
from apiclient.client import ApiClient, _normalize_headers, _redact_secrets_in_trace, response_summary
from apiclient.exceptions import HttpStatusError, RedirectError, RetryExhausted, TransportError
from apiclient.http.redirects import RedirectPolicy
from apiclient.models import CaseInsensitiveHeaders, RedirectRecord, Request, Response
from apiclient.resilience.retry import RetryPolicy
from apiclient.transport.base import Transport


class MockTransport(Transport):
    def __init__(self, outcomes: list[Response | BaseException]) -> None:
        self._outcomes = list(outcomes)
        self.calls = 0

    def send(self, request: Request, timeout) -> Response:  # noqa: ANN001
        self.calls += 1
        if not self._outcomes:
            raise TransportError("no more outcomes")
        item = self._outcomes.pop(0)
        if isinstance(item, BaseException):
            raise item
        return replace(item, request=request)

    def close(self) -> None:
        pass


def _response(status: int, *, url: str = "http://example.test/", headers: dict | None = None) -> Response:
    return Response(
        status,
        "OK" if status < 400 else "ERR",
        CaseInsensitiveHeaders(headers or {}),
        b"{}",
        url,
    )


class ClientExhaustiveTests(unittest.TestCase):
    def test_context_manager_closes_transport(self) -> None:
        transport = MockTransport([_response(200)])
        with ApiClient(transport=transport) as client:
            client.request("GET", "http://example.test/")
        self.assertEqual(transport.calls, 1)

    def test_fail_raises_http_status_error(self) -> None:
        client = ApiClient(transport=MockTransport([_response(500)]))
        with self.assertRaises(HttpStatusError):
            client.request("GET", "http://example.test/", fail=True)

    def test_trace_redacts_secrets_in_url(self) -> None:
        transport = MockTransport([_response(200)])
        client = ApiClient(transport=transport)
        client.request(
            "GET",
            "http://example.test/",
            auth=BearerTokenAuth("supersecret-token-value"),
            trace=True,
        )
        joined = "\n".join(client.last_trace)
        self.assertNotIn("supersecret-token-value", joined)
        self.assertIn("bearertokenauth", joined.lower())

    def test_redact_skips_empty_secret(self) -> None:
        trace = ["line with nothing"]
        _redact_secrets_in_trace(trace, [""])
        self.assertEqual(trace, ["line with nothing"])

    def test_normalize_headers_from_sequence(self) -> None:
        headers = _normalize_headers(["X-Test: value", "Y: z"])
        self.assertEqual(headers["X-Test"], "value")
        self.assertEqual(headers["Y"], "z")

    def test_normalize_headers_bad_format(self) -> None:
        with self.assertRaises(ValueError):
            _normalize_headers(["no-colon"])

    def test_normalize_headers_from_mapping(self) -> None:
        headers = _normalize_headers({"A": "1"})
        self.assertEqual(headers["a"], "1")

    def test_retry_exhausted_on_transport_errors(self) -> None:
        policy = RetryPolicy(retries=2, retry_statuses=frozenset())
        sleeps: list[float] = []
        client = ApiClient(
            transport=MockTransport([TransportError("down"), TransportError("down")]),
            retry_policy=policy,
            sleep_func=lambda s: sleeps.append(s),
        )
        with self.assertRaises(RetryExhausted):
            client.request("GET", "http://example.test/")
        self.assertEqual(len(sleeps), 2)

    def test_retry_exhausted_after_retryable_status(self) -> None:
        policy = RetryPolicy(retries=1, retry_statuses=frozenset({503}))
        client = ApiClient(
            transport=MockTransport([
                _response(503),
                _response(503),
            ]),
            retry_policy=policy,
            sleep_func=lambda _: None,
        )
        with self.assertRaises(RetryExhausted):
            client.request("GET", "http://example.test/")

    def test_no_retry_when_retries_zero_returns_503(self) -> None:
        policy = RetryPolicy(retries=0, retry_statuses=frozenset({503}))
        client = ApiClient(
            transport=MockTransport([_response(503)]),
            retry_policy=policy,
        )
        response = client.request("GET", "http://example.test/")
        self.assertEqual(response.status_code, 503)

    def test_redirect_too_many_hops(self) -> None:
        redirect = _response(
            302,
            headers={"Location": "http://other.test/next"},
        )
        client = ApiClient(
            transport=MockTransport([redirect, redirect, redirect]),
            redirect_policy=RedirectPolicy(max_hops=1),
        )
        with self.assertRaises(RedirectError):
            client.request("GET", "http://example.test/", follow_redirects=True)

    def test_redirect_missing_location_raises(self) -> None:
        policy = RedirectPolicy()
        request = Request("GET", "http://example.test/")
        response = _response(302, headers={})
        with self.assertRaises(RedirectError):
            policy.next_request(request, response)

    def test_response_summary_json_decode_fallback(self) -> None:
        response = Response(
            200,
            "OK",
            CaseInsensitiveHeaders({"Content-Type": "application/json"}),
            b"not-json",
            "http://x",
        )
        summary = response_summary(response)
        self.assertEqual(summary["body"], "not-json")

    def test_response_summary_binary_body(self) -> None:
        response = Response(
            200,
            "OK",
            CaseInsensitiveHeaders({"Content-Type": "application/octet-stream"}),
            b"\x00\x01",
            "http://x",
        )
        summary = response_summary(response)
        self.assertIn("binary bytes", str(summary["body"]))

    def test_response_summary_text_plain(self) -> None:
        response = Response(
            200,
            "OK",
            CaseInsensitiveHeaders({"Content-Type": "text/plain"}),
            b"hello",
            "http://x",
        )
        self.assertEqual(response_summary(response)["body"], "hello")

    def test_response_raise_for_status(self) -> None:
        response = _response(404)
        with self.assertRaises(HttpStatusError):
            response.raise_for_status()

    def test_send_rejects_non_http_url(self) -> None:
        client = ApiClient(transport=MockTransport([_response(200)]))
        with self.assertRaises(Exception):
            client.send(Request("GET", "ftp://example.test/"))


if __name__ == "__main__":
    unittest.main()
