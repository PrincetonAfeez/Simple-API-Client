"""Connection pool unit tests."""

from __future__ import annotations

import socket
import ssl
import unittest
from unittest.mock import MagicMock, patch

from apiclient.transport.pool import ConnectionPool, _looks_alive, _safe_close


class ConnectionPoolTests(unittest.TestCase):
    def test_invalid_max_per_host(self) -> None:
        with self.assertRaises(ValueError):
            ConnectionPool(max_per_host=0)

    def test_invalid_max_idle_seconds(self) -> None:
        with self.assertRaises(ValueError):
            ConnectionPool(max_idle_seconds=0)

    def test_acquire_returns_none_when_empty(self) -> None:
        pool = ConnectionPool()
        self.assertIsNone(pool.acquire("http", "127.0.0.1", 80))

    def test_release_and_acquire_round_trip(self) -> None:
        pool = ConnectionPool(max_per_host=2)
        sock = MagicMock(spec=socket.socket)
        with patch("apiclient.transport.pool._looks_alive", return_value=True):
            pool.release("http", "127.0.0.1", 80, sock)
            got = pool.acquire("http", "127.0.0.1", 80)
        self.assertIs(got, sock)

    def test_acquire_skips_expired_entry(self) -> None:
        import time

        pool = ConnectionPool(max_idle_seconds=0.001)
        sock = MagicMock(spec=socket.socket)
        with patch("apiclient.transport.pool._looks_alive", return_value=True):
            pool.release("http", "127.0.0.1", 80, sock)
            time.sleep(0.005)
            self.assertIsNone(pool.acquire("http", "127.0.0.1", 80))
        sock.close.assert_called()

    def test_acquire_skips_dead_socket(self) -> None:
        pool = ConnectionPool()
        sock = MagicMock(spec=socket.socket)
        pool.release("http", "127.0.0.1", 80, sock)
        with patch("apiclient.transport.pool._looks_alive", return_value=False):
            self.assertIsNone(pool.acquire("http", "127.0.0.1", 80))

    def test_release_evicts_oldest_when_at_capacity(self) -> None:
        pool = ConnectionPool(max_per_host=1)
        first = MagicMock(spec=socket.socket)
        second = MagicMock(spec=socket.socket)
        with patch("apiclient.transport.pool._looks_alive", return_value=True):
            pool.release("http", "127.0.0.1", 80, first)
            pool.release("http", "127.0.0.1", 80, second)
            got = pool.acquire("http", "127.0.0.1", 80)
        self.assertIs(got, second)
        first.close.assert_called()

    def test_close_drains_all_buckets(self) -> None:
        pool = ConnectionPool()
        sock = MagicMock(spec=socket.socket)
        pool.release("http", "127.0.0.1", 80, sock)
        pool.close()
        self.assertIsNone(pool.acquire("http", "127.0.0.1", 80))


class LooksAliveTests(unittest.TestCase):
    def test_blocking_io_error_means_alive(self) -> None:
        sock = MagicMock(spec=socket.socket)
        sock.setblocking = MagicMock()
        sock.recv = MagicMock(side_effect=BlockingIOError)
        self.assertTrue(_looks_alive(sock))

    def test_ssl_want_read_means_alive(self) -> None:
        sock = MagicMock(spec=socket.socket)
        sock.setblocking = MagicMock()
        sock.recv = MagicMock(side_effect=ssl.SSLWantReadError)
        self.assertTrue(_looks_alive(sock))

    def test_oserror_means_not_alive(self) -> None:
        sock = MagicMock(spec=socket.socket)
        sock.setblocking = MagicMock(side_effect=OSError("broken"))
        self.assertFalse(_looks_alive(sock))

    def test_pending_bytes_means_not_alive(self) -> None:
        sock = MagicMock(spec=socket.socket)
        sock.setblocking = MagicMock()
        sock.recv = MagicMock(return_value=b"x")
        self.assertFalse(_looks_alive(sock))

    def test_setblocking_restore_oserror_swallowed(self) -> None:
        sock = MagicMock(spec=socket.socket)
        sock.setblocking = MagicMock(side_effect=[None, OSError("restore failed")])
        sock.recv = MagicMock(side_effect=BlockingIOError)
        self.assertTrue(_looks_alive(sock))

    def test_safe_close_swallows_oserror(self) -> None:
        sock = MagicMock(spec=socket.socket)
        sock.close.side_effect = OSError("already closed")
        _safe_close(sock)


if __name__ == "__main__":
    unittest.main()
