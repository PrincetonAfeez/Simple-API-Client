"""Tests for the CLI helpers."""

from __future__ import annotations

import argparse
import unittest

from apiclient.auth import ApiKeyHeaderAuth, ApiKeyQueryAuth, BasicAuth, BearerTokenAuth
from apiclient.cli.main import (
    _build_redirect_policy,
    _build_retry_policy,
    make_auth,
    make_timeout,
    parse_assignment,
    parse_pairs,
    resolve_url,
)
from apiclient.config import ClientConfig
from apiclient.exceptions import InvalidUrlError


def _ns(**fields) -> argparse.Namespace:
    base = dict(
        bearer_token=None,
        basic=None,
        api_key_header=None,
        api_key_query=None,
        timeout=None,
        connect_timeout=None,
        read_timeout=None,
        retries=None,
        retry_non_idempotent=None,
        keep_alive=None,
        pool_size=None,
        pool_idle=None,
        backoff_factor=None,
        retry_jitter=None,
        retry_max_backoff=None,
        retry_status=[],
        max_redirects=None,
        no_follow_redirects=False,
        preserve_auth_across_hosts=None,
        redirect_status=[],
    )
    base.update(fields)
    return argparse.Namespace(**base)


class CliHelperTests(unittest.TestCase):
    def test_parse_pairs_preserves_repeats_and_order(self) -> None:
        pairs = parse_pairs(["tag=a", "tag=b", "name=ada"])
        self.assertEqual(pairs, [("tag", "a"), ("tag", "b"), ("name", "ada")])

    def test_parse_assignment_strips_key(self) -> None:
        self.assertEqual(parse_assignment(" name = value with spaces "), ("name", " value with spaces "))

    def test_parse_assignment_rejects_missing_equals(self) -> None:
        with self.assertRaises(ValueError):
            parse_assignment("no_equals_here")

    def test_make_timeout_prefers_explicit_total(self) -> None:
        timeout = make_timeout(_ns(timeout=7.5), ClientConfig())
        self.assertEqual(timeout.connect, 7.5)
        self.assertEqual(timeout.read, 7.5)
        self.assertEqual(timeout.total, 7.5)

    def test_make_timeout_falls_back_to_config_and_defaults(self) -> None:
        timeout = make_timeout(_ns(), ClientConfig(connect_timeout=2.0))
        self.assertEqual(timeout.connect, 2.0)
        self.assertEqual(timeout.read, 10.0)

    def test_make_auth_picks_strategies_in_priority_order(self) -> None:
        self.assertIsInstance(make_auth(_ns(bearer_token="t"), ClientConfig()), BearerTokenAuth)
        self.assertIsInstance(make_auth(_ns(basic="u:p"), ClientConfig()), BasicAuth)
        self.assertIsInstance(
            make_auth(_ns(api_key_header="X-API-Key=demo"), ClientConfig()),
            ApiKeyHeaderAuth,
        )
        self.assertIsInstance(
            make_auth(_ns(api_key_query="api_key=demo"), ClientConfig()),
            ApiKeyQueryAuth,
        )
        self.assertIsNone(make_auth(_ns(), ClientConfig()))

    def test_make_auth_rejects_basic_without_colon(self) -> None:
        with self.assertRaises(ValueError):
            make_auth(_ns(basic="no-colon"), ClientConfig())

    def test_resolve_url_joins_with_base_url(self) -> None:
        config = ClientConfig(base_url="http://server/")
        self.assertEqual(resolve_url("/items", config), "http://server/items")
        self.assertEqual(resolve_url("items/3", config), "http://server/items/3")
        self.assertEqual(
            resolve_url("http://explicit", config),
            "http://explicit",
        )

    def test_resolve_url_raises_without_base(self) -> None:
        with self.assertRaises(InvalidUrlError):
            resolve_url("/items", ClientConfig())

    def test_build_retry_policy_uses_explicit_overrides(self) -> None:
        ns = _ns(
            backoff_factor=2.5,
            retry_jitter=0.5,
            retry_max_backoff=99.0,
            retry_status=[500, 502],
        )
        policy = _build_retry_policy(
            ns, ClientConfig(), retries=3, retry_non_idempotent=False
        )
        self.assertEqual(policy.retries, 3)
        self.assertEqual(policy.backoff_factor, 2.5)
        self.assertEqual(policy.jitter, 0.5)
        self.assertEqual(policy.max_backoff, 99.0)
        self.assertEqual(policy.retry_statuses, {500, 502})

    def test_build_redirect_policy_honors_max_redirects(self) -> None:
        policy = _build_redirect_policy(_ns(max_redirects=2), ClientConfig())
        self.assertEqual(policy.max_hops, 2)
        default_policy = _build_redirect_policy(_ns(), ClientConfig())
        self.assertEqual(default_policy.max_hops, 5)

    def test_retry_non_idempotent_cli_overrides_profile(self) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--retry-non-idempotent",
            action=argparse.BooleanOptionalAction,
            default=None,
        )
        ns = parser.parse_args(["--no-retry-non-idempotent"])
        config = ClientConfig(retry_non_idempotent=True)
        effective = ns.retry_non_idempotent if ns.retry_non_idempotent is not None else config.retry_non_idempotent
        self.assertFalse(effective)


if __name__ == "__main__":
    unittest.main()
