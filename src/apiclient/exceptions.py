"""Project-specific exceptions with CLI-friendly meanings."""


class ApiClientError(Exception):
    """Base class for all expected client errors."""

    exit_code = 1


class InvalidUrlError(ApiClientError):
    """Raised when a URL cannot be parsed or has an unsupported scheme."""

    exit_code = 2


class TransportError(ApiClientError):
    """Raised when a transport cannot complete the request."""

    exit_code = 3


class ConnectionFailure(TransportError):
    """Raised for DNS, TCP, or TLS connection failures."""


class RequestTimeout(TransportError):
    """Raised when connect or read operations time out."""


class HttpStatusError(ApiClientError):
    """Raised when --fail is used and the response status is not successful."""

    exit_code = 4


class RetryExhausted(ApiClientError):
    """Raised after the final retry attempt fails."""

    exit_code = 5


class AuthError(ApiClientError):
    """Raised for authentication setup or authentication response failures."""

    exit_code = 6


class ProtocolError(ApiClientError):
    """Raised when HTTP bytes cannot be parsed safely."""

    exit_code = 7


class PaginationError(ApiClientError):
    """Raised when pagination metadata is missing or malformed."""

    exit_code = 8


class RedirectError(ApiClientError):
    """Raised when redirect handling cannot continue safely."""

    exit_code = 9


class ConfigError(ApiClientError):
    """Raised when configuration cannot be read or written."""

    exit_code = 10
