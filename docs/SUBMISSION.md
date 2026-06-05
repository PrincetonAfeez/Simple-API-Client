# Capstone submission guide

Use this checklist before handing in the project or presenting live. It maps to
the rubric in `api_client_capstone_revised_scope.txt` (section 20) and the demo
pass/fail criteria (section 18).

## Quick verification

From the repository root:

```powershell
python scripts/verify_submission.py
```

Or manually:

```powershell
python -m pip install -r requirements.lock
python -m pip install -e .
pytest -q
ruff check src tests server
python -m compileall -q src server tests
apiclient --version
```

For a flexible (non-pinned) install, `python -m pip install -e ".[dev]"` is equivalent.

## Pre-submission gate (all required)

| # | Item | How to verify |
|---|------|----------------|
| 1 | All tests pass | `pytest -q` → 0 failures |
| 2 | Lint clean | `ruff check src tests server` |
| 3 | Package installs | `pip install -e .` then `apiclient --version` |
| 4 | Demo server starts | `python server/run_server.py --port 8000` |
| 5 | Traced raw request works | See [demo-script.md](demo-script.md) step 3 |
| 6 | No secrets in repo | No real tokens in git history or screenshots |
| 7 | GitHub URLs valid | Update `[project.urls]` in `pyproject.toml` |
| 8 | Docs complete | README, 4 ADRs, protocol-notes, production-reflection |
| 9 | You can answer demo questions | See [demo-questions.md](demo-questions.md) |
| 10 | Report / video ready | See [report-outline.md](report-outline.md) |

## Deliverables checklist

### Repository

- [ ] Public or instructor-accessible Git repository URL recorded on the cover sheet
- [ ] `LICENSE` (MIT) present
- [ ] `CHANGELOG.md` reflects final release state
- [ ] `.gitignore` excludes `~/.apiclient.toml`, `.env`, `__pycache__/`
- [ ] Commit messages are readable (not one giant “final” commit only)

### Documentation (in repo)

- [ ] [README.md](../README.md) — install, demo server, CLI examples, exit codes, out of scope
- [ ] [architecture.md](architecture.md) — layers + request lifecycle
- [ ] [protocol-notes.md](protocol-notes.md) — one request, partial reads, chunked vs CL
- [ ] [production-reflection.md](production-reflection.md) — why not production
- [ ] [protocol-mastery-checklist.md](protocol-mastery-checklist.md) — all boxes checked
- [ ] [demo-script.md](demo-script.md) — live presentation order
- [ ] [demo-questions.md](demo-questions.md) — oral exam prep
- [ ] [report-outline.md](report-outline.md) — written report skeleton
- [ ] [windows-testing.md](windows-testing.md) — if graders use PowerShell
- [ ] Four ADRs under `docs/adr/`

### Written report (if required by course)

- [ ] Export [report-outline.md](report-outline.md) to PDF with your prose filled in
- [ ] Include architecture diagram (from architecture.md or your own)
- [ ] Include test count and coverage summary (`pytest -q` output or CI screenshot)
- [ ] Explicit limitations section (do not claim production readiness)

### Live demo or video (8–15 minutes)

Follow [demo-script.md](demo-script.md). Narrate **layers**, not feature list:

1. Problem and goal (30 s)
2. WSGI contract on screen (1 min)
3. One full `--trace` raw request (3–4 min)
4. Auth + retries + pagination (2–3 min)
5. Transport swap + bench (1–2 min)
6. Production reflection (1–2 min)

## Rubric self-score (target Grade A)

### Networking / protocols — Excellent if

- [ ] Raw socket HTTP works against local WSGI
- [ ] HTTPS uses `ssl` correctly (demo step 4)
- [ ] Content-Length and chunked parsing demonstrated (tests + optional chunked server)
- [ ] Partial reads explained (protocol-notes)
- [ ] Trace shows timings and framing
- [ ] Parser safety limits named (header/body/chunk caps)
- [ ] You explain byte-level flow without reading slides verbatim

### Python design — Excellent if

- [ ] Typed dataclasses for core models
- [ ] Interfaces for transport, auth, pagination
- [ ] Specific exceptions and CLI exit codes
- [ ] Tests cover parsing, retry, redirect, auth edge cases
- [ ] Code readable; ADRs explain non-obvious choices

### System architecture — Excellent if

- [ ] Dependencies point downward (cli not imported by transport)
- [ ] Transport swap without CLI changes
- [ ] WSGI server as realistic local target
- [ ] ADRs at the right level of detail
- [ ] Stretch features do not break core story

### CLI quality — Excellent if

- [ ] Commands discoverable; `--help` on subcommands
- [ ] Clear errors and stable exit codes
- [ ] `--output pretty|raw|table` useful
- [ ] Secrets redacted in trace and `--curl`
- [ ] Trace teaches; not overwhelming on a simple GET

### Presentation — Excellent if

- [ ] Layer-by-layer story
- [ ] Explain CLI → TCP → HTTP → parser → response
- [ ] Explain production vs educational client
- [ ] Honest about out-of-scope items

## What not to add before submit

Do **not** expand scope to chase points:

- HTTP/2, cookie jars, multipart uploads, production proxy/TLS policy
- Django + HTMX (stretch only in original scope)
- Large refactors unrelated to demo or report

## Course metadata

Fill in on the report cover and optionally in README:

| Field | Value |
|-------|--------|
| Student name | Princeton Afeez |
| Course code | _fill in_ |
| Instructor | _fill in_ |
| Submission date | _fill in_ |
| Repository URL | _fill in after push_ |
