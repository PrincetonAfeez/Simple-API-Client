# Schema

Simple schema pack for the **Simple API Client** demo WSGI server.

This folder documents the JSON shapes exposed by `server/endpoints.py` and gives
the project a lightweight contract layer that can be referenced from docs,
tests, client examples, or future validation work.

## Files

- `openapi.yaml` — small OpenAPI 3.1 contract for the demo API.
- `json/*.schema.json` — standalone JSON Schema files for common response bodies.

## Demo endpoints covered

- `GET /health`
- `GET /private`
- `GET /items`
- `GET /items/{id}`
- `GET /flaky`
- `GET /redirect`
- `POST /echo`
- `GET /reset-flaky`

## Notes

The demo server uses hard-coded credentials for learning only:

- Bearer token: `demo-token`
- Basic auth: `demo:secret`
- API key: `demo-key`

These schemas are intentionally simple and educational. They describe the local
capstone API; they are not meant to imply that the demo server is production-ready.
