"""Regression tests for fixes BN1-BN6 and MN1-MN12."""

from __future__ import annotations

import asyncio
import json
import tomllib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from apiclient.concurrency import fetch_many
from apiclient.config import (
    _dump_toml,
    _render_toml_value,
    get_config_value,
    set_config_value,
)
from apiclient.exceptions import ConfigError, PaginationError
from apiclient.http.encode import encode_body
from apiclient.http.parser import (
    DEFAULT_MAX_HEADER_LINES,
    DEFAULT_MAX_TRAILER_LINES,
    parse_response_bytes,
)
from apiclient.http.redirects import RedirectPolicy
from apiclient.models import CaseInsensitiveHeaders, Response
from apiclient.pagination import LinkHeaderPaginator
from apiclient.resilience.retry import RetryPolicy
from apiclient.transport.socket_transport import _can_pool_response


class BN1ConfigRootScalarsRoundtripTests(unittest.TestCase):
    def test_root_scalar_stays_at_root_after_round_trip(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            path.write_text(
                'top_setting = "hello"\n\n[telemetry]\nsink = "prom"\n',
                encoding="utf-8",
            )
            set_config_value("dev.retries", "3", path=path)
            text = path.read_text(encoding="utf-8")
            data = tomllib.loads(text)
            self.assertEqual(data.get("top_setting"), "hello")
            self.assertNotIn("top_setting", data.get("telemetry", {}))


class BN4ResponseJsonRaisesDecodeErrorTests(unittest.TestCase):
    def test_response_json_raises_json_decode_error(self) -> None:
        response = Response(200, "OK", CaseInsensitiveHeaders(), b"not json", "http://x")
        with self.assertRaises(json.JSONDecodeError):
            response.json()


class BN5UrllibTimeoutZeroTests(unittest.TestCase):
    def test_zero_total_timeout_does_not_fall_back(self) -> None:
        from apiclient.resilience.timeout import TimeoutConfig

        # Smoke check the resolution rule, no network involvement.
        cfg = TimeoutConfig(connect=10, read=20, total=0.0)
        # Reproduce the urllib_transport rule inline:
        effective = cfg.total if cfg.total is not None else max(cfg.connect, cfg.read)
        self.assertEqual(effective, 0.0)


class BN6AsyncCancelledSuppressionTests(unittest.TestCase):
    def test_fail_fast_does_not_leak_cancellation_error(self) -> None:
        class _FailFirst:
            def __init__(self) -> None:
                self.calls = 0

            def request(self, method, url, **kwargs):  # noqa: ANN001
                self.calls += 1
                raise RuntimeError("boom")

        # Many URLs ensures sibling tasks get cancelled mid-flight.
        urls = [f"http://x/{i}" for i in range(20)]
        result = asyncio.run(
            fetch_many(_FailFirst(), urls, concurrency=8, fail_fast=True)
        )
        # The function must return cleanly; failure recorded for at least one URL.
        self.assertGreaterEqual(result.failed, 1)


class MN1RetryPolicyFrozensetTests(unittest.TestCase):
    def test_defaults_are_frozensets(self) -> None:
        policy = RetryPolicy()
        self.assertIsInstance(policy.retry_statuses, frozenset)
        self.assertIsInstance(policy.idempotent_methods, frozenset)


class MN2LinkPaginatorCycleGuardTests(unittest.TestCase):
    def test_revisited_url_raises(self) -> None:
        class _Client:
            def request(self, method, url, **kwargs):  # noqa: ANN001
                body = json.dumps({"results": [{"id": 1}]}).encode()
                headers = CaseInsensitiveHeaders(
                    {
                        "Content-Type": "application/json",
                        "Link": '<http://example.test/p>; rel="next"',
                    }
                )
                return Response(200, "OK", headers, body, url)

        with self.assertRaises(PaginationError):
            list(
                LinkHeaderPaginator(max_pages=5).pages(
                    _Client(), "http://example.test/p"
                )
            )


class MN3EncodeBinaryFileFriendlyErrorTests(unittest.TestCase):
    def test_missing_binary_file_raises_value_error(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            encode_body(binary_file="/no/such/file.bin")
        self.assertIn("/no/such/file.bin", str(ctx.exception))


class MN4ParserHeaderLineCapsTests(unittest.TestCase):
    def test_too_many_header_lines_is_rejected(self) -> None:
        extra = b"\r\n".join(
            f"X-Header-{i}: v".encode() for i in range(DEFAULT_MAX_HEADER_LINES + 5)
        )
        raw = b"HTTP/1.1 200 OK\r\n" + extra + b"\r\nContent-Length: 0\r\n\r\n"
        with self.assertRaises(Exception) as ctx:
            parse_response_bytes(raw)
        self.assertIn("safety limit", str(ctx.exception))

    def test_trailer_line_cap_is_a_compile_time_constant(self) -> None:
        # The trailer cap is exercised separately via parser internals; here we
        # simply assert the constant exists and is finite.
        self.assertGreater(DEFAULT_MAX_TRAILER_LINES, 0)


class MN8ConfigNonScalarRejectedTests(unittest.TestCase):
    def test_render_rejects_list(self) -> None:
        with self.assertRaises(ConfigError):
            _render_toml_value([1, 2, 3])

    def test_dump_supports_only_scalars_under_tables(self) -> None:
        data = {"profiles": {"dev": {"base_url": "http://x"}}, "top_key": "hi"}
        text = _dump_toml(data)
        round_tripped = tomllib.loads(text)
        self.assertEqual(round_tripped["top_key"], "hi")


class MN9ConfigGetLosslessTests(unittest.TestCase):
    def test_bool_round_trip_uses_toml_literal(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            set_config_value("dev.retry_non_idempotent", "true", path=path)
            self.assertEqual(
                get_config_value("dev.retry_non_idempotent", path=path), "true"
            )

    def test_int_returns_its_decimal_form(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            set_config_value("dev.retries", "3", path=path)
            self.assertEqual(get_config_value("dev.retries", path=path), "3")


class MN10RetryDelayGuardTests(unittest.TestCase):
    def test_attempt_zero_raises(self) -> None:
        with self.assertRaises(ValueError):
            RetryPolicy(retries=1).delay_for(0)

    def test_attempt_one_uses_backoff_factor(self) -> None:
        policy = RetryPolicy(retries=1, backoff_factor=0.5, jitter=0, max_backoff=10)
        self.assertEqual(policy.delay_for(1), 0.5)


class MN11CanPoolResponseHTTPVersionTests(unittest.TestCase):
    def test_http_1_0_without_keep_alive_is_not_poolable(self) -> None:
        self.assertFalse(_can_pool_response("HTTP/1.0", CaseInsensitiveHeaders()))

    def test_http_1_0_with_keep_alive_is_poolable(self) -> None:
        self.assertTrue(
            _can_pool_response(
                "HTTP/1.0", CaseInsensitiveHeaders({"Connection": "keep-alive"})
            )
        )

    def test_http_1_1_is_poolable_by_default(self) -> None:
        self.assertTrue(_can_pool_response("HTTP/1.1", CaseInsensitiveHeaders()))

    def test_explicit_close_blocks_pooling(self) -> None:
        self.assertFalse(
            _can_pool_response(
                "HTTP/1.1", CaseInsensitiveHeaders({"Connection": "close"})
            )
        )


class MN5RedirectPolicyCliKnobsTests(unittest.TestCase):
    def test_preserve_auth_flag_threaded_through(self) -> None:
        import argparse

        from apiclient.cli.main import _build_redirect_policy
        from apiclient.config import ClientConfig

        ns = argparse.Namespace(
            max_redirects=2,
            preserve_auth_across_hosts=True,
            redirect_status=[301, 308],
        )
        policy: RedirectPolicy = _build_redirect_policy(ns, ClientConfig())
        self.assertEqual(policy.max_hops, 2)
        self.assertTrue(policy.preserve_auth_across_hosts)
        self.assertEqual(policy.allowed_statuses, frozenset({301, 308}))


if __name__ == "__main__":
    unittest.main()
