"""CLI main() integration tests against the WSGI demo server."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apiclient.cli.main import (
    _DeferredStderrHandler,
    _fail_on_error,
    _follow_redirects,
    _positive_float,
    _positive_int,
    build_parser,
    handle_configure,
    main,
    make_client,
    make_paginator,
)
from apiclient.config import ClientConfig
from apiclient.exceptions import ApiClientError, AuthError, ConfigError
from tests.helpers import wsgi_server


class _Ns:
    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


class CliCommandsTests(unittest.TestCase):
    def test_main_get_health(self) -> None:
        with wsgi_server() as base:
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                code = main(["get", f"{base}/health"])
            self.assertEqual(code, 0)
            self.assertIn("ok", buf.getvalue().lower())

    def test_main_post_echo_json(self) -> None:
        with wsgi_server() as base:
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                code = main([
                    "post",
                    f"{base}/echo",
                    "--json",
                    '{"name":"test"}',
                ])
            self.assertEqual(code, 0)
            self.assertIn("test", buf.getvalue())

    def test_main_trace_command(self) -> None:
        with wsgi_server() as base:
            stderr = io.StringIO()
            with patch("sys.stderr", stderr):
                code = main(["trace", "GET", f"{base}/health", "--transport", "raw"])
            self.assertEqual(code, 0)
            self.assertIn("DNS", stderr.getvalue())

    def test_main_request_with_fail(self) -> None:
        with wsgi_server() as base:
            code = main(["get", f"{base}/private", "--fail"])
            self.assertNotEqual(code, 0)

    def test_main_paginate_items_only(self) -> None:
        with wsgi_server() as base:
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                code = main([
                    "paginate",
                    f"{base}/items",
                    "--strategy",
                    "offset",
                    "--limit",
                    "2",
                    "--max-pages",
                    "2",
                    "--items-only",
                ])
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertIsInstance(payload, list)

    def test_main_paginate_with_page_metadata(self) -> None:
        with wsgi_server() as base:
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                code = main([
                    "paginate",
                    f"{base}/items",
                    "--strategy",
                    "page",
                    "--limit",
                    "2",
                    "--max-pages",
                    "1",
                ])
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertIn("page_count", payload)
            self.assertIn("pages", payload)

    def test_main_auth_test_success(self) -> None:
        with wsgi_server() as base:
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                code = main([
                    "auth",
                    "test",
                    f"{base}/private",
                    "--bearer-token",
                    "demo-token",
                ])
            self.assertEqual(code, 0)

    def test_main_auth_test_without_credentials(self) -> None:
        with wsgi_server() as base:
            code = main(["auth", "test", f"{base}/health"])
            self.assertEqual(code, AuthError.exit_code)

    def test_main_auth_wrong_subcommand(self) -> None:
        with wsgi_server() as base:
            with self.assertRaises(SystemExit) as ctx:
                main(["auth", "noop", f"{base}/health", "--bearer-token", "x"])
            self.assertEqual(ctx.exception.code, 2)

    def test_main_bench(self) -> None:
        with wsgi_server() as base:
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                code = main([
                    "bench",
                    f"{base}/health",
                    "--count",
                    "3",
                    "--concurrency",
                    "2",
                ])
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["total_requested"], 3)

    def test_main_bench_trace_with_concurrency_raises(self) -> None:
        with wsgi_server() as base:
            code = main([
                "bench",
                f"{base}/health",
                "--concurrency",
                "2",
                "--trace",
            ])
            self.assertEqual(code, ConfigError.exit_code)

    def test_main_configure_set_get_unset_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            os.environ["APICLIENT_CONFIG"] = str(path)
            try:
                buf = io.StringIO()
                with patch("sys.stdout", buf):
                    self.assertEqual(
                        main(["configure", "set", "dev.base_url", "http://localhost:8000"]),
                        0,
                    )
                self.assertIn("Wrote", buf.getvalue())

                buf = io.StringIO()
                with patch("sys.stdout", buf):
                    self.assertEqual(main(["configure", "get", "dev.base_url"]), 0)
                self.assertIn("localhost", buf.getvalue())

                self.assertEqual(main(["configure", "get", "dev.missing"]), 1)

                buf = io.StringIO()
                with patch("sys.stdout", buf):
                    main(["configure", "unset", "dev.base_url"])
                self.assertIn("Removed", buf.getvalue())

                buf = io.StringIO()
                with patch("sys.stdout", buf):
                    main(["configure", "list"])
                self.assertIn("default", buf.getvalue())
            finally:
                os.environ.pop("APICLIENT_CONFIG", None)

    def test_handle_configure_unknown_command(self) -> None:
        args = _Ns(configure_command="explode")
        with self.assertRaises(ConfigError):
            handle_configure(args)

    def test_main_invalid_json_body(self) -> None:
        with wsgi_server() as base:
            code = main(["post", f"{base}/echo", "--json", "{bad"])
            self.assertEqual(code, 2)

    def test_main_relative_url_without_base(self) -> None:
        code = main(["get", "/health"])
        self.assertNotEqual(code, 0)

    def test_main_no_command_prints_help(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args([])

    def test_make_client_unknown_transport(self) -> None:
        args = _Ns(
            transport="ftp",
            keep_alive=None,
            pool_size=None,
            pool_idle=None,
            retries=None,
            retry_non_idempotent=None,
            backoff_factor=None,
            retry_jitter=None,
            retry_max_backoff=None,
            retry_status=[],
            max_redirects=None,
            no_follow_redirects=False,
            preserve_auth_across_hosts=None,
            redirect_status=[],
            timeout=None,
            connect_timeout=None,
            read_timeout=None,
        )
        with self.assertRaises(ConfigError):
            make_client(args, ClientConfig())

    def test_make_client_keep_alive_requires_raw(self) -> None:
        args = _Ns(
            transport="urllib",
            keep_alive=True,
            pool_size=None,
            pool_idle=None,
            retries=None,
            retry_non_idempotent=None,
            backoff_factor=None,
            retry_jitter=None,
            retry_max_backoff=None,
            retry_status=[],
            max_redirects=None,
            no_follow_redirects=False,
            preserve_auth_across_hosts=None,
            redirect_status=[],
            timeout=None,
            connect_timeout=None,
            read_timeout=None,
        )
        with self.assertRaises(ConfigError):
            make_client(args, ClientConfig())

    def test_make_paginator_all_strategies(self) -> None:
        for strategy in ("offset", "page", "cursor", "link"):
            args = _Ns(strategy=strategy, limit=10, max_pages=2, items_key="items")
            paginator = make_paginator(args)
            self.assertIsNotNone(paginator)

    def test_follow_redirects_and_fail_helpers(self) -> None:
        config = ClientConfig(no_follow_redirects=True, fail=True)
        args = _Ns(no_follow_redirects=False, fail=False)
        self.assertFalse(_follow_redirects(args, config))
        self.assertTrue(_fail_on_error(_Ns(fail=True), ClientConfig()))

    def test_positive_int_and_float_validators(self) -> None:
        self.assertEqual(_positive_int("3"), 3)
        self.assertEqual(_positive_float("1.5"), 1.5)
        with self.assertRaises(Exception):
            _positive_int("0")
        with self.assertRaises(Exception):
            _positive_float("0")

    def test_deferred_stderr_handler_emit(self) -> None:
        handler = _DeferredStderrHandler()
        handler.setFormatter(handler.formatter or __import__("logging").Formatter("%(message)s"))
        record = __import__("logging").LogRecord(
            "apiclient", 20, "", 0, "hello", (), None
        )
        stderr = io.StringIO()
        with patch("sys.stderr", stderr):
            handler.emit(record)
        self.assertIn("hello", stderr.getvalue())

    def test_main_keyboard_interrupt(self) -> None:
        with patch("apiclient.cli.main.handle_request_command", side_effect=KeyboardInterrupt):
            with patch("apiclient.cli.main.load_config", return_value=ClientConfig()):
                code = main(["get", "http://example.test/"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
