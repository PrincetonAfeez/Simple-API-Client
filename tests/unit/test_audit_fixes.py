"""Tests for the third portfolio audit pass."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from apiclient.client import ApiClient
from apiclient.config import list_profiles, parse_status_csv
from apiclient.exceptions import InvalidUrlError
from apiclient.http.redirects import RedirectPolicy
from apiclient.models import CaseInsensitiveHeaders, Request, Response


class SendValidatesUrlTests(unittest.TestCase):
    def test_send_rejects_relative_url(self) -> None:
        client = ApiClient()
        request = Request("GET", "/relative-only")
        with self.assertRaises(InvalidUrlError):
            client.send(request)


class ConfigCsvStatusTests(unittest.TestCase):
    def test_parse_status_csv(self) -> None:
        self.assertEqual(parse_status_csv("429, 503, 504"), frozenset({429, 503, 504}))

    def test_list_profiles_always_includes_default(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.toml"
            path.write_text("[profiles.dev]\nbase_url = \"http://dev\"\n", encoding="utf-8")
            self.assertEqual(list_profiles(path=path), ["default", "dev"])


class RedirectAuthStripTests(unittest.TestCase):
    def test_cross_host_strips_authorization_by_default(self) -> None:
        original = Request(
            "GET",
            "http://a.test/",
            headers=CaseInsensitiveHeaders({"Authorization": "Bearer secret"}),
        )
        response = Response(
            302,
            "",
            CaseInsensitiveHeaders({"Location": "http://b.test/next"}),
            b"",
            original.url,
        )
        next_request, _ = RedirectPolicy().next_request(original, response)
        self.assertNotIn("Authorization", next_request.headers)

    def test_preserve_auth_keeps_authorization(self) -> None:
        policy = RedirectPolicy(preserve_auth_across_hosts=True)
        original = Request(
            "GET",
            "http://a.test/",
            headers=CaseInsensitiveHeaders({"Authorization": "Bearer secret"}),
        )
        response = Response(
            302,
            "",
            CaseInsensitiveHeaders({"Location": "http://b.test/next"}),
            b"",
            original.url,
        )
        next_request, _ = policy.next_request(original, response)
        self.assertEqual(next_request.headers["Authorization"], "Bearer secret")


if __name__ == "__main__":
    unittest.main()
