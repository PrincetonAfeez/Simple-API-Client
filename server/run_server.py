"""Run the local raw WSGI server."""

from __future__ import annotations

import argparse
from wsgiref.simple_server import make_server

try:
    from .wsgi_app import application
except ImportError:  # pragma: no cover - script execution
    from wsgi_app import application


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Simple API Client WSGI demo server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    with make_server(args.host, args.port, application) as server:
        print(f"Serving raw WSGI app at http://{args.host}:{args.port}")
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
