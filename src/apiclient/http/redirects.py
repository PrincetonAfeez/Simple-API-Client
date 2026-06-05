"""Redirect policy and request rewriting."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from apiclient.auth.base import AuthStrategy
from apiclient.exceptions import RedirectError
from apiclient.http.url import resolve_redirect_url
from apiclient.models import RedirectRecord, Request, Response
from apiclient.observability.redaction import sensitive_query_param_names

_DEFAULT_ALLOWED_REDIRECTS: frozenset[int] = frozenset({301, 302, 303, 307, 308})
_DEFAULT_AUTH_HEADERS = frozenset(
    {"authorization", "proxy-authorization", "x-api-key", "api-key"}
)


@dataclass(frozen=True, slots=True)
class RedirectPolicy:
    max_hops: int = 5
    allowed_statuses: frozenset[int] = field(default_factory=lambda: _DEFAULT_ALLOWED_REDIRECTS)
    preserve_auth_across_hosts: bool = False
    rewrite_post_to_get: bool = True

    def is_redirect(self, response: Response) -> bool:
        return response.status_code in self.allowed_statuses and "Location" in response.headers

    def next_request(
        self,
        request: Request,
        response: Response,
        *,
        auth: AuthStrategy | None = None,
    ) -> tuple[Request, RedirectRecord]:
        location = response.headers.get("Location")
        if not location:
            raise RedirectError("Redirect response did not include a Location header")

        next_url = resolve_redirect_url(request.url, location)
        next_method = request.method
        next_body = request.body
        headers = request.headers.copy()

        if self.rewrite_post_to_get and _should_rewrite_to_get(request.method, response.status_code):
            next_method = "GET"
            next_body = b""
            headers.pop("Content-Type", None)
            headers.pop("Content-Length", None)

        if not self.preserve_auth_across_hosts and _host_changed(request.url, next_url):
            header_names = _auth_sensitive_headers(auth)
            for name in list(headers.keys()):
                if name.lower() in header_names:
                    headers.pop(name, None)
            next_url = _strip_sensitive_query_params(next_url, _auth_sensitive_query_params(auth))

        record = RedirectRecord(
            url=request.url,
            status_code=response.status_code,
            location=next_url,
            method=request.method,
        )
        return request.copy_with(method=next_method, url=next_url, headers=headers, body=next_body), record


def _auth_sensitive_headers(auth: AuthStrategy | None) -> frozenset[str]:
    names = set(_DEFAULT_AUTH_HEADERS)
    if auth is not None:
        names.update(auth.sensitive_header_names())
    return frozenset(names)


def _auth_sensitive_query_params(auth: AuthStrategy | None) -> frozenset[str]:
    names = set(sensitive_query_param_names())
    if auth is not None:
        names.update(auth.sensitive_query_params())
    return frozenset(names)


def _strip_sensitive_query_params(url: str, param_names: frozenset[str]) -> str:
    if not param_names:
        return url
    split = urlsplit(url)
    if not split.query:
        return url
    filtered = [
        (key, value)
        for key, value in parse_qsl(split.query, keep_blank_values=True)
        if key.lower() not in param_names
    ]
    return urlunsplit(
        (split.scheme, split.netloc, split.path, urlencode(filtered), split.fragment)
    )


def _should_rewrite_to_get(method: str, status_code: int) -> bool:
    if status_code == 303 and method.upper() not in {"GET", "HEAD"}:
        return True
    return status_code in {301, 302} and method.upper() == "POST"


def _host_changed(old_url: str, new_url: str) -> bool:
    old = urlsplit(old_url)
    new = urlsplit(new_url)
    return (old.scheme, old.hostname, old.port) != (new.scheme, new.hostname, new.port)
