# Written report outline (capstone)

Copy this structure into your course report (Word/Google Docs/PDF). Replace
italic prompts with your own prose. Target 8–15 pages unless your syllabus
specifies otherwise.

---

## Cover page

- Project title: **Simple API Client**
- Student name, ID, course, instructor, date
- Repository URL
- One-line abstract

---

## 1. Abstract (150–250 words)

_Summarize: educational CLI HTTP client; raw socket transport; library transport
for comparison; WSGI demo server; goal is protocol understanding, not replacing
requests/httpx._

---

## 2. Introduction & goals

- Problem: developers use `requests.get()` without seeing DNS, TCP, TLS, framing
- Learning objectives (from capstone scope §2): URL, DNS, TCP, TLS, HTTP/1.1
  serialization/parsing, auth, retries, pagination, asyncio fan-out, WSGI
- Constraints: Python, CLI-first, student-readable code, not production-grade

---

## 3. Architecture

- Include diagram from [architecture.md](architecture.md)
- Layer table: CLI → client → http / transport / auth / pagination / resilience
- Dependency rule: one-way imports; `Transport` interface
- Reference ADRs 0001–0004 (one paragraph each)

---

## 4. Protocol deep-dive (core section)

### 4.1 One traced GET

Walk through a real `--trace` log for `GET /health` (raw transport):

- URL parsing
- DNS / TCP / (TLS if HTTPS)
- Request line and headers
- Response status and headers
- Body framing (`Content-Length` example)

### 4.2 Partial reads

Explain why `recv()` can return a fragment and how the parser buffers.

### 4.3 Content-Length vs chunked

Compare framing modes; mention TE+CL conflict policy (chunked wins when
`chunked` in `Transfer-Encoding`).

### 4.4 Parser safety limits

List max header size, body size, chunk size, line counts, timeouts.

---

## 5. Features (brief, behavior-focused)

| Feature | Design choice | Key file |
|---------|---------------|----------|
| Auth | Bearer, Basic, API key; `secrets()` redaction | `auth/` |
| Retries | Idempotent methods; backoff; Retry-After | `resilience/retry.py` |
| Redirects | Cross-host strip; 303 POST→GET | `http/redirects.py` |
| Pagination | offset/page/cursor/link; cycle guards | `pagination/` |
| Concurrency | `asyncio.to_thread` + semaphore | `concurrency/` |
| Config | TOML profiles; CLI overrides | `config.py` |

---

## 6. WSGI demo server

- Why WSGI instead of only mocking HTTP
- Contract: `environ`, `start_response`, byte iterable
- Endpoints: health, private, items, flaky, redirect, echo
- Demo credentials are lab-only

---

## 7. Testing & quality

- Test pyramid: unit (parser, policy) vs integration (WSGI)
- Example counts: _run `pytest -q` and paste summary_
- Coverage gate (80%+ on package)
- CI: Ubuntu + Windows; Python 3.11–3.14; ruff
- How to reproduce: see [windows-testing.md](windows-testing.md)

---

## 8. Limitations & future work

Pull from README “Out of scope” and [production-reflection.md](production-reflection.md):

- No cookie jar, HTTP/2, gzip, multipart, proxies
- Educational pool vs production connection management
- Redirect auth strip heuristics

---

## 9. Conclusion

_What you learned; why the project is stronger for admitting limits; when you
would reach for mature libraries._

---

## 10. References

- RFC 9110 / 7230 (HTTP semantics)
- PEP 3333 (WSGI)
- Python `socket`, `ssl`, `urllib` documentation
- Course materials (if applicable)

---

## Appendix A — Sample commands

Paste from README: install, server, trace, auth, flaky, paginate, bench.

## Appendix B — Exit code table

Paste from README exit codes section.
