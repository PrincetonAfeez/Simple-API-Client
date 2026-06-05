"""Observability helpers used by trace and curl output.

* ``timing`` — small helpers for rendering monotonic durations.
* ``redaction`` — strips bearer tokens, basic credentials, API keys, and
  sensitive query parameters from headers and URLs before display.

The redaction module is shared by the raw transport's trace output, the
urllib transport's trace output, and the CLI's ``--curl`` exporter so the
same redaction policy applies everywhere a secret could leak.
"""
