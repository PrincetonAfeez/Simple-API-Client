"""CLI formatting helpers."""

from __future__ import annotations

import json
import shlex
import sys

from apiclient.models import Request, Response
from apiclient.observability.redaction import redact_headers, redact_url


def print_response(response: Response, output: str = "pretty") -> None:
    if output == "raw":
        sys.stdout.buffer.write(response.body)
        if response.body and not response.body.endswith(b"\n"):
            sys.stdout.write("\n")
        return
    if output == "table":
        print_table_response(response)
        return
    print_pretty_response(response)


def print_pretty_response(response: Response) -> None:
    content_type = response.headers.get("Content-Type", "") or ""
    if "application/json" in content_type.lower():
        try:
            print(json.dumps(response.json(), indent=2, sort_keys=True))
            return
        except json.JSONDecodeError:
            pass
    print(response.text)


def print_table_response(response: Response) -> None:
    try:
        data = response.json()
    except json.JSONDecodeError:
        print(f"status\t{response.status_code}")
        print(f"body\t{response.text}")
        return
    rows = _rows_from_json(data)
    if not rows:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    headers = sorted({key for row in rows for key in row})
    widths = {key: max(len(key), *(len(str(row.get(key, ""))) for row in rows)) for key in headers}
    print("  ".join(key.ljust(widths[key]) for key in headers))
    print("  ".join("-" * widths[key] for key in headers))
    for row in rows:
        print("  ".join(str(row.get(key, "")).ljust(widths[key]) for key in headers))


def build_curl(request: Request) -> str:
    pieces = ["curl", "-i", "-X", request.method, shlex.quote(redact_url(request.url))]
    for key, value in redact_headers(request.headers).items():
        pieces.extend(["-H", shlex.quote(f"{key}: {value}")])
    if request.body:
        try:
            rendered = request.body.decode("utf-8")
        except UnicodeDecodeError:
            rendered = f"<{len(request.body)} binary bytes>"
        pieces.extend(["--data", shlex.quote(rendered)])
    return " ".join(pieces)


def _rows_from_json(data: object) -> list[dict]:
    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        return data
    if isinstance(data, dict):
        for key in ("results", "items", "data"):
            value = data.get(key)
            if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                return value
    return []
