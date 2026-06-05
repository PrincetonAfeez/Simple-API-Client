"""Idle connection pool keyed on (scheme, host, port).

Educational only. Sockets returned to the pool are reused for one more request
provided the previous response did not ask the server to close, and the socket
still answers a zero-byte peek without bytes pending. The pool has a bounded
capacity per key and an idle-time cap; expired or rejected sockets are closed.

Thread safety: ``acquire``, ``release``, and ``close`` are guarded by a lock and
may be called from worker threads (e.g. ``fetch_many``). Use one pool per
``ApiClient``; do not share a pool across unrelated processes.
"""

from __future__ import annotations

import socket
import ssl
import threading
from collections import deque
from dataclasses import dataclass
from time import monotonic


@dataclass(slots=True)
class _Entry:
    sock: socket.socket | ssl.SSLSocket
    returned_at: float


class ConnectionPool:
    def __init__(
        self,
        *,
        max_per_host: int = 4,
        max_idle_seconds: float = 30.0,
    ) -> None:
        if max_per_host < 1:
            raise ValueError(
                f"max_per_host must be >= 1, got {max_per_host}"
            )
        if max_idle_seconds <= 0:
            raise ValueError(
                f"max_idle_seconds must be > 0, got {max_idle_seconds}"
            )
        self.max_per_host = max_per_host
        self.max_idle_seconds = max_idle_seconds
        self._lock = threading.Lock()
        self._idle: dict[tuple[str, str, int], deque[_Entry]] = {}

    def acquire(self, scheme: str, host: str, port: int) -> socket.socket | ssl.SSLSocket | None:
        key = (scheme, host, port)
        with self._lock:
            bucket = self._idle.get(key)
            if not bucket:
                return None
            while bucket:
                entry = bucket.popleft()
                if monotonic() - entry.returned_at > self.max_idle_seconds:
                    _safe_close(entry.sock)
                    continue
                if not _looks_alive(entry.sock):
                    _safe_close(entry.sock)
                    continue
                return entry.sock
            return None

    def release(
        self, scheme: str, host: str, port: int, sock: socket.socket | ssl.SSLSocket
    ) -> None:
        key = (scheme, host, port)
        with self._lock:
            bucket = self._idle.setdefault(key, deque())
            if len(bucket) >= self.max_per_host:
                evicted = bucket.popleft()
                _safe_close(evicted.sock)
            bucket.append(_Entry(sock=sock, returned_at=monotonic()))

    def close(self) -> None:
        with self._lock:
            for bucket in self._idle.values():
                while bucket:
                    _safe_close(bucket.popleft().sock)
            self._idle.clear()


def _looks_alive(sock: socket.socket | ssl.SSLSocket) -> bool:
    """Return True only if the socket is open AND has no pending bytes.

    Pending bytes on an idle pooled socket are always leftovers from a previous
    response — never the start of a new one — because the pool only hands a
    connection back after a clean read. If recv-peek returns data, the next
    request would misread those bytes as response headers, so the connection
    must be discarded.

    Any ``OSError`` (including from ``setblocking`` on a broken file descriptor)
    is treated as "not alive" so the caller can dispose of the socket cleanly
    instead of letting it leak.
    """

    try:
        try:
            sock.setblocking(False)
            sock.recv(1, socket.MSG_PEEK)
        except (BlockingIOError, ssl.SSLWantReadError):
            return True
        except OSError:
            return False
        # An empty peek means the peer closed; a non-empty peek means stale
        # bytes are queued. Either way the connection is unusable.
        return False
    finally:
        try:
            sock.setblocking(True)
        except OSError:
            pass


def _safe_close(sock: socket.socket | ssl.SSLSocket) -> None:
    try:
        sock.close()
    except OSError:
        pass
