# Protocol Notes

## One Request

`apiclient get http://127.0.0.1:8000/health --transport raw --trace`

1. The CLI parses arguments.
2. `ApiClient` builds a `Request`.
3. URL parsing separates scheme, hostname, port, path, and query.
4. DNS lookup resolves the host.
5. A TCP socket connects to the selected address.
6. For HTTPS, TLS wraps the TCP socket before HTTP bytes are sent.
7. The raw transport serializes the request line and headers with CRLF.
8. The parser reads until `CRLF CRLF` marks the end of headers.
9. The parser chooses body framing: content length, chunked, bodyless, or
   connection close.
10. The CLI decodes and prints the response.

## Partial Reads

TCP is a byte stream. One `recv()` call may return a full response, part of a
header, part of a body, or multiple pieces at once. The parser keeps a buffer and
only advances when enough bytes have arrived.

## Content-Length Vs Chunked

`Content-Length` tells the parser exactly how many body bytes to read.

`Transfer-Encoding: chunked` sends the body as repeated chunks:

```text
size-in-hex CRLF
chunk-bytes CRLF
0 CRLF
optional trailers CRLF
```

The parser enforces maximum chunk and decoded-body sizes.

## WSGI Is Not HTTP

WSGI is a Python server/application interface. The WSGI app receives normalized
request data in `environ` and returns body bytes. HTTP framing, TCP sockets, and
hop-by-hop headers are handled by the server or gateway.

## Intentional Limitations

- **Folded headers** (obsolete line continuation with leading space/tab) are
  rejected with ``ProtocolError``.
- **1xx responses** (including ``101 Switching Protocols``) are consumed and
  skipped until a non-1xx status line is parsed.
- **``Transfer-Encoding`` + ``Content-Length``** on the same response: if
  ``chunked`` appears in ``Transfer-Encoding``, the chunked reader is used and
  ``Content-Length`` is ignored (RFC 7230 §3.3.3).
- **Cookies**: ``Set-Cookie`` values are stored on ``Response.set_cookies`` but
  are not sent on subsequent requests (no cookie jar).
- **Compression**: ``Content-Encoding`` is not decoded; body bytes are raw.
- **Upload framing**: the client does not emit chunked request bodies.

## What Was Hard

The tricky parts are boundaries: partial reads, body size limits, malformed
framing, redirect auth safety, and making retries visible without making the
client retry unsafe methods by default.
