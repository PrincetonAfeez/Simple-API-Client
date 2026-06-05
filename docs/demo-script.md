# Demo Script

1. Start the local server:

   ```powershell
   python server/run_server.py --host 127.0.0.1 --port 8000
   ```

2. Show `server/wsgi_app.py`.

   Point out `environ`, `start_response`, and the returned iterable of bytes.

3. Run a traced raw request:

   ```powershell
   apiclient get http://127.0.0.1:8000/health --transport raw --trace
   ```

   Explain URL parsing, DNS, TCP connect, request line, headers, response status,
   response headers, `Content-Length`, and timings.

4. Show HTTPS layering:

   ```powershell
   apiclient get https://example.com --transport raw --trace
   ```

   Explain that TCP connects first, TLS wraps the socket, then HTTP bytes are
   exchanged inside TLS.

5. Run auth:

   ```powershell
   apiclient get http://127.0.0.1:8000/private --bearer-token demo-token --trace --curl
   ```

   Show that the request succeeds and the token is redacted.

6. Run retries:

   ```powershell
   apiclient get 'http://127.0.0.1:8000/flaky?key=demo&succeed_after=2' --retries 2 --trace
   ```

   Explain retryable status, `Retry-After`, and idempotent method behavior.

7. Run pagination:

   ```powershell
   apiclient paginate http://127.0.0.1:8000/items --strategy offset --limit 10 --max-pages 3
   ```

   Explain lazy page fetching and the max-page safety cap.

8. Swap transports:

   ```powershell
   apiclient get http://127.0.0.1:8000/health --transport urllib
   ```

   Explain that only the backend changed.

9. Run async fan-out:

   ```powershell
   apiclient bench http://127.0.0.1:8000/items/{id} --count 25 --concurrency 5
   ```

   Note: per-request `--trace` is not reliable when `concurrency > 1` (documented
   warning). For the demo, use concurrency 1 with trace, or show bench summary only.

10. End with the production reflection.

    Use [production-reflection.md](production-reflection.md) and memorize the
    one-liner in [demo-questions.md](demo-questions.md).

## Before you present

- Rehearse on a clean machine: `pip install -e ".[dev]"`, start server, run steps 3–9.
- Run `python scripts/verify_submission.py` from the repo root.
- Review [demo-questions.md](demo-questions.md) (12 core questions).
- Fill course metadata in README and your report cover page.
