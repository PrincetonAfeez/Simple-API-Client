"""Raw socket HTTP/1.1 transport.

This module is intentionally readable: it shows DNS lookup, TCP connect, optional
TLS wrapping, HTTP byte serialization, and response parsing as separate steps.
"""

from __future__ import annotations

import socket
import ssl
from time import monotonic

from apiclient.exceptions import ConnectionFailure, RequestTimeout, TransportError
from apiclient.http.parser import (
    DEFAULT_MAX_BODY_SIZE,
    DEFAULT_MAX_CHUNK_SIZE,
    DEFAULT_MAX_HEADER_SIZE,
    read_response,
)
from apiclient.http.url import parse_url
from apiclient.models import CaseInsensitiveHeaders, Request, Response, TimingInfo
from apiclient.observability.redaction import redact_headers, redact_url
from apiclient.observability.timing import ms
from apiclient.resilience.timeout import TimeoutConfig
from apiclient.transport.base import Transport
from apiclient.transport.pool import ConnectionPool

_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})


class _FirstByteSocket:
    def __init__(self, sock: socket.socket, start: float, deadline: float | None) -> None:
        self.sock = sock
        self.start = start
        self.first_byte_at: float | None = None
        self.deadline = deadline

    def recv(self, size: int) -> bytes:
        if self.deadline is not None:
            remaining = self.deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError("total timeout exceeded")
            # Let OSError surface; a failing settimeout means the socket is
            # already broken and we should not pretend the next recv is valid.
            self.sock.settimeout(remaining)
        chunk = self.sock.recv(size)
        if chunk and self.first_byte_at is None:
            self.first_byte_at = monotonic()
        return chunk


class RawSocketTransport(Transport):
    def __init__(
        self,
        *,
        max_header_size: int = DEFAULT_MAX_HEADER_SIZE,
        max_body_size: int = DEFAULT_MAX_BODY_SIZE,
        max_chunk_size: int = DEFAULT_MAX_CHUNK_SIZE,
        pool: ConnectionPool | None = None,
    ) -> None:
        self.max_header_size = max_header_size
        self.max_body_size = max_body_size
        self.max_chunk_size = max_chunk_size
        self.pool = pool

    def send(self, request: Request, timeout: TimeoutConfig) -> Response:
        parsed = parse_url(request.url)
        timings = TimingInfo()
        total_start = monotonic()
        total_deadline = total_start + timeout.total if timeout.total is not None else None
        request.trace.append(
            "URL: "
            f"scheme={parsed.scheme} host={parsed.hostname} port={parsed.port} "
            f"target={parsed.target}"
        )

        sock: socket.socket | ssl.SSLSocket | None = None
        try:
            sock = self._acquire_pooled_socket(parsed)
            if sock is not None:
                request.trace.append(
                    f"Connection: reused pooled socket for {parsed.hostname}:{parsed.port}"
                )
            else:
                dns_start = monotonic()
                addresses = socket.getaddrinfo(
                    parsed.hostname, parsed.port, type=socket.SOCK_STREAM
                )
                timings.dns = monotonic() - dns_start
                request.trace.append(
                    f"DNS lookup: {len(addresses)} address(es) in {ms(timings.dns)}"
                )

                connect_start = monotonic()
                raw_sock = self._connect(
                    addresses, _bounded(timeout.connect, total_deadline)
                )
                timings.tcp_connect = monotonic() - connect_start
                request.trace.append(
                    f"TCP connect: {parsed.hostname}:{parsed.port} in {ms(timings.tcp_connect)}"
                )

                sock = raw_sock
                if parsed.scheme == "https":
                    tls_start = monotonic()
                    context = ssl.create_default_context()
                    sock = context.wrap_socket(raw_sock, server_hostname=parsed.hostname)
                    timings.tls_handshake = monotonic() - tls_start
                    request.trace.append(f"TLS handshake: {ms(timings.tls_handshake)}")

            self._apply_read_timeout(sock, timeout, total_deadline)
            payload, display_headers, keep_alive_requested = self._serialize_request(
                request, parsed
            )
            request.trace.append(f"> {request.method} {parsed.target} HTTP/1.1")
            for key, value in redact_headers(display_headers).items():
                request.trace.append(f"> {key}: {value}")
            if request.body:
                request.trace.append(f"> body: {len(request.body)} byte(s)")

            send_start = monotonic()
            sock.sendall(payload)
            timings.request_send = monotonic() - send_start
            request.trace.append(
                f"Request bytes sent: {len(payload)} in {ms(timings.request_send)}"
            )

            reader = _FirstByteSocket(sock, monotonic(), total_deadline)
            parsed_response = read_response(
                reader,
                method=request.method,
                max_header_size=self.max_header_size,
                max_body_size=self.max_body_size,
                max_chunk_size=self.max_chunk_size,
            )
            timings.time_to_first_byte = (
                (reader.first_byte_at - reader.start)
                if reader.first_byte_at is not None
                else 0.0
            )
            timings.total = monotonic() - total_start
            request.trace.append(
                f"< HTTP/1.1 {parsed_response.status_code} {parsed_response.reason}".rstrip()
            )
            for key, value in redact_headers(parsed_response.headers).items():
                request.trace.append(f"< {key}: {value}")
            request.trace.append(f"Response framing: {parsed_response.framing}")
            request.trace.append(f"Time to first byte: {ms(timings.time_to_first_byte)}")
            request.trace.append(f"Total time: {ms(timings.total)}")

            response = Response(
                status_code=parsed_response.status_code,
                reason=parsed_response.reason,
                headers=parsed_response.headers,
                body=parsed_response.body,
                url=request.url,
                elapsed=timings.total,
                timings=timings,
                request=request,
                framing=parsed_response.framing,
                set_cookies=list(parsed_response.set_cookies),
                trailers=parsed_response.trailers,
            )

            if (
                self.pool is not None
                and keep_alive_requested
                and _can_pool_response(parsed_response.version, parsed_response.headers)
            ):
                self.pool.release(parsed.scheme, parsed.hostname, parsed.port, sock)
                sock = None
            return response
        except TimeoutError as exc:
            # socket.timeout is an alias for TimeoutError in Python 3.10+.
            raise RequestTimeout(f"Timed out while requesting {redact_url(request.url)}") from exc
        except ssl.SSLError as exc:
            raise ConnectionFailure(
                f"TLS failure for {redact_url(request.url)}: {exc}"
            ) from exc
        except OSError as exc:
            # If the socket came from the pool, the `finally` block below will
            # close it, removing the poisoned entry. The retry policy can pick
            # up a fresh connection on the next attempt.
            raise ConnectionFailure(
                f"Socket failure for {redact_url(request.url)}: {exc}"
            ) from exc
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

    def _connect(self, addresses: list[tuple], timeout: float | None) -> socket.socket:
        last_error: OSError | None = None
        for family, socktype, proto, _, sockaddr in addresses:
            sock = socket.socket(family, socktype, proto)
            if timeout is not None:
                sock.settimeout(timeout)
            try:
                sock.connect(sockaddr)
                return sock
            except OSError as exc:
                last_error = exc
                sock.close()
        if last_error:
            raise last_error
        raise TransportError("DNS lookup returned no usable socket addresses")

    def _acquire_pooled_socket(self, parsed) -> socket.socket | ssl.SSLSocket | None:
        if self.pool is None:
            return None
        return self.pool.acquire(parsed.scheme, parsed.hostname, parsed.port)

    def _apply_read_timeout(
        self,
        sock: socket.socket | ssl.SSLSocket,
        timeout: TimeoutConfig,
        total_deadline: float | None,
    ) -> None:
        effective = _bounded(timeout.read, total_deadline)
        if effective is not None:
            sock.settimeout(effective)

    def _serialize_request(
        self, request: Request, parsed
    ) -> tuple[bytes, CaseInsensitiveHeaders, bool]:
        headers = request.headers.copy()
        headers.setdefault("Host", parsed.host_header)
        headers.setdefault("User-Agent", "simple-api-client/0.1")
        headers.setdefault("Accept", "*/*")
        if self.pool is None:
            headers.setdefault("Connection", "close")
        else:
            headers.setdefault("Connection", "keep-alive")
        # Only "keep-alive" counts as keep-alive intent for pooling. Anything
        # else (close, upgrade, te, custom values) means we must not return the
        # socket to the pool after this request.
        connection_value = headers.get("Connection", "").lower()
        keep_alive_requested = "keep-alive" in connection_value

        # RFC 7231: HEAD must not carry a message body.
        body = b"" if request.method.upper() == "HEAD" else request.body

        # Content-Length is owned by the transport (encode_body does not set it).
        if body:
            headers["Content-Length"] = str(len(body))
        elif request.method in _BODY_METHODS:
            # RFC 7230 §3.3.2: methods that can carry a payload must declare
            # Content-Length even when the body is empty.
            headers["Content-Length"] = "0"
        else:
            headers.pop("Content-Length", None)

        lines = [f"{request.method} {parsed.target} HTTP/1.1"]
        for key, value in headers.items():
            if "\r" in key or "\n" in key or "\r" in value or "\n" in value:
                raise TransportError("Header names and values cannot contain CR or LF")
            lines.append(f"{key}: {value}")
        head = "\r\n".join(lines).encode("iso-8859-1") + b"\r\n\r\n"
        return head + body, headers, keep_alive_requested

    def close(self) -> None:
        if self.pool is not None:
            self.pool.close()


def _bounded(value: float | None, deadline: float | None) -> float | None:
    if deadline is None:
        return value
    remaining = max(0.0, deadline - monotonic())
    if value is None:
        return remaining
    return min(value, remaining)


def _can_pool_response(version: str, headers: CaseInsensitiveHeaders) -> bool:
    connection = (headers.get("Connection", "") or "").lower()
    if "close" in connection:
        return False
    if "upgrade" in connection:
        # The peer hijacked the connection (WebSocket, h2c, etc.). Even though
        # we never speak those protocols, returning the socket to the pool
        # would let the next request read leftover Upgrade bytes.
        return False
    # RFC 7230 §A.1.2: HTTP/1.0 responses default to "Connection: close"
    # unless the server explicitly requests keep-alive.
    if version.upper() == "HTTP/1.0":
        return "keep-alive" in connection
    return True
