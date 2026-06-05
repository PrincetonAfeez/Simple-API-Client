# Demo oral-exam questions

If you can answer these from memory while running the commands in
[demo-script.md](demo-script.md), you meet the capstone demo pass/fail criteria
(section 18 of the revised scope).

## The twelve core questions

1. **URL decomposition** — For `http://127.0.0.1:8000/items?limit=10`, what are
   scheme, hostname, port, path, and query?

2. **DNS** — When does hostname resolution happen in the raw transport trace?

3. **TCP** — When is the socket connected? What does “byte stream” mean for the
   parser?

4. **TLS** — For HTTPS, what happens after TCP connect and before HTTP bytes are
   sent?

5. **Request bytes** — What is on the wire for `GET /health HTTP/1.1` plus
   headers? Why `\r\n\r\n`?

6. **Response framing** — How did the parser know where the body ended for your
   last response (`Content-Length`, chunked, or connection close)?

7. **Retries** — When does `RetryPolicy` retry? Why might POST not retry by
   default? What does `Retry-After` do?

8. **Auth redaction** — Where could secrets leak without redaction? What does
   `--curl` show instead of the raw token?

9. **Redirects** — What happens to `Authorization` on a cross-host 302? What
   does `--preserve-auth-across-hosts` change?

10. **WSGI** — How does `server/wsgi_app.py` differ from speaking HTTP on the
    wire? Name `environ`, `start_response`, and the response iterable.

11. **Transport swap** — Why does `apiclient get … --transport urllib` use the
    same CLI code path?

12. **Production** — What would you use in production and what hard problems
    does this educational client intentionally skip?

## Bonus questions graders sometimes ask

- Why is chunked testing done with fixtures / a raw test server instead of the
  WSGI app?
- What parser safety limits exist and why?
- Why is `fetch_many` trace unreliable with `concurrency > 1`?
- Why does `HEAD` not send a body even if one was attached to `Request`?

## One-sentence production reflection (memorize)

“This client proves I understand HTTP/1.1 on the wire; in production I would use
`requests` or `httpx` because they already solve cookies, compression, HTTP/2,
and years of edge cases.”
