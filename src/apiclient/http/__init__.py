"""Low-level HTTP utilities used by both transports.

* ``url`` — URL parsing, query-string composition, and redirect resolution.
* ``encode`` — request body encoding (JSON / form / raw / binary) plus
  ``Content-Type`` / ``Content-Length`` header policy.
* ``parser`` — HTTP/1.1 response parser supporting Content-Length, chunked
  transfer encoding, and connection-close framing.
* ``redirects`` — :class:`RedirectPolicy` deciding when to rewrite POST → GET
  and when to strip cross-host credentials.

All four modules are dependency-free with respect to the rest of the package,
so they can be tested in isolation.
"""
