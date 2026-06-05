"""Test fixtures that spin up local HTTP servers in background threads.

Two server fixtures are exposed:

* :func:`wsgi_server` — runs the project's WSGI app via :mod:`wsgiref` for
  integration tests of the high-level CLI / client against ``/health``,
  ``/items``, ``/private``, ``/flaky``, ``/redirect``, ``/echo``.
* :func:`chunked_server` — runs the hand-rolled raw socket server because
  ``wsgiref`` is HTTP/1.0-only and cannot produce ``Transfer-Encoding:
  chunked`` responses; the parser's chunked path is tested against this fixture.

Both yield a base URL (``http://host:port``) and tear the server down cleanly
on context exit, including a bounded ``thread.join``.
"""

from __future__ import annotations

import socketserver
from contextlib import contextmanager
from threading import Thread
from wsgiref.simple_server import WSGIRequestHandler, make_server

from server.chunked_test_server import ChunkedHandler
from server.wsgi_app import application


class QuietWSGIRequestHandler(WSGIRequestHandler):
    def log_message(self, format, *args):  # noqa: A002, ANN001
        return


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


@contextmanager
def wsgi_server():
    server = make_server("127.0.0.1", 0, application, handler_class=QuietWSGIRequestHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@contextmanager
def chunked_server():
    server = ReusableTCPServer(("127.0.0.1", 0), ChunkedHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
