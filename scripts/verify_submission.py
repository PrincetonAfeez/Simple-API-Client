#!/usr/bin/env python3
"""Pre-submission verification for the Simple API Client capstone.

Run from the repository root:

    python scripts/verify_submission.py

Exits 0 when all checks pass; non-zero on first failure.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(label: str, cmd: list[str]) -> None:
    print(f"\n==> {label}")
    print("    ", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    if result.returncode != 0:
        print(f"\nFAILED: {label} (exit {result.returncode})")
        sys.exit(result.returncode)
    print(f"OK: {label}")


def main() -> int:
    py = sys.executable
    print(f"Repository: {ROOT}")
    print(f"Python: {py}")

    run("byte-compile", [py, "-m", "compileall", "-q", "src", "server", "tests"])

    try:
        import pytest  # noqa: F401
    except ImportError:
        print("\npytest not installed; run: python -m pip install -e \".[dev]\"")
        return 1

    run("pytest", [py, "-m", "pytest", "-q"])

    try:
        import ruff  # noqa: F401
    except ImportError:
        print("\nWARNING: ruff not installed; skipping lint")
    else:
        run("ruff", [py, "-m", "ruff", "check", "src", "tests", "server"])

    run("apiclient --version", [py, "-m", "apiclient", "--version"])

    required_docs = [
        "README.md",
        "docs/architecture.md",
        "docs/protocol-notes.md",
        "docs/production-reflection.md",
        "docs/demo-script.md",
        "docs/demo-questions.md",
        "docs/SUBMISSION.md",
        "docs/adr/0001-raw-sockets-vs-library.md",
        "docs/adr/0002-sync-core-async-layer.md",
        "docs/adr/0003-toml-config-and-profiles.md",
        "docs/adr/0004-wsgi-as-local-server-contract.md",
        "LICENSE",
    ]
    print("\n==> required documentation files")
    missing = [p for p in required_docs if not (ROOT / p).exists()]
    if missing:
        for p in missing:
            print(f"MISSING: {p}")
        return 1
    print(f"OK: all {len(required_docs)} paths present")

    print("\nAll submission checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
