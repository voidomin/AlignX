# Using the StructScope REST API from other tools

StructScope's backend is a FastAPI app, so it already exposes a full OpenAPI 3
schema at its stable defaults — no extra flags needed:

- Interactive docs: `http://localhost:8000/docs`
- Raw schema: `http://localhost:8000/openapi.json`

Every route is grouped under a tag (System, Structures, Jobs, Comparison,
Ligands & Interfaces, Annotations, History, Sequence, Reports, Discovery) —
useful both when browsing `/docs` and when a generated client organizes its
methods by tag.

## Generating a typed client

Rather than checking in generated client code (which would need
regenerating every time a route changes), generate one on demand with
[`openapi-python-client`](https://github.com/openapi-generators/openapi-python-client):

```bash
pip install openapi-python-client
openapi-python-client generate --url http://localhost:8000/openapi.json
```

This produces a standalone, importable Python package (named after the API
title) with one typed method per route, grouped into modules by tag. Point
`--url` at whatever host is actually running the backend (a deployed
instance, not just localhost) if you're generating against something other
than a local dev server.

If you only need a couple of endpoints and don't want a generated package at
all, `httpx` (already a StructScope dependency) works directly against any
documented route — see `scripts/structscope_cli.py` for a small, real
example (submit an alignment job, poll it, download the PDF report).

## Authentication

If the backend has `ALIGNX_API_KEY` set, every `/api/*` request needs an
`X-API-Key` header (or an `api_key` query parameter) with that value —
unauthenticated requests to `/api/*` get a 401. `/health` and the static
`/docs`/`/openapi.json` routes are never gated.

## Rate limits

Two job-submission routes are specifically rate-limited per client (by API
key if provided, otherwise by IP): `POST /api/jobs/align` and
`POST /api/jobs/discover`. Every other route, including the batch
`POST /api/screen` route, has no per-path submission limiter — `/api/screen`
instead caps how many targets a single request can carry
(`_MAX_SCREEN_TARGETS` server-side), since it's one request rather than N
job submissions.
