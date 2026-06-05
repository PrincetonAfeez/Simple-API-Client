"""Tests for portfolio evaluation fixes."""

from __future__ import annotations

import asyncio
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from apiclient.auth import ApiKeyHeaderAuth, ApiKeyQueryAuth
from apiclient.concurrency import fetch_many
from apiclient.config import load_config, set_config_value
from apiclient.exceptions import ConfigError, InvalidUrlError
from apiclient.http.parser import parse_response_bytes
from apiclient.http.redirects import RedirectPolicy
from apiclient.models import CaseInsensitiveHeaders, Request, Response
from apiclient.observability.redaction import redact_url, sensitive_query_param_names
from apiclient.resilience.timeout import TimeoutConfig
from apiclient.transport.urllib_transport import UrllibTransport


class UnknownProfileTests(unittest.TestCase):
    def test_explicit_default_profile_without_section_is_allowed(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            path.write_text("[profiles.dev]\nbase_url = \"http://dev\"\n", encoding="utf-8")
            config = load_config("default", path=path)
            self.assertIsNone(config.base_url)

    def test_missing_profile_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            path.write_text("[profiles.default]\nbase_url = \"http://x\"\n", encoding="utf-8")
            with self.assertRaises(ConfigError) as ctx:
                load_config("ghost", path=path)
            self.assertIn("ghost", str(ctx.exception))


class SetConfigValidationTests(unittest.TestCase):
    def test_unknown_setting_rejected_at_set_time(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            with self.assertRaises(ConfigError) as ctx:
                set_config_value("dev.typo_field", "x", path=path)
            self.assertIn("typo_field", str(ctx.exception))


class RedirectQueryStripTests(unittest.TestCase):
    def test_cross_host_strips_api_key_query(self) -> None:
        auth = ApiKeyQueryAuth("api_key", "secret-key")
        original = Request("GET", "http://example.test/from")
        original = auth.apply(original)
        response = Response(
            302,
            "",
            CaseInsensitiveHeaders({"Location": "http://other.test/target"}),
            b"",
            original.url,
        )
        next_request, _ = RedirectPolicy().next_request(original, response, auth=auth)
        self.assertNotIn("api_key=", next_request.url)
        self.assertEqual(next_request.url, "http://other.test/target")

    def test_custom_header_stripped_on_cross_host(self) -> None:
        auth = ApiKeyHeaderAuth("X-My-Key", "sekrit")
        original = auth.apply(Request("GET", "http://example.test/from"))
        response = Response(
            302,
            "",
            CaseInsensitiveHeaders({"Location": "http://other.test/t"}),
            b"",
            original.url,
        )
        next_request, _ = RedirectPolicy().next_request(original, response, auth=auth)
        self.assertNotIn("X-My-Key", next_request.headers)


class UrllibUserinfoTests(unittest.TestCase):
    def test_userinfo_in_url_raises(self) -> None:
        transport = UrllibTransport()
        request = Request("GET", "http://user:pass@127.0.0.1:9/")
        with self.assertRaises(InvalidUrlError):
            transport.send(request, TimeoutConfig(connect=0.1, read=0.1, total=0.2))


class FetchManyByUrlTests(unittest.TestCase):
    def test_results_by_url_aligns_with_input(self) -> None:
        class _Client:
            def request(self, method, url, **kwargs):  # noqa: ANN001
                if url.endswith("/bad"):
                    raise RuntimeError("nope")
                return Response(200, "OK", CaseInsensitiveHeaders(), b"", url)

        urls = ["http://x/ok", "http://x/bad", "http://x/ok2"]
        result = asyncio.run(fetch_many(_Client(), urls, concurrency=2))
        self.assertEqual(len(result.results_by_url), 3)
        self.assertIsNotNone(result.results_by_url[0])
        self.assertIsNone(result.results_by_url[1])
        self.assertIsNotNone(result.results_by_url[2])
        self.assertIn("bad", result.errors_by_url[1] or "")


class FetchManyOrderingTests(unittest.TestCase):
    def test_responses_follow_input_url_order(self) -> None:
        seen: list[str] = []

        class _Client:
            def request(self, method, url, **kwargs):  # noqa: ANN001
                seen.append(url)
                return Response(200, "OK", CaseInsensitiveHeaders(), b"", url)

        urls = [f"http://x/{i}" for i in (3, 1, 2)]
        result = asyncio.run(
            fetch_many(_Client(), urls, concurrency=3)
        )
        self.assertEqual([r.url for r in result.responses], urls)


class Parser101Tests(unittest.TestCase):
    def test_101_is_skipped_like_other_1xx(self) -> None:
        raw = (
            b"HTTP/1.1 101 Switching Protocols\r\n\r\n"
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"
        )
        parsed = parse_response_bytes(raw)
        self.assertEqual(parsed.status_code, 200)
        self.assertEqual(parsed.body, b"ok")


class RedactParamsEnvTests(unittest.TestCase):
    def test_extra_sensitive_query_names_from_env(self) -> None:
        sensitive_query_param_names.cache_clear()
        os.environ["APICLIENT_REDACT_PARAMS"] = "session_id,MyToken"
        try:
            names = sensitive_query_param_names()
            self.assertIn("session_id", names)
            self.assertIn("mytoken", names)
            redacted = redact_url("http://x/?session_id=abc&page=1")
            self.assertIn("session_id=", redacted)
            self.assertNotIn("abc", redacted)
            self.assertIn("page=1", redacted)
        finally:
            del os.environ["APICLIENT_REDACT_PARAMS"]
            sensitive_query_param_names.cache_clear()


if __name__ == "__main__":
    unittest.main()
