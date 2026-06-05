# ADR 0001: Raw Sockets Vs Library Backend

## Status

Accepted.

## Context

The capstone needs to demonstrate HTTP over TCP/IP, not only use a convenient
HTTP abstraction.

## Decision

The project provides two transports behind one interface:

- `RawSocketTransport` for DNS, TCP, TLS, HTTP byte serialization, and manual
  response parsing.
- `UrllibTransport` for comparison with a mature standard-library backend.

## Alternatives considered

- **`requests` or `httpx` only.** Most concise option, but it hides the very
  layers the capstone is intended to teach (Content-Length vs chunked, TLS
  wrapping, partial reads, redirect rewriting).
- **Raw socket only.** Cleaner story, but loses the side-by-side comparison
  that makes the library transport's value visible.
- **Two unrelated client classes.** Rejected because the `ApiClient` /
  `Transport` split is the architectural point — the higher layer doesn't
  know which backend is underneath.

## Consequences

The CLI and `ApiClient` can swap transports without changing behavior. The raw
transport remains educational and intentionally small; the library transport
shows what production code normally delegates. Two implementations means two
trace formats — bridged by a shared `framing` vocabulary (`chunked`,
`content-length`, `bodyless`, `connection-close`) derived in both transports.
