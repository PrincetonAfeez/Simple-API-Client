"""Simple API Client — educational HTTP/1.1 client built on raw sockets.

The package exposes a small public surface:

* :class:`ApiClient` — high-level synchronous client with retries, redirects,
  authentication, and pagination. Transport-agnostic.
* :class:`Request` / :class:`Response` — dataclass models passed between the
  client and any :class:`~apiclient.transport.base.Transport`.

The codebase is layered downward:

    cli → client → http (parser, url, encode, redirects)
                    └→ transport (raw socket or urllib backend)
                    └→ resilience, auth, pagination, observability

Each subpackage exposes its public objects via its own ``__init__``. Nothing in
``http`` or ``transport`` imports from ``cli``; the dependency graph runs in one
direction only.
"""

from .auth import (
    ApiKeyHeaderAuth,
    ApiKeyQueryAuth,
    BasicAuth,
    BearerTokenAuth,
)
from .client import ApiClient
from .concurrency import BatchResult, fetch_many
from .exceptions import (
    ApiClientError,
    AuthError,
    ConfigError,
    ConnectionFailure,
    HttpStatusError,
    InvalidUrlError,
    PaginationError,
    ProtocolError,
    RedirectError,
    RequestTimeout,
    RetryExhausted,
    TransportError,
)
from .models import Request, Response

__all__ = [
    "ApiClient",
    "ApiKeyHeaderAuth",
    "ApiKeyQueryAuth",
    "AuthError",
    "ApiClientError",
    "BasicAuth",
    "BatchResult",
    "BearerTokenAuth",
    "ConfigError",
    "ConnectionFailure",
    "HttpStatusError",
    "InvalidUrlError",
    "PaginationError",
    "ProtocolError",
    "RedirectError",
    "Request",
    "RequestTimeout",
    "Response",
    "RetryExhausted",
    "TransportError",
    "fetch_many",
]
