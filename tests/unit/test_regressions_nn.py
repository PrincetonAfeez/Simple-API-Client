"""Regression tests for NN1-NN5."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from apiclient.config import load_config
from apiclient.exceptions import ConfigError
from apiclient.models import CaseInsensitiveHeaders, Request, Response
from apiclient.resilience.retry import retry_after_seconds
from apiclient.transport.pool import _looks_alive


class NN1PoolSocketLeakTests(unittest.TestCase):
    def test_looks_alive_returns_false_when_setblocking_fails(self) -> None:
        class _Sock:
            def setblocking(self, _flag):
                raise OSError("fd broken")

            def recv(self, *_args, **_kwargs):
                return b""

        # Must not raise; must return False so the caller can _safe_close().
        self.assertFalse(_looks_alive(_Sock()))


class NN2RequestBodyTypeTests(unittest.TestCase):
    def test_list_body_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            Request("POST", "http://x", body=[1, 2, 3])

    def test_dict_body_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            Request("POST", "http://x", body={"k": "v"})

    def test_bytearray_body_is_normalised(self) -> None:
        request = Request("POST", "http://x", body=bytearray(b"abc"))
        self.assertEqual(request.body, b"abc")
        self.assertIsInstance(request.body, bytes)

    def test_bytes_str_none_still_supported(self) -> None:
        self.assertEqual(Request("GET", "http://x", body=b"x").body, b"x")
        self.assertEqual(Request("GET", "http://x", body="x").body, b"x")
        self.assertEqual(Request("GET", "http://x", body=None).body, b"")


class NN3MaxPagesDefaultTests(unittest.TestCase):
    def test_cli_default_matches_paginator_default(self) -> None:
        from apiclient.cli.main import build_parser
        from apiclient.pagination import OffsetPaginator

        parser = build_parser()
        args = parser.parse_args(["paginate", "http://x"])
        self.assertEqual(args.max_pages, 10)
        self.assertEqual(args.max_pages, OffsetPaginator.__dataclass_fields__["max_pages"].default)


class NN4UnknownConfigKeyTests(unittest.TestCase):
    def test_unknown_profile_key_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            path.write_text(
                '[profiles.dev]\nbase_url = "http://x"\ntypo_field = "oops"\n',
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError) as ctx:
                load_config("dev", path=path)
            self.assertIn("typo_field", str(ctx.exception))

    def test_default_profile_unknown_key_also_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            path.write_text(
                '[profiles.default]\nweird = "x"\n',
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError):
                load_config(None, path=path)


class NN5RetryAfterFloatTests(unittest.TestCase):
    def _resp(self, header_value: str) -> Response:
        return Response(
            429,
            "",
            CaseInsensitiveHeaders({"Retry-After": header_value}),
            b"",
            "http://x",
        )

    def test_decimal_seconds_accepted(self) -> None:
        self.assertEqual(retry_after_seconds(self._resp("1.5")), 1.5)

    def test_integer_seconds_still_work(self) -> None:
        self.assertEqual(retry_after_seconds(self._resp("5")), 5.0)

    def test_negative_seconds_clamped_to_zero(self) -> None:
        self.assertEqual(retry_after_seconds(self._resp("-2")), 0.0)

    def test_garbage_value_returns_none(self) -> None:
        self.assertIsNone(retry_after_seconds(self._resp("not-a-time")))


if __name__ == "__main__":
    unittest.main()
