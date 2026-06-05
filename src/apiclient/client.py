"""High-level API client that is independent of the chosen transport."""

from __future__ import annotations

import json as json_module
from dataclasses import asdict
from time import sleep as default_sleep
from typing import Mapping, Sequence

from apiclient.auth.base import AuthStrategy
from apiclient.exceptions import HttpStatusError, RedirectError, RetryExhausted, TransportError
from apiclient.http.encode import encode_body
from apiclient.http.redirects import RedirectPolicy
from apiclient.http.url import merge_query_params, require_http_url
from apiclient.models import CaseInsensitiveHeaders, Request, Response
from apiclient.observability.redaction import redact_secret
from apiclient.resilience.retry import RetryPolicy
from apiclient.resilience.timeout import TimeoutConfig
from apiclient.transport.base import Transport
from apiclient.transport.socket_transport import RawSocketTransport


class ApiClient:
    """Synchronous HTTP client with retries, redirects, and transport swapping.

    ``last_trace`` and ``last_request`` reflect only the most recent call. They
    are not safe to read while using :func:`~apiclient.concurrency.fetch_many`
    with ``concurrency > 1``.
    """

    def __init__(
        self,
        *,
        transport: Transport | None = None,
        retry_policy: RetryPolicy | None = None,
        redirect_policy: RedirectPolicy | None = None,
        timeout: TimeoutConfig | None = None,
        sleep_func=default_sleep,
    ) -> None:
        self.transport = transport or RawSocketTransport()
        self.retry_policy = retry_policy or RetryPolicy()
        self.redirect_policy = redirect_policy or RedirectPolicy()
        self.timeout = timeout or TimeoutConfig()
        self.sleep_func = sleep_func
        self.last_trace: list[str] = []
        self.last_request: Request | None = None

    def close(self) -> None:
        """Release transport resources (e.g. close pooled sockets)."""

        self.transport.close()

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self.close()

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | Sequence[str] | None = None,
        params: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
        json: object | None = None,
        form: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
        data: str | bytes | None = None,
        binary_file: str | None = None,
        auth: AuthStrategy | None = None,
        timeout: TimeoutConfig | None = None,
        follow_redirects: bool = True,
        fail: bool = False,
        trace: bool = False,
    ) -> Response:
        header_map = _normalize_headers(headers)
        body, header_map = encode_body(
            json_value=json,
            form=form,
            data=data,
            binary_file=binary_file,
            headers=header_map,
        )
        prepared_url = require_http_url(merge_query_params(url, params))
        request = Request(method=method, url=prepared_url, headers=header_map, body=body)
        return self.send(
            request,
            auth=auth,
            timeout=timeout,
            follow_redirects=follow_redirects,
            fail=fail,
            trace=trace,
        )

    def send(
        self,
        request: Request,
        *,
        auth: AuthStrategy | None = None,
        timeout: TimeoutConfig | None = None,
        follow_redirects: bool = True,
        fail: bool = False,
        trace: bool = False,
    ) -> Response:
        validated_url = require_http_url(request.url)
        prepared = request.copy_with(
            url=validated_url,
            headers=request.headers.copy(),
            trace=list(request.trace),
        )
        if trace:
            prepared.trace.append(f"Preparing {prepared.method} {prepared.url}")
        secrets_to_mask: list[str] = []
        if auth is not None:
            secrets_to_mask = list(auth.secrets())
            prepared = auth.apply(prepared)
            if trace:
                prepared.trace.append(f"Applied auth strategy: {auth.__class__.__name__}")
        self.last_request = prepared

        response = self._send_with_redirects(
            prepared,
            timeout or self.timeout,
            follow_redirects=follow_redirects,
            auth=auth,
        )
        trace_target = (
            response.request.trace if response.request is not None else prepared.trace
        )
        if secrets_to_mask:
            _redact_secrets_in_trace(trace_target, secrets_to_mask)
        self.last_trace = trace_target
        if fail and not response.ok:
            raise HttpStatusError(f"HTTP {response.status_code} {response.reason} for {response.url}")
        return response

    def _send_with_redirects(
        self,
        request: Request,
        timeout: TimeoutConfig,
        *,
        follow_redirects: bool,
        auth: AuthStrategy | None = None,
    ) -> Response:
        current = request
        history = []
        for hop in range(self.redirect_policy.max_hops + 1):
            response = self._send_with_retries(current, timeout)
            response.history = list(history)
            if not follow_redirects or not self.redirect_policy.is_redirect(response):
                return response
            if hop >= self.redirect_policy.max_hops:
                raise RedirectError(f"Too many redirects; max is {self.redirect_policy.max_hops}")
            next_request, record = self.redirect_policy.next_request(
                current, response, auth=auth
            )
            history.append(record)
            next_request.trace.append(
                f"Redirect: HTTP {response.status_code} -> {next_request.method} {next_request.url}"
            )
            current = next_request
        raise RedirectError("Redirect handling ended unexpectedly")

    def _send_with_retries(self, request: Request, timeout: TimeoutConfig) -> Response:
        last_error: BaseException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            if attempt > 1:
                request.trace.append(f"Retry attempt {attempt}/{self.retry_policy.max_attempts}")
            try:
                response = self.transport.send(request, timeout)
            except TransportError as exc:
                last_error = exc
                if not self._can_retry_exception(request, exc, attempt):
                    if (
                        self.retry_policy.retries > 0
                        and self.retry_policy.should_retry_exception(request.method, exc)
                    ):
                        raise RetryExhausted(
                            f"Retry exhausted after {attempt} attempt(s): {exc}"
                        ) from exc
                    raise
                delay = self.retry_policy.delay_for(attempt)
                request.trace.append(
                    f"Retrying after {exc.__class__.__name__}; sleeping {delay:.2f}s"
                )
                self.sleep_func(delay)
                continue

            if self.retry_policy.should_retry_response(request.method, response):
                if attempt >= self.retry_policy.max_attempts:
                    if self.retry_policy.retries > 0:
                        raise RetryExhausted(
                            f"Retry exhausted after {attempt} attempt(s); "
                            f"last response was HTTP {response.status_code}"
                        )
                    return response
                delay = self.retry_policy.delay_for(attempt, response)
                request.trace.append(
                    f"Retryable HTTP {response.status_code}; sleeping {delay:.2f}s"
                )
                self.sleep_func(delay)
                continue
            return response

        if last_error is not None:
            raise RetryExhausted(
                f"Retry exhausted after {self.retry_policy.max_attempts} attempt(s): {last_error}"
            ) from last_error
        raise RetryExhausted(f"Retry exhausted after {self.retry_policy.max_attempts} attempt(s)")

    def _can_retry_exception(self, request: Request, exc: BaseException, attempt: int) -> bool:
        return (
            attempt < self.retry_policy.max_attempts
            and self.retry_policy.retries > 0
            and self.retry_policy.should_retry_exception(request.method, exc)
        )


def _redact_secrets_in_trace(trace: list[str], secrets: list[str]) -> None:
    """Replace any plaintext secret occurrence in trace events with its mask.

    Called once after all transports / redirect hops have appended their trace
    events, so a secret that survived header redaction (e.g. embedded in a URL
    path) is still masked before the user reads the trace.
    """

    for raw in secrets:
        if not raw:
            continue
        masked = redact_secret(raw)
        for i, line in enumerate(trace):
            if raw in line:
                trace[i] = line.replace(raw, masked)


def _normalize_headers(headers: Mapping[str, str] | Sequence[str] | None) -> CaseInsensitiveHeaders:
    header_map = CaseInsensitiveHeaders()
    if headers is None:
        return header_map
    if hasattr(headers, "items"):
        header_map.update(headers)  # type: ignore[arg-type]
        return header_map
    for header in headers:
        if ":" not in header:
            raise ValueError(f"Header must be in 'Name: value' format: {header!r}")
        name, value = header.split(":", 1)
        header_map[name.strip()] = value.strip()
    return header_map


_TEXT_MEDIA_PREFIXES = ("text/", "application/xml", "application/x-www-form-urlencoded")


def response_summary(response: Response) -> dict[str, object]:
    content_type = (response.headers.get("Content-Type") or "").lower()
    body: object
    if "json" in content_type:
        try:
            body = response.json()
        except json_module.JSONDecodeError:
            body = response.text
    elif any(content_type.startswith(prefix) for prefix in _TEXT_MEDIA_PREFIXES) or not content_type:
        body = response.text
    else:
        body = f"<{len(response.body)} binary bytes>"
    return {
        "status_code": response.status_code,
        "reason": response.reason,
        "url": response.url,
        "headers": dict(response.headers.items()),
        "body": body,
        "elapsed": response.elapsed,
        "framing": response.framing,
        "timings": response.timings.as_dict(),
        "history": [asdict(record) for record in response.history],
    }
