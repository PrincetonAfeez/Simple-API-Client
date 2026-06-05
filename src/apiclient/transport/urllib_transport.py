"""Standard-library transport behind the same interface as RawSocketTransport."""

from __future__ import annotations

import socket
import urllib.error
import urllib.request
from time import monotonic

from apiclient.exceptions import ConnectionFailure, RequestTimeout
from apiclient.http.url import parse_url
from apiclient.models import CaseInsensitiveHeaders, Request, Response, TimingInfo
from apiclient.observability.redaction import redact_headers, redact_url
from apiclient.observability.timing import ms
from apiclient.resilience.timeout import TimeoutConfig
from apiclient.transport.base import Transport


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Defers redirect handling to the project's RedirectPolicy.

    Returning ``None`` from ``redirect_request`` tells urllib that this handler
    will not produce a new request. urllib then raises ``HTTPError`` for the
    redirect response, which we capture below and translate into a normal
    ``Response`` so the higher-level client can apply its own policy.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class UrllibTransport(Transport):
    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(_NoRedirectHandler)

    def send(self, request: Request, timeout: TimeoutConfig) -> Response:
        parse_url(request.url)
        headers = dict(request.headers.items())
        request.trace.append(f"urllib transport: {request.method} {redact_url(request.url)}")
        for key, value in redact_headers(request.headers).items():
            request.trace.append(f"> {key}: {value}")

        timings = TimingInfo()
        host_for_dns = _hostname_for(request.url)
        if host_for_dns is not None:
            try:
                dns_start = monotonic()
                socket.getaddrinfo(host_for_dns, None, type=socket.SOCK_STREAM)
                timings.dns = monotonic() - dns_start
                request.trace.append(f"DNS lookup: {ms(timings.dns)}")
            except OSError:
                # DNS will fail again inside urllib and surface as ConnectionFailure.
                pass

        start = monotonic()
        payload = None
        if request.method.upper() != "HEAD" and request.body:
            payload = request.body
        req = urllib.request.Request(
            request.url,
            data=payload,
            headers=headers,
            method=request.method,
        )
        effective_timeout = (
            timeout.total if timeout.total is not None else max(timeout.connect, timeout.read)
        )
        try:
            raw_response = self._opener.open(req, timeout=effective_timeout)
        except urllib.error.HTTPError as exc:
            raw_response = exc
        except TimeoutError as exc:
            raise RequestTimeout(
                f"Timed out while requesting {redact_url(request.url)}"
            ) from exc
        except OSError as exc:
            raise ConnectionFailure(
                f"urllib failure for {redact_url(request.url)}: {exc}"
            ) from exc

        try:
            body = raw_response.read()
            elapsed = monotonic() - start
            timings.total = elapsed
            headers_obj = CaseInsensitiveHeaders(raw_response.headers.items())
            reason = getattr(raw_response, "reason", "") or ""
            status = raw_response.getcode()
            set_cookies = list(raw_response.headers.get_all("Set-Cookie") or [])
            framing = _derive_framing(request.method, status, headers_obj)
            request.trace.append(f"< HTTP {status} {reason}".rstrip())
            for key, value in redact_headers(headers_obj).items():
                request.trace.append(f"< {key}: {value}")
            request.trace.append(f"Response framing: {framing}")
            request.trace.append(f"Total time: {ms(elapsed)}")
            return Response(
                status_code=status,
                reason=str(reason),
                headers=headers_obj,
                body=body,
                url=request.url,
                elapsed=elapsed,
                timings=timings,
                request=request,
                framing=framing,
                set_cookies=set_cookies,
            )
        finally:
            raw_response.close()


def _hostname_for(url: str) -> str | None:
    from urllib.parse import urlsplit

    try:
        return urlsplit(url).hostname
    except ValueError:
        return None


def _derive_framing(method: str, status_code: int, headers: CaseInsensitiveHeaders) -> str:
    if method.upper() == "HEAD" or 100 <= status_code < 200 or status_code in {204, 205, 304}:
        return "bodyless"
    transfer_encoding = (headers.get("Transfer-Encoding") or "").lower()
    if "chunked" in transfer_encoding:
        return "chunked"
    if headers.get("Content-Length") is not None:
        return "content-length"
    return "connection-close"
