# Executive Writer

[![CI](https://github.com/kazeed/executive-writer/actions/workflows/ci.yml/badge.svg)](https://github.com/kazeed/executive-writer/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.13-blue)
![Coverage](https://img.shields.io/badge/coverage-99.17%25-brightgreen)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Executive Writer** is a Python-based AI research and writing project intended to turn an assignment into an evidence-grounded executive document.

Rather than treating document creation as a single prompt-to-text operation, the project aims to use an inspectable workflow: understand the assignment, plan the research, gather and assess evidence, structure an argument, draft, critically review, and deliver a finished document.

The intended audience includes engineering leaders, architects, product and business decision-makers, and others preparing decision-oriented papers. The project is under active development; **it is not yet a functioning AI writer**.

## Vision and planned capabilities

Executive Writer is being designed to:

- Produce executive briefings, reports, proposals, decision papers, and technical RFCs.
- Adapt depth, language, and presentation to the audience and purpose.
- Accept objectives, context, constraints, instructions, and supporting sources.
- Research external sources when explicitly authorized, retaining evidence provenance.
- Compare alternatives, surface assumptions and uncertainties, and explain trade-offs.
- Preserve intermediate outputs for review, evaluation, and eventually resumable execution.
- Apply an editorial quality check for clarity, concision, completeness, and factual support.
- Enforce model/tool budgets and security boundaries in application code rather than prompts alone.

The planned workflow is:

```text
Assignment -> Research plan -> Evidence -> Analysis and outline
           -> Draft -> Critical review -> Final document
```

These are **target capabilities**, not claims about the present implementation. See the [product requirements](docs/requirements.md) for the evolving requirements specification, and [`AGENTS.md`](AGENTS.md) for Codex engineering instructions.

## Current state: v0.1.0

The repository provides a **FastAPI** API foundation and an internal, in-memory workflow
engine (Milestone 2B P1/P2). The stack uses Python 3.13, **uv**, **Pydantic v2**,
**pytest**, **Ruff**, and strict **Pyright** checks. The package version remains `0.1.0`.

### Internal workflow engine

The [workflow package](src/executive_writer/workflow/) implements:

- Typed, immutable assignment, plan, evidence, draft, review, and execution contracts.
- Plan validation against trusted permissions, stage ordering, dependencies, and resource ceilings.
- Sequential async orchestration with optional research, analysis, and outline stages, followed by drafting and review.
- Bounded planning corrections and transient retries, reported model-call/token accounting, deadlines, and cooperative cancellation.
- Execution-local, append-only artifacts with provenance, versions, attempt records, and lifecycle history.
- Mechanical completion checks for draft content, word limits, required headings, and citation evidence IDs.

[Injected stage interfaces](src/executive_writer/workflow/components.py) and
[synthetic components](src/executive_writer/workflow/fakes.py) support offline execution and tests.
There are no real model providers or external retrieval integrations. Evidence-ID checks do
not verify facts or citation support. Artifacts are lost when the process exits, and the
engine is not connected to the HTTP API.

### HTTP API

| Endpoint | Current behavior |
| --- | --- |
| `GET /health` | Returns HTTP 200 with `{"status":"ok"}`. |
| `POST /documents` | Validates a document request and returns HTTP 202 with a generated ID and `accepted` status. |
| `GET /docs`, `GET /redoc` | Interactive API documentation, enabled by default. |
| `GET /openapi.json` | Generated OpenAPI schema, enabled by default. |

**Important:** `POST /documents` is currently a placeholder. It does not create, queue, persist, or return a document and makes no LLM calls. The returned ID is not yet a retrievable job identifier. Run this version locally: authentication, authorization, API request-size limits, and rate limiting are not implemented. Safe error responses and basic security/cache headers are implemented; they do not establish public-production readiness.

## Local development

### Prerequisites

- Python 3.13 (uv can install/manage it).
- [uv](https://docs.astral.sh/uv/).
- Git.

From the repository root:

```bash
uv python install 3.13
uv sync --locked
```

Start the development API:

```bash
uv run uvicorn executive_writer.main:app --reload
```

Open http://127.0.0.1:8000/docs, or test directly:

```bash
curl http://127.0.0.1:8000/health

curl --fail-with-body -X POST http://127.0.0.1:8000/documents \
  -H 'Content-Type: application/json' \
  -d '{
    "objective": "Assess the adoption of AI in software engineering teams",
    "document_type": "briefing",
    "audience": "Engineering leadership",
    "context": "Focus on productivity, quality, and operational risks",
    "instructions": "Write concisely for decision-makers"
  }'
```

The document request currently accepts `objective` (required and nonblank), `document_type` (`memo`, `report`, or `briefing`), and optional `audience`, `context`, and `instructions`.

### Configuration

Settings are read from environment variables; `.env` files are not loaded automatically.

| Variable | Default | Meaning |
| --- | --- | --- |
| `EW_ENVIRONMENT` | `development` | Accepts `development` or `production`; the label alone enables no additional protections. |
| `EW_DOCS_ENABLED` | `true` | Set to `false` to disable Swagger, ReDoc, and OpenAPI routes. |

### Quality checks

```bash
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
uv run pytest -q --cov --cov-report=term-missing
```

Local verification on 2026-10-29 passed: Ruff lint and formatting, strict Pyright,
lockfile verification, and **151 tests with 99.17% statement coverage** (90% required).
The suite emits one dependency deprecation warning about FastAPI/Starlette TestClient's
use of httpx. Tests require no live provider credentials or internet access.

[GitHub Actions](.github/workflows/ci.yml) configures quality, coverage, dependency audit,
static analysis, secret scanning, and container build/smoke/vulnerability jobs. Those
security/container jobs and GitHub-hosted CI were not rerun for this README update.
Older documentation records TestClient/coverage blockers; the local results above
supersede those historical blockers for this checkout.

See the [development guide](docs/development/guide.md) for additional checks and the
[P2 implementation record](docs/architecture/milestone-2b-p2.md) for workflow details.

## Docker packaging and usage

A multi-stage Dockerfile installs locked production dependencies into a non-root Python 3.13
runtime. Build and execution remain unverified in the implementation sandbox:

```bash
docker build -t executive-writer:local .
docker run --rm --name executive-writer --read-only --cap-drop=ALL \
  --security-opt=no-new-privileges --pids-limit=64 --memory=256m --cpus=1 \
  -p 127.0.0.1:8000:8000 executive-writer:local
```

Visit http://127.0.0.1:8000/docs or query `/health`. Stop with `docker stop --time 15 executive-writer`.
Run `bash scripts/container-smoke.sh` for automated checks. Keep host exposure on loopback.
See [runtime settings, scans and deployment prerequisites](docs/operations/status.md).
Version pins still require immutable digest resolution before release. No hosting provider or
public deployment is selected; this milestone does not establish public-production readiness.

## Engineering and architecture

See the [technical documentation index](docs/README.md) for current architecture, API contracts, development checks, operational limitations, and recorded decisions.

The revised roadmap defers durable execution to P3, review-driven revision and research
re-entry to P4, and final milestone verification to P5. Real model integrations and external
research remain future work. See the [roadmap and open decisions](docs/architecture/milestone-2b-p2.md#approved-roadmap-clarification).

Key design principles are explicit contracts, separation between application control and AI judgment, testability, least privilege, evidence provenance, and avoiding unnecessary frameworks or abstractions. See [`AGENTS.md`](AGENTS.md) for detailed engineering and security requirements.

## License

Executive Writer is licensed under the [Apache License, Version 2.0](LICENSE). You may use, modify, and distribute it, including commercially, under the license terms. Copyright and attribution notices must be preserved as required by the license.

## Project status and contribution

This is an early-stage personal/open-source engineering project. Interfaces and architecture may change as the first functional generation pipeline is developed. Issues and constructive feedback are welcome; treat the existing API as experimental until a stable contract is declared.
