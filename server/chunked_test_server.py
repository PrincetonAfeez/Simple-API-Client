"""Tiny raw-socket server that emits Transfer-Encoding: chunked responses."""

from __future__ import annotations

import argparse
import socketserver


class ChunkedHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        self.request.recv(4096)
        chunks = [b'{"message":"', b"hello from chunks", b'"}']
        head = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"Connection: close\r\n"
            b"\r\n"
        )
        self.request.sendall(head)
        for chunk in chunks:
            self.request.sendall(f"{len(chunk):X}\r\n".encode("ascii") + chunk + b"\r\n")
        self.request.sendall(b"0\r\n\r\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a tiny chunked HTTP test server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    with socketserver.TCPServer((args.host, args.port), ChunkedHandler) as server:
        print(f"Serving chunked responses at http://{args.host}:{args.port}")
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
