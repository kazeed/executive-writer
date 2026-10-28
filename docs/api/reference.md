# API reference

Sources: [application registration](../../src/executive_writer/main.py),
[document route](../../src/executive_writer/api/documents.py),
[models](../../src/executive_writer/models/documents.py) and
[API tests](../../tests/test_api.py).

## Routes

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/health` | HTTP 200 JSON `{"status":"ok"}`; static liveness response |
| POST | `/documents` | HTTP 202 acceptance placeholder; validation failures return 422 |
| GET | `/openapi.json` | Framework-generated OpenAPI schema |
| GET | `/docs` | Framework-provided Swagger UI |
| GET | `/docs/oauth2-redirect` | Swagger UI OAuth redirect helper; does not establish application authentication |
| GET | `/redoc` | Framework-provided ReDoc UI |

Documentation routes are enabled by FastAPI defaults. Browser UI assets may require external
access; their availability is not established by the application API tests.

## POST /documents

Send a JSON object with these fields:

| Field | Type | Required/default | Validation |
| --- | --- | --- | --- |
| `objective` | string | Required | Must contain a non-whitespace character; surrounding whitespace is preserved |
| `document_type` | string | Required | Exactly `memo`, `report` or `briefing` |
| `audience` | string or null | Defaults to null | No additional application validator |
| `context` | string or null | Defaults to null | No additional application validator |
| `instructions` | string or null | Defaults to null | No additional application validator |

There are no application-defined text length or request-body size limits. Models use Pydantic's
default extra-field handling: unknown fields are ignored. Supplying a future field such as
`research_enabled` does not enable research or enforce a permission.

Example request:

```json
{"objective":"Summarize quarterly results","document_type":"memo"}
```

Example HTTP 202 response (UUID varies):

```json
{"document_id":"ad7e25ad-6082-4de1-903b-94e6ab25e2fd","status":"accepted","document_type":"memo"}
```

`document_id` is a newly generated UUID v4 serialized as a string; `status` is always `accepted`;
`document_type` echoes the validated type. There is no generated document, queue, persistence,
status lookup or retrieval endpoint.

## Errors and verification limits

FastAPI returns its default validation error envelope with a `detail` list. Tests verify HTTP 422
and the first error's `loc` for missing/empty/whitespace objective and missing/unsupported document
type. They do not establish every malformed-input behavior or safe redaction of submitted values.
No custom exception handler or application error schema is configured. Do not rely on validation
responses being free of submitted content.
