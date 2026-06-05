"""Request body encoding helpers."""

from __future__ import annotations

import json as json_module
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import urlencode

from apiclient.models import CaseInsensitiveHeaders


def encode_body(
    *,
    json_value: object | None = None,
    form: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
    data: str | bytes | None = None,
    binary_file: str | None = None,
    headers: CaseInsensitiveHeaders | None = None,
) -> tuple[bytes, CaseInsensitiveHeaders]:
    headers = headers.copy() if headers else CaseInsensitiveHeaders()
    supplied = [json_value is not None, form is not None, data is not None, binary_file is not None]
    if sum(supplied) > 1:
        raise ValueError("Only one request body source can be used at a time")

    body = b""
    if json_value is not None:
        body = json_module.dumps(json_value, separators=(",", ":")).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    elif form is not None:
        body = urlencode(form, doseq=True).encode("utf-8")
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif data is not None:
        body = data if isinstance(data, bytes) else data.encode("utf-8")
        headers.setdefault("Content-Type", "text/plain; charset=utf-8")
    elif binary_file is not None:
        try:
            body = Path(binary_file).read_bytes()
        except OSError as exc:
            raise ValueError(f"Could not read binary file {binary_file!r}: {exc}") from exc
        headers.setdefault("Content-Type", "application/octet-stream")

    # Content-Length is set by the transport when the request is serialized.
    return body, headers
