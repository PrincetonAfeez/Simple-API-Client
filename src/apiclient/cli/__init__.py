"""Command-line interface package.

Entry point :func:`apiclient.cli.main.main` is exposed as the ``apiclient``
console script by ``pyproject.toml``. Argument parsing lives in
:func:`build_parser`; output formatting (``pretty`` / ``raw`` / ``table``) and
the ``--curl`` exporter live in :mod:`apiclient.cli.output`.
"""
