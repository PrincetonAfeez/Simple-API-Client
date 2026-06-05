# Testing on Windows (PowerShell)

The project is developed and CI-tested on Windows and Ubuntu. Use these steps
for local verification or grader reproduction.

## Prerequisites

- Python 3.11 or newer (3.12+ recommended; 3.14 supported in CI)
- PowerShell 5.1+ or PowerShell 7+

## Install

```powershell
cd "C:\path\to\Simple API Client"
python -m pip install -e ".[dev]"
```

## Run tests

```powershell
pytest -q
```

With coverage (same as CI):

```powershell
pytest -q --cov=apiclient --cov-report=term-missing
```

Unittest discovery (alternate runner):

```powershell
python -m compileall -q src server tests
$env:PYTHONPATH = "src"
python -c "import sys, unittest; r = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests')); sys.exit(0 if r.wasSuccessful() else 1)"
```

## Lint

```powershell
ruff check src tests server
```

## Submission verification script

```powershell
python scripts/verify_submission.py
```

## PowerShell URL quoting

`&` separates commands in PowerShell. Quote URLs with query strings:

```powershell
apiclient get 'http://127.0.0.1:8000/flaky?key=demo&succeed_after=2' --retries 2 --trace
```

## Demo server

In one terminal:

```powershell
python server/run_server.py --host 127.0.0.1 --port 8000
```

In another:

```powershell
apiclient get http://127.0.0.1:8000/health --transport raw --trace
```

## Common issues

| Symptom | Fix |
|---------|-----|
| `apiclient` not found | Re-run `pip install -e .` or use `python -m apiclient` |
| Port 8000 in use | `run_server.py --port 8001` and change URLs |
| Tests hang on network | Integration tests use `127.0.0.1`; check firewall |
| `pytest` not found | `pip install -e ".[dev]"` |

## Config file location

Default profile path: `%USERPROFILE%\.apiclient.toml`. Copy
[examples/apiclient.toml.example](examples/apiclient.toml.example) as a starting
point.
