# ADR 0004: WSGI As Local Server Contract

## Status

Accepted.

## Context

The capstone needs a controlled local target and should show what Django speaks
at the server boundary.

## Decision

The local API is a raw WSGI app using `environ`, `start_response`, and an
iterable of bytes.

## Alternatives considered

- **Django app.** Best fidelity to a real production server, but pulls in a
  framework and obscures the WSGI contract the project is trying to teach.
- **Flask app.** Smaller framework, same problem: the framework wraps WSGI,
  whereas the goal is to *be* the WSGI application.
- **Mock objects in tests, no local server.** Loses the ability to exercise
  real socket I/O, chunked framing, and redirect behavior end-to-end.
- **HTTPS-on-localhost via a generated cert.** Worth doing for a TLS demo;
  declined here to keep the test setup zero-config. The TLS branch in
  `RawSocketTransport` is exercised separately by `https://` smoke tests.

## Consequences

The client can exercise auth, pagination, retries, redirects, and request bodies
without turning the capstone into a web app. Chunked response tests use a tiny
raw-socket server because WSGI apps should not manually emit
`Transfer-Encoding: chunked` — `wsgiref` is also HTTP/1.0-only, so keep-alive
behavior must be verified with the hand-rolled HTTP/1.1 server.
