# Executive Writer

Python 3.13 FastAPI application, version 0.1.0, managed with uv.

## Setup

Install Python 3.13 and uv, then install project and development dependencies:

```sh
uv sync
```

## Run

```sh
uv run uvicorn executive_writer.main:app --reload
```

API documentation is available at http://127.0.0.1:8000/docs.
`GET /health` returns `{"status": "ok"}`. `POST /documents` accepts a required,
nonblank `objective` and a `document_type` of `memo`, `report`, or `briefing`.
Optional fields are `audience`, `context`, and `instructions`.

```sh
curl -X POST http://127.0.0.1:8000/documents \
  -H 'Content-Type: application/json' \
  -d '{"objective":"Summarize quarterly results","document_type":"memo"}'
```

The endpoint returns HTTP 202 with a generated `document_id`, `status: "accepted"`,
and the requested `document_type`. This is a placeholder: no document is generated,
queued, or persisted, and no LLM is called.

## Test and lint

```sh
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```
