"""argparse-powered command-line interface."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from urllib.parse import urljoin

from apiclient.auth import ApiKeyHeaderAuth, ApiKeyQueryAuth, BasicAuth, BearerTokenAuth
from apiclient.cli.output import build_curl, print_response
from apiclient.client import ApiClient
from apiclient.concurrency import fetch_many
from apiclient.config import (
    ClientConfig,
    get_config_value,
    list_profiles,
    load_config,
    parse_status_csv,
    set_config_value,
    unset_config_value,
)
from apiclient.exceptions import ApiClientError, AuthError, ConfigError, InvalidUrlError
from apiclient.http.redirects import RedirectPolicy
from apiclient.http.url import require_http_url
from apiclient.pagination import (
    CursorPaginator,
    LinkHeaderPaginator,
    OffsetPaginator,
    PageNumberPaginator,
    iter_items,
)
from apiclient.resilience.retry import RetryPolicy
from apiclient.resilience.timeout import TimeoutConfig
from apiclient.transport import ConnectionPool, RawSocketTransport, UrllibTransport


class _DeferredStderrHandler(logging.Handler):
    """Logging handler that resolves ``sys.stderr`` at emit time.

    A standard :class:`logging.StreamHandler` captures the stream object at
    construction time, which means it bypasses ``unittest.mock.patch("sys.stderr",
    ...)`` fixtures and writes to the original FD. Looking up ``sys.stderr``
    inside :meth:`emit` keeps the handler test-friendly.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            sys.stderr.write(self.format(record) + "\n")
            sys.stderr.flush()
        except Exception:  # pragma: no cover - never raised in practice
            self.handleError(record)


logger = logging.getLogger("apiclient")
if not any(isinstance(h, _DeferredStderrHandler) for h in logger.handlers):
    _handler = _DeferredStderrHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.propagate = False
    logger.setLevel(logging.WARNING)


def _package_version() -> str:
    try:
        return _pkg_version("simple-api-client")
    except PackageNotFoundError:  # not installed as a wheel
        return "0.1.0+source"


def _cli_override(cli_value, config_value):  # noqa: ANN001
    """Use the CLI value when the user passed a flag; otherwise fall back to config."""

    return config_value if cli_value is None else cli_value


def _follow_redirects(args: argparse.Namespace, config: ClientConfig) -> bool:
    if args.no_follow_redirects:
        return False
    if config.no_follow_redirects:
        return False
    return True


def _fail_on_error(args: argparse.Namespace, config: ClientConfig) -> bool:
    return bool(args.fail or config.fail)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    diagnostics_on = (
        getattr(args, "trace", False)
        or getattr(args, "verbose", False)
        or getattr(args, "curl", False)
        or args.command == "trace"
    )
    logger.setLevel(logging.INFO if diagnostics_on else logging.WARNING)
    try:
        if args.command == "configure":
            return handle_configure(args)

        config = load_config(getattr(args, "profile", None))
        if args.command in {"get", "post", "request", "trace"}:
            return handle_request_command(args, config)
        if args.command == "paginate":
            return handle_paginate(args, config)
        if args.command == "auth":
            return handle_auth(args, config)
        if args.command == "bench":
            return handle_bench(args, config)
        parser.print_help()
        return 2
    except ApiClientError as exc:
        logger.error("apiclient: %s", exc)
        return exc.exit_code
    except (ValueError, json.JSONDecodeError) as exc:
        logger.error("apiclient: %s", exc)
        return 2
    except KeyboardInterrupt:
        logger.error("apiclient: interrupted")
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apiclient", description="Educational HTTP API client")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_package_version()}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--profile")
    common.add_argument("--transport", choices=["raw", "urllib"])
    common.add_argument("--output", choices=["pretty", "raw", "table"])
    common.add_argument("--timeout", type=float)
    common.add_argument("--connect-timeout", type=float)
    common.add_argument("--read-timeout", type=float)
    common.add_argument("--retries", type=int)
    common.add_argument(
        "--retry-non-idempotent",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Retry non-idempotent methods (default: profile/config, else off)",
    )
    common.add_argument("--backoff-factor", type=float)
    common.add_argument("--retry-jitter", type=float)
    common.add_argument("--retry-max-backoff", type=float)
    common.add_argument(
        "--retry-status",
        action="append",
        default=[],
        type=int,
        help="HTTP status code to retry; repeatable",
    )
    common.add_argument("--max-redirects", type=int)
    common.add_argument(
        "--no-follow-redirects",
        action="store_true",
        help="Surface redirect responses instead of following them",
    )
    common.add_argument(
        "--preserve-auth-across-hosts",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Forward credentials on cross-host redirects (unsafe; default off)",
    )
    common.add_argument(
        "--redirect-status",
        action="append",
        default=[],
        type=int,
        help="HTTP status code to treat as a redirect; repeatable",
    )
    common.add_argument(
        "--keep-alive",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable a connection pool on the raw transport (HTTP/1.1 keep-alive).",
    )
    common.add_argument(
        "--pool-size",
        type=_positive_int,
        default=None,
        help="Max sockets per host in the pool (must be >= 1; default from profile or 4).",
    )
    common.add_argument(
        "--pool-idle",
        type=_positive_float,
        default=None,
        help="Idle socket lifetime in seconds (must be > 0; default from profile or 30).",
    )
    common.add_argument("--fail", action="store_true")
    common.add_argument("--trace", action="store_true")
    common.add_argument("--verbose", action="store_true")
    common.add_argument("--curl", action="store_true")
    common.add_argument("-H", "--header", action="append", default=[])
    common.add_argument("--param", action="append", default=[])
    common.add_argument("--bearer-token")
    common.add_argument("--basic", help="username:password")
    common.add_argument("--api-key-header", help="Header-Name=value")
    common.add_argument("--api-key-query", help="param=value")

    body = argparse.ArgumentParser(add_help=False)
    body.add_argument("--json", dest="json_body")
    body.add_argument("--form", action="append", default=[], help="name=value")
    body.add_argument("--data")
    body.add_argument("--data-binary")

    get = sub.add_parser("get", parents=[common])
    get.add_argument("url")

    post = sub.add_parser("post", parents=[common, body])
    post.add_argument("url")

    request = sub.add_parser("request", parents=[common, body])
    request.add_argument("method")
    request.add_argument("url")

    trace = sub.add_parser("trace", parents=[common, body])
    trace.add_argument("method")
    trace.add_argument("url")

    paginate = sub.add_parser("paginate", parents=[common])
    paginate.add_argument("url")
    paginate.add_argument("--strategy", choices=["offset", "page", "cursor", "link"], default="offset")
    paginate.add_argument("--limit", type=int, default=25)
    paginate.add_argument("--max-pages", type=int, default=10)
    paginate.add_argument("--items-key", default="results")
    paginate.add_argument("--items-only", action="store_true")

    auth = sub.add_parser("auth")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)
    auth_test = auth_sub.add_parser("test", parents=[common])
    auth_test.add_argument("url")

    configure = sub.add_parser("configure")
    configure_sub = configure.add_subparsers(dest="configure_command", required=True)
    configure_set = configure_sub.add_parser("set")
    configure_set.add_argument("key")
    configure_set.add_argument("value")
    configure_get = configure_sub.add_parser("get")
    configure_get.add_argument("key")
    configure_sub.add_parser("list")
    configure_unset = configure_sub.add_parser("unset")
    configure_unset.add_argument("key")

    bench = sub.add_parser("bench", parents=[common])
    bench.add_argument("url")
    bench.add_argument("--method", default="GET")
    bench.add_argument("--count", type=_positive_int, default=10)
    bench.add_argument("--concurrency", type=_positive_int, default=5)
    bench.add_argument("--fail-fast", action="store_true")

    return parser


def handle_request_command(args: argparse.Namespace, config: ClientConfig) -> int:
    method = _method_for(args)
    trace_enabled = args.trace or args.verbose or args.command == "trace"

    with make_client(args, config) as client:
        response = client.request(
            method,
            resolve_url(args.url, config),
            headers=args.header,
            params=parse_pairs(args.param),
            json=parse_json_body(getattr(args, "json_body", None)),
            form=parse_pairs(getattr(args, "form", [])) if getattr(args, "form", []) else None,
            data=getattr(args, "data", None),
            binary_file=getattr(args, "data_binary", None),
            auth=make_auth(args, config),
            timeout=make_timeout(args, config),
            follow_redirects=_follow_redirects(args, config),
            fail=_fail_on_error(args, config),
            trace=trace_enabled,
        )
        emit_diagnostics(args, client, trace_enabled)
        print_response(response, args.output or config.output)
    return 0


def handle_paginate(args: argparse.Namespace, config: ClientConfig) -> int:
    trace_enabled = args.trace or args.verbose
    with make_client(args, config) as client:
        paginator = make_paginator(args)
        pages = paginator.pages(
            client,
            resolve_url(args.url, config),
            headers=args.header,
            params=parse_pairs(args.param),
            auth=make_auth(args, config),
            timeout=make_timeout(args, config),
            follow_redirects=_follow_redirects(args, config),
            fail=_fail_on_error(args, config),
            trace=trace_enabled,
        )
        if args.items_only:
            payload = list(iter_items(pages))
        else:
            page_list = list(pages)
            payload = {
                "page_count": len(page_list),
                "items": [item for page in page_list for item in page.items],
                "pages": [
                    {
                        "number": page.number,
                        "status_code": page.response.status_code,
                        "url": page.response.url,
                        "item_count": len(page.items),
                    }
                    for page in page_list
                ],
            }
        print(json.dumps(payload, indent=2, sort_keys=True))
        if trace_enabled:
            for event in client.last_trace:
                logger.info(event)
    return 0


def handle_auth(args: argparse.Namespace, config: ClientConfig) -> int:
    if args.auth_command != "test":
        return 2
    auth = make_auth(args, config)
    if auth is None:
        raise AuthError(
            "auth test requires an authentication flag "
            "(--bearer-token / --basic / --api-key-header / --api-key-query) "
            "or a profile that provides one; an unauthenticated request would "
            "not test authentication."
        )
    trace_enabled = args.trace or args.verbose
    with make_client(args, config) as client:
        response = client.request(
            "GET",
            resolve_url(args.url, config),
            headers=args.header,
            params=parse_pairs(args.param),
            auth=auth,
            timeout=make_timeout(args, config),
            follow_redirects=_follow_redirects(args, config),
            trace=trace_enabled,
        )
        emit_diagnostics(args, client, trace_enabled)
        print_response(response, args.output or config.output)
        if response.status_code in {401, 403}:
            raise AuthError(f"authentication failed with HTTP {response.status_code}")
    return 0


def handle_bench(args: argparse.Namespace, config: ClientConfig) -> int:
    if args.concurrency > 1 and (args.trace or args.verbose):
        raise ConfigError(
            "bench does not support --trace/--verbose with --concurrency > 1; "
            "last_trace would reflect arbitrary concurrent requests"
        )
    base = resolve_url(args.url, config)
    urls = [base.format(id=i) if "{id}" in base else base for i in range(1, args.count + 1)]
    with make_client(args, config) as client:
        result = asyncio.run(
            fetch_many(
                client,
                urls,
                method=args.method.upper(),
                concurrency=args.concurrency,
                fail_fast=args.fail_fast,
                headers=args.header,
                params=parse_pairs(args.param),
                auth=make_auth(args, config),
                timeout=make_timeout(args, config),
                follow_redirects=_follow_redirects(args, config),
                fail=_fail_on_error(args, config),
                trace=args.trace or args.verbose,
            )
        )
    results_by_url = []
    for url, response, error in zip(
        urls, result.results_by_url, result.errors_by_url, strict=True
    ):
        if response is not None:
            results_by_url.append(
                {
                    "url": url,
                    "status_code": response.status_code,
                    "ok": response.ok,
                    "elapsed": response.elapsed,
                }
            )
        else:
            results_by_url.append({"url": url, "error": error or "request failed"})
    print(
        json.dumps(
            {
                "total_requested": result.total,
                "succeeded": result.succeeded,
                "failed": result.failed,
                "total_elapsed": result.total_elapsed,
                "average_latency": result.average_latency,
                "results": results_by_url,
                "errors": result.errors,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.failed == 0 else 1


def handle_configure(args: argparse.Namespace) -> int:
    command = args.configure_command
    if command == "set":
        path = set_config_value(args.key, args.value)
        print(f"Wrote {args.key} to {path}")
        return 0
    if command == "get":
        value = get_config_value(args.key)
        if value is None:
            print("", end="")
            return 1
        print(value)
        return 0
    if command == "unset":
        path = unset_config_value(args.key)
        print(f"Removed {args.key} from {path}")
        return 0
    if command == "list":
        for name in list_profiles():
            print(name)
        return 0
    raise ConfigError(f"Unknown configure command: {command!r}")


_SUPPORTED_TRANSPORTS = {"raw", "urllib"}


def make_client(args: argparse.Namespace, config: ClientConfig) -> ApiClient:
    transport_name = args.transport or config.transport
    if transport_name not in _SUPPORTED_TRANSPORTS:
        raise ConfigError(
            f"Unknown transport {transport_name!r}; expected one of "
            f"{sorted(_SUPPORTED_TRANSPORTS)}"
        )
    keep_alive = _cli_override(args.keep_alive, config.keep_alive)
    pool = None
    if keep_alive:
        if transport_name != "raw":
            raise ConfigError(
                "--keep-alive currently only applies to the raw transport "
                "(the urllib transport manages its own connection lifecycle)."
            )
        pool_size = args.pool_size if args.pool_size is not None else config.pool_size
        pool_idle = args.pool_idle if args.pool_idle is not None else config.pool_idle
        pool = ConnectionPool(max_per_host=pool_size, max_idle_seconds=pool_idle)
    transport = (
        RawSocketTransport(pool=pool) if transport_name == "raw" else UrllibTransport()
    )
    retries = args.retries if args.retries is not None else int(config.retries)
    retry_non_idempotent = _cli_override(
        args.retry_non_idempotent, config.retry_non_idempotent
    )
    retry_policy = _build_retry_policy(args, config, retries, retry_non_idempotent)
    redirect_policy = _build_redirect_policy(args, config)
    return ApiClient(
        transport=transport,
        retry_policy=retry_policy,
        redirect_policy=redirect_policy,
        timeout=make_timeout(args, config),
    )


def _positive_int(value: str) -> int:
    """argparse type that rejects non-positive integers."""

    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError(f"value must be >= 1, got {parsed}")
    return parsed


def _positive_float(value: str) -> float:
    """argparse type that rejects non-positive floats."""

    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f"value must be > 0, got {parsed}")
    return parsed


def _build_retry_policy(
    args: argparse.Namespace,
    config: ClientConfig,
    retries: int,
    retry_non_idempotent: bool,
) -> RetryPolicy:
    fields: dict[str, object] = {
        "retries": retries,
        "retry_non_idempotent": retry_non_idempotent,
    }
    backoff = _cli_override(args.backoff_factor, config.backoff_factor)
    if backoff is not None:
        fields["backoff_factor"] = backoff
    jitter = _cli_override(args.retry_jitter, config.retry_jitter)
    if jitter is not None:
        fields["jitter"] = jitter
    max_backoff = _cli_override(args.retry_max_backoff, config.retry_max_backoff)
    if max_backoff is not None:
        fields["max_backoff"] = max_backoff
    if args.retry_status:
        fields["retry_statuses"] = frozenset(args.retry_status)
    else:
        from_config = parse_status_csv(config.retry_statuses)
        if from_config is not None:
            fields["retry_statuses"] = from_config
    return RetryPolicy(**fields)  # type: ignore[arg-type]


def _build_redirect_policy(args: argparse.Namespace, config: ClientConfig) -> RedirectPolicy:
    fields: dict[str, object] = {}
    max_redirects = _cli_override(args.max_redirects, config.max_redirects)
    if max_redirects is not None:
        fields["max_hops"] = max_redirects
    preserve_auth = _cli_override(
        args.preserve_auth_across_hosts, config.preserve_auth_across_hosts
    )
    if preserve_auth:
        fields["preserve_auth_across_hosts"] = True
    if args.redirect_status:
        fields["allowed_statuses"] = frozenset(args.redirect_status)
    else:
        from_config = parse_status_csv(config.redirect_statuses)
        if from_config is not None:
            fields["allowed_statuses"] = from_config
    return RedirectPolicy(**fields)  # type: ignore[arg-type]


def make_timeout(args: argparse.Namespace, config: ClientConfig) -> TimeoutConfig:
    total = args.timeout if args.timeout is not None else config.timeout
    if total is not None and args.connect_timeout is None and args.read_timeout is None:
        return TimeoutConfig.from_single_value(float(total))
    connect = args.connect_timeout if args.connect_timeout is not None else config.connect_timeout
    read = args.read_timeout if args.read_timeout is not None else config.read_timeout
    return TimeoutConfig(
        connect=float(connect if connect is not None else 5.0),
        read=float(read if read is not None else 10.0),
        total=float(total) if total is not None else None,
    )


def make_auth(args: argparse.Namespace, config: ClientConfig):
    bearer = args.bearer_token or config.bearer_token
    if bearer:
        return BearerTokenAuth(bearer)
    basic = args.basic
    if basic:
        if ":" not in basic:
            raise ValueError("--basic must look like username:password")
        username, password = basic.split(":", 1)
        return BasicAuth(username, password)
    api_key_header = args.api_key_header or config.api_key_header
    if api_key_header:
        name, value = parse_assignment(api_key_header)
        return ApiKeyHeaderAuth(name, value)
    api_key_query = args.api_key_query or config.api_key_query
    if api_key_query:
        name, value = parse_assignment(api_key_query)
        return ApiKeyQueryAuth(name, value)
    return None


def make_paginator(args: argparse.Namespace):
    if args.strategy == "offset":
        return OffsetPaginator(limit=args.limit, max_pages=args.max_pages, items_key=args.items_key)
    if args.strategy == "page":
        return PageNumberPaginator(per_page=args.limit, max_pages=args.max_pages, items_key=args.items_key)
    if args.strategy == "cursor":
        return CursorPaginator(limit=args.limit, max_pages=args.max_pages, items_key=args.items_key)
    return LinkHeaderPaginator(max_pages=args.max_pages, items_key=args.items_key)


def emit_diagnostics(args: argparse.Namespace, client: ApiClient, trace_enabled: bool) -> None:
    if args.curl and client.last_request is not None:
        logger.info(build_curl(client.last_request))
    if trace_enabled:
        for event in client.last_trace:
            logger.info(event)


def resolve_url(url: str, config: ClientConfig) -> str:
    if url.startswith(("http://", "https://")):
        return require_http_url(url)
    if config.base_url:
        return require_http_url(
            urljoin(config.base_url.rstrip("/") + "/", url.lstrip("/"))
        )
    raise InvalidUrlError(
        f"Relative URL {url!r} requires a base_url in the active profile "
        "or an absolute http(s) URL"
    )


def parse_json_body(value: str | None):
    if value is None:
        return None
    return json.loads(value)


def parse_pairs(values: list[str]) -> list[tuple[str, str]]:
    """Return ordered (key, value) pairs that preserve repeated keys."""

    pairs: list[tuple[str, str]] = []
    for item in values:
        pairs.append(parse_assignment(item))
    return pairs


def parse_assignment(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise ValueError(f"Expected name=value, got {value!r}")
    key, raw = value.split("=", 1)
    key = key.strip()
    if not key:
        raise ValueError("Assignment name cannot be empty")
    return key, raw


def _method_for(args: argparse.Namespace) -> str:
    if args.command == "get":
        return "GET"
    if args.command == "post":
        return "POST"
    if args.command in {"request", "trace"}:
        return args.method.upper()
    return args.command.upper()


if __name__ == "__main__":
    raise SystemExit(main())
