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

Additional strict typing, security scanning, and CI checks are planned. Do not interpret the current checks as proof of production readiness.

## Docker packaging and usage (planned)

**Docker/OCI is the selected packaging format, but no `Dockerfile` or `.dockerignore` is committed yet.** The commands below describe the intended interface **after** the container packaging milestone has been implemented and verified. They will not work against the current checkout.

### Build

From the repository root, after a Dockerfile has been added:

```bash
docker build -t executive-writer:local .
```

### Run locally

```bash
docker run --rm --name executive-writer \
  --publish 127.0.0.1:8000:8000 \
  executive-writer:local
```

Check the running container at http://127.0.0.1:8000/docs or:

```bash
curl http://127.0.0.1:8000/health
```

Stop it with `Ctrl+C` when running attached, or from another terminal:

```bash
docker stop executive-writer
```

### Container design requirements

When Docker support is implemented, the image must:

- Run the API on `0.0.0.0:8000` **inside** the container while the example above publishes only to the host's loopback interface.
- Use a minimal, supported Python runtime, a non-root user, and only necessary runtime dependencies.
- Use reproducible builds with `uv.lock`, a pinned base image strategy, and a `.dockerignore` excluding secrets, `.venv`, tests, Git metadata, and local caches as appropriate.
- Avoid baking secrets into images or storing sensitive documents in container layers.
- Include a working health-check strategy and support clean shutdown.
- Remain portable across OCI-compatible hosting providers, without committing to a particular cloud service.

**Security:** The `--publish 127.0.0.1:8000:8000` binding intentionally limits access to the local machine. Do not expose this initial API publicly until authentication, abuse controls, deployment protections, and the required security verification are implemented.

## Engineering and architecture

See the [technical documentation index](docs/README.md) for current architecture, API contracts, development checks, operational limitations, and recorded decisions.

The application is deliberately small at this stage. We will introduce model integrations, workflow orchestration, persistence, and operational infrastructure incrementally as requirements justify them.

Key design principles are explicit contracts, separation between application control and AI judgment, testability, least privilege, evidence provenance, and avoiding unnecessary frameworks or abstractions. See [`AGENTS.md`](AGENTS.md) for detailed engineering and security requirements.

## Project status and contribution

This is an early-stage personal/open-source engineering project. Interfaces and architecture may change as the first functional generation pipeline is developed. Issues and constructive feedback are welcome; treat the existing API as experimental until a stable contract is declared.
