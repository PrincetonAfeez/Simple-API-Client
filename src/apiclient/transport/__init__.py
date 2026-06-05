"""Transport backends behind a single :class:`Transport` interface.

Two interchangeable backends are provided:

* :class:`RawSocketTransport` opens a TCP (and optionally TLS) socket, hand-
  builds the HTTP/1.1 request bytes, and parses the response with the
  in-tree parser. Optional :class:`ConnectionPool` enables keep-alive reuse.
* :class:`UrllibTransport` defers to :mod:`urllib.request`, demonstrating the
  same contract over a mature stdlib backend.

The :class:`ApiClient` layer above is transport-agnostic; the swap point is the
:class:`Transport` ABC.
"""

from .base import Transport
from .pool import ConnectionPool
from .socket_transport import RawSocketTransport
from .urllib_transport import UrllibTransport

__all__ = ["ConnectionPool", "RawSocketTransport", "Transport", "UrllibTransport"]
