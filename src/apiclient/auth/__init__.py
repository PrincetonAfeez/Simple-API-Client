"""Authentication strategies behind a single :class:`AuthStrategy` interface.

Strategies are immutable dataclasses with two required methods:

* :meth:`AuthStrategy.apply` returns a new :class:`Request` with the credential
  attached. Strategies do not mutate the input request.
* :meth:`AuthStrategy.secrets` lists the raw credential values so the trace
  / curl output layers can redact them before display.

Available strategies:

* :class:`BearerTokenAuth` — adds ``Authorization: Bearer <token>``.
* :class:`BasicAuth` — RFC 7617 base64 of ``username:password``.
* :class:`ApiKeyHeaderAuth` — arbitrary header name / value pair.
* :class:`ApiKeyQueryAuth` — adds the key as a URL query parameter.
"""

from .apikey import ApiKeyHeaderAuth, ApiKeyQueryAuth
from .base import AuthStrategy
from .basic import BasicAuth
from .bearer import BearerTokenAuth

__all__ = [
    "ApiKeyHeaderAuth",
    "ApiKeyQueryAuth",
    "AuthStrategy",
    "BasicAuth",
    "BearerTokenAuth",
]
