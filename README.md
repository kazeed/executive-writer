# Executive Writer

**Executive Writer** is an open-source, Python-based AI research and writing application intended to turn an assignment into an evidence-grounded executive document.

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

These are **target capabilities**, not claims about the present implementation. See [`requirements.md`](docs/requirements.md) for the evolving requirements specification when that file is present in the repository, and [`AGENTS.md`](AGENTS.md) for Codex engineering instructions.

## Current state: v0.1.0

The repository currently provides a minimal, tested **FastAPI** foundation using Python 3.13, **uv**, **Pydantic**, **pytest**, and **Ruff**.

| Endpoint | Current behavior |
| --- | --- |
| `GET /health` | Returns HTTP 200 with `{"status":"ok"}`. |
| `POST /documents` | Validates a document request and returns HTTP 202 with a generated ID and `accepted` status. |
| `GET /docs` | Interactive Swagger/OpenAPI documentation. |

**Important:** `POST /documents` is currently a placeholder. It does not create, queue, persist, or return a document and makes no LLM calls. The returned ID is not yet a retrievable job identifier. There is no authentication or public-production hardening yet: run this version locally, not as an internet-facing service.

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

### Quality checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Internal M2B P2 in-memory orchestration is implemented with synthetic components.
The public API remains unchanged. Durable execution is P3; review-driven routing is P4.
See the [P2 scope, revised roadmap and verification record](docs/architecture/milestone-2b-p2.md).
Strict typing passes locally; full HTTP tests, coverage and security verification have recorded limitations. See the [development guide](docs/development/guide.md) and [Milestone 2A verification record](docs/operations/milestone-2a.md).

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

The application is deliberately small at this stage. We will introduce real model integrations, durable execution, review-driven routing, and operational infrastructure incrementally under the revised roadmap.

Key design principles are explicit contracts, separation between application control and AI judgment, testability, least privilege, evidence provenance, and avoiding unnecessary frameworks or abstractions. See [`AGENTS.md`](AGENTS.md) for detailed engineering and security requirements.

## Project status and contribution

This is an early-stage personal/open-source engineering project. Interfaces and architecture may change as the first functional generation pipeline is developed. Issues and constructive feedback are welcome; treat the existing API as experimental until a stable contract is declared.
