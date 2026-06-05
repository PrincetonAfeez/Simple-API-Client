"""HTTP/1.1 response parser for the educational raw socket transport."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from apiclient.exceptions import ProtocolError, RequestTimeout
from apiclient.models import CaseInsensitiveHeaders

CRLF = b"\r\n"
HEADER_END = b"\r\n\r\n"
DEFAULT_MAX_HEADER_SIZE = 64 * 1024
DEFAULT_MAX_BODY_SIZE = 10 * 1024 * 1024
DEFAULT_MAX_CHUNK_SIZE = 1024 * 1024
DEFAULT_MAX_HEADER_LINES = 200
DEFAULT_MAX_TRAILER_LINES = 50


class RecvStream(Protocol):
    def recv(self, size: int) -> bytes:
        ...


@dataclass(slots=True)
class ParsedResponse:
    version: str
    status_code: int
    reason: str
    headers: CaseInsensitiveHeaders
    body: bytes
    framing: str
    set_cookies: list[str] = field(default_factory=list)
    trailers: CaseInsensitiveHeaders = field(default_factory=CaseInsensitiveHeaders)


class _BufferedReader:
    def __init__(self, stream: RecvStream, initial: bytes = b"") -> None:
        self.stream = stream
        self.buffer = bytearray(initial)

    def _recv(self, size: int = 4096) -> bytes:
        try:
            chunk = self.stream.recv(size)
        except TimeoutError as exc:
            # socket.timeout is an alias for TimeoutError in Python 3.10+.
            raise RequestTimeout("Timed out while reading HTTP response bytes") from exc
        if chunk == b"":
            return b""
        self.buffer.extend(chunk)
        return chunk

    def ensure(self, size: int) -> None:
        while len(self.buffer) < size:
            if not self._recv(max(4096, size - len(self.buffer))):
                raise ProtocolError("Connection closed before the expected response bytes arrived")

    def read_exact(self, size: int) -> bytes:
        self.ensure(size)
        out = bytes(self.buffer[:size])
        del self.buffer[:size]
        return out

    def read_line(self, max_line_size: int = DEFAULT_MAX_HEADER_SIZE) -> bytes:
        while True:
            idx = self.buffer.find(CRLF)
            if idx >= 0:
                out = bytes(self.buffer[:idx])
                del self.buffer[: idx + len(CRLF)]
                return out
            if len(self.buffer) > max_line_size:
                raise ProtocolError("HTTP line exceeded parser safety limit")
            if not self._recv():
                raise ProtocolError("Connection closed before a CRLF-terminated line arrived")

    def read_until_close(self, max_body_size: int) -> bytes:
        body = bytearray(self.buffer)
        self.buffer.clear()
        if len(body) > max_body_size:
            raise ProtocolError("Response body exceeded parser safety limit")
        while True:
            chunk = self._recv()
            if not chunk:
                return bytes(body)
            body.extend(chunk)
            if len(body) > max_body_size:
                raise ProtocolError("Response body exceeded parser safety limit")


def read_response(
    stream: RecvStream,
    *,
    method: str = "GET",
    max_header_size: int = DEFAULT_MAX_HEADER_SIZE,
    max_body_size: int = DEFAULT_MAX_BODY_SIZE,
    max_chunk_size: int = DEFAULT_MAX_CHUNK_SIZE,
) -> ParsedResponse:
    """Read and parse one HTTP/1.1 response from a recv()-compatible stream.

    Per RFC 7230 §3.1.2, 1xx informational responses (other than 101) are
    consumed and discarded; the final non-1xx response is returned.
    """

    # Loop over any 1xx informational responses before the real one.
    while True:
        header_bytes, body_start = _read_header_block(stream, max_header_size)
        version, status_code, reason, headers, set_cookies = _parse_header_block(header_bytes)
        if 100 <= status_code < 200:
            # body_start contains bytes that came after this 1xx's CRLFCRLF —
            # they are the beginning of the next response. Splice them back in
            # front of the underlying stream for the next iteration.
            if body_start:
                stream = _PrefixedStream(body_start, stream)
            continue
        break

    if _response_has_no_body(method, status_code):
        return ParsedResponse(
            version, status_code, reason, headers, b"", "bodyless", set_cookies=set_cookies,
        )

    transfer_encoding = headers.get("Transfer-Encoding", "") or ""
    if "chunked" in transfer_encoding.lower():
        reader = _BufferedReader(stream, body_start)
        body, trailers = _read_chunked_body(
            reader, max_body_size=max_body_size, max_chunk_size=max_chunk_size
        )
        return ParsedResponse(
            version,
            status_code,
            reason,
            headers,
            body,
            "chunked",
            set_cookies=set_cookies,
            trailers=trailers,
        )

    content_length = headers.get("Content-Length")
    if content_length is not None:
        # RFC 7230 §3.3.2 specifies 1*DIGIT — no leading sign, no whitespace
        # inside the value (after header trimming).
        stripped = content_length.strip()
        if not stripped or not stripped.isdigit():
            raise ProtocolError(f"Invalid Content-Length: {content_length!r}")
        length = int(stripped)
        if length > max_body_size:
            raise ProtocolError("Response body exceeded parser safety limit")
        reader = _BufferedReader(stream, body_start)
        body = reader.read_exact(length)
        return ParsedResponse(
            version,
            status_code,
            reason,
            headers,
            body,
            "content-length",
            set_cookies=set_cookies,
        )

    reader = _BufferedReader(stream, body_start)
    body = reader.read_until_close(max_body_size)
    return ParsedResponse(
        version,
        status_code,
        reason,
        headers,
        body,
        "connection-close",
        set_cookies=set_cookies,
    )


class _PrefixedStream:
    """Wraps a stream so the first recv calls drain a leading byte buffer.

    Used to feed leftover bytes (e.g. the next response after a 1xx) back
    into the parser without changing the public stream interface.
    """

    __slots__ = ("_prefix", "_inner")

    def __init__(self, prefix: bytes, inner: RecvStream) -> None:
        self._prefix = bytearray(prefix)
        self._inner = inner

    def recv(self, size: int) -> bytes:
        if self._prefix:
            count = min(size, len(self._prefix))
            chunk = bytes(self._prefix[:count])
            del self._prefix[:count]
            return chunk
        return self._inner.recv(size)


def parse_response_bytes(raw: bytes, *, method: str = "GET", recv_chunk_size: int = 4096) -> ParsedResponse:
    """Parse a complete response fixture while still exercising partial reads."""

    class ByteStream:
        def __init__(self, data: bytes) -> None:
            self.data = bytearray(data)

        def recv(self, size: int) -> bytes:
            count = min(size, recv_chunk_size, len(self.data))
            if count <= 0:
                return b""
            out = bytes(self.data[:count])
            del self.data[:count]
            return out

    return read_response(ByteStream(raw), method=method)


def _read_header_block(stream: RecvStream, max_header_size: int) -> tuple[bytes, bytes]:
    buffer = bytearray()
    while HEADER_END not in buffer:
        if len(buffer) > max_header_size:
            raise ProtocolError("HTTP headers exceeded parser safety limit")
        try:
            chunk = stream.recv(4096)
        except TimeoutError as exc:
            # socket.timeout is an alias for TimeoutError in Python 3.10+.
            raise RequestTimeout("Timed out before HTTP response headers arrived") from exc
        if not chunk:
            raise ProtocolError("Connection closed before HTTP response headers arrived")
        buffer.extend(chunk)
    header_bytes, body_start = bytes(buffer).split(HEADER_END, 1)
    if len(header_bytes) > max_header_size:
        raise ProtocolError("HTTP headers exceeded parser safety limit")
    return header_bytes, body_start


def _parse_header_block(
    header_bytes: bytes,
    max_lines: int = DEFAULT_MAX_HEADER_LINES,
) -> tuple[str, int, str, CaseInsensitiveHeaders, list[str]]:
    # ISO-8859-1 is a total decoder — every byte maps to a code point — so this
    # cannot raise UnicodeDecodeError. The choice satisfies RFC 9110 §5.5.
    lines = header_bytes.decode("iso-8859-1").split("\r\n")

    if not lines or not lines[0]:
        raise ProtocolError("Missing HTTP status line")
    parts = lines[0].split(" ", 2)
    if len(parts) < 2 or not parts[0].startswith("HTTP/"):
        raise ProtocolError(f"Malformed HTTP status line: {lines[0]!r}")
    version = parts[0]
    try:
        status_code = int(parts[1])
    except ValueError as exc:
        raise ProtocolError(f"Malformed HTTP status code: {parts[1]!r}") from exc
    reason = parts[2] if len(parts) == 3 else ""

    headers = CaseInsensitiveHeaders()
    set_cookies: list[str] = []
    seen_lines = 0
    for line in lines[1:]:
        if not line:
            continue
        seen_lines += 1
        if seen_lines > max_lines:
            raise ProtocolError(
                f"HTTP header field count exceeded parser safety limit ({max_lines})"
            )
        if line.startswith((" ", "\t")):
            raise ProtocolError("Obsolete folded headers are not supported")
        if ":" not in line:
            raise ProtocolError(f"Malformed header line: {line!r}")
        name, value = line.split(":", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            raise ProtocolError("Header name cannot be empty")
        if name.lower() == "set-cookie":
            # RFC 6265 §3: Set-Cookie headers are not comma-joinable. Keep each
            # cookie as its own list entry; expose the most recent value through
            # the regular header map for convenience.
            set_cookies.append(value)
            headers[name] = value
            continue
        if name in headers:
            headers[name] = f"{headers[name]}, {value}"
        else:
            headers[name] = value
    return version, status_code, reason, headers, set_cookies


def _response_has_no_body(method: str, status_code: int) -> bool:
    if method.upper() == "HEAD":
        return True
    return 100 <= status_code < 200 or status_code in {204, 205, 304}


def _read_chunked_body(
    reader: _BufferedReader,
    *,
    max_body_size: int,
    max_chunk_size: int,
) -> tuple[bytes, CaseInsensitiveHeaders]:
    decoded = bytearray()
    while True:
        line = reader.read_line()
        size_token = line.split(b";", 1)[0].strip()
        if not size_token:
            raise ProtocolError("Missing chunk size")
        try:
            chunk_size = int(size_token, 16)
        except ValueError as exc:
            raise ProtocolError(f"Invalid chunk size: {size_token!r}") from exc
        if chunk_size > max_chunk_size:
            raise ProtocolError("Chunk size exceeded parser safety limit")
        if chunk_size == 0:
            trailers = _consume_trailers(reader)
            return bytes(decoded), trailers
        if len(decoded) + chunk_size > max_body_size:
            raise ProtocolError("Decoded chunked body exceeded parser safety limit")
        decoded.extend(reader.read_exact(chunk_size))
        if reader.read_exact(2) != CRLF:
            raise ProtocolError("Chunk data was not followed by CRLF")


def _consume_trailers(
    reader: _BufferedReader, max_lines: int = DEFAULT_MAX_TRAILER_LINES
) -> CaseInsensitiveHeaders:
    trailers = CaseInsensitiveHeaders()
    seen = 0
    while True:
        line = reader.read_line()
        if line == b"":
            return trailers
        seen += 1
        if seen > max_lines:
            raise ProtocolError(
                f"HTTP trailer field count exceeded parser safety limit ({max_lines})"
            )
        if b":" not in line:
            raise ProtocolError("Malformed trailer header")
        name, _, value = line.partition(b":")
        # ISO-8859-1 cannot fail to decode.
        decoded_name = name.decode("iso-8859-1").strip()
        decoded_value = value.decode("iso-8859-1").strip()
        if not decoded_name:
            raise ProtocolError("Trailer header name cannot be empty")
        if decoded_name in trailers:
            trailers[decoded_name] = f"{trailers[decoded_name]}, {decoded_value}"
        else:
            trailers[decoded_name] = decoded_value
