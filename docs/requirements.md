# Executive Writer — Product Requirements

**Document version:** 0.1.0  
**Project:** [kazeed/executive-writer](https://github.com/kazeed/executive-writer)  
**Status:** Working requirements baseline; architecture and later milestones remain subject to design review  
**Last updated:** 2026-10-28

## 1. Purpose and vision

Executive Writer is a Python-based AI-assisted research and executive-writing application. It accepts a writing assignment, understands the goal and intended readers, investigates relevant evidence where permitted, analyzes alternatives and trade-offs, and produces a critically reviewed document.

The target experience is **objective → plan → evidence → analysis/outline → draft → review → final document**, rather than a single prompt-to-text completion.

The system should produce decision-useful executive papers and technical documents with explicit uncertainty, traceable sources, appropriate abstraction, and concise recommendations.

### Core principles

1. **Evidence before assertion:** distinguish documented facts, assumptions, model inferences, and recommendations.
2. **Audience-aware writing:** emphasize information, risk, alternatives, and decisions relevant to the reader.
3. **Inspectable execution:** stage outputs should eventually be available for debugging, evaluation, and review.
4. **Controlled autonomy:** the Python application owns validation, execution flow, tool permissions, retries, errors, and persistence; models perform interpretation, planning, analysis, synthesis, drafting, and editorial judgment within those controls.
5. **Incremental engineering:** start with direct LLM API integration and small typed modules; avoid frameworks and infrastructure until justified by requirements.
6. **Human review remains possible:** never imply that model-produced claims have been independently verified unless evidence supports that statement.

## 2. Intended use cases

Initial and target document types include:

- Executive briefings and decision memos
- Executive or strategic reports
- Business/technical proposals
- Technical RFCs and architecture decision papers

Examples include assessing an architectural migration, evaluating investment or delivery alternatives, writing a leadership briefing, or recommending an engineering strategy.

## 3. Functional requirements

The priority labels describe product intent, **not a mandate to implement everything in the next Codex task**.

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| FR-01 | Provide a REST API to submit document-generation requests. | Must | FastAPI. Initial stub already exists. |
| FR-02 | Support several document types. | Must | Current scaffold: `memo`, `report`, `briefing`; extend to proposals/RFCs in a subsequent contract revision. |
| FR-03 | Accept an intended audience and tailor the document to it. | Must | Business executives, engineering leadership, or technical reviewers. |
| FR-04 | Accept an objective, context, instructions, constraints, and supporting materials. | Must | Use structured fields alongside free-form narrative. |
| FR-05 | Allow research to be explicitly permitted or disabled per request. | Must | No external retrieval when disabled. |
| FR-06 | Investigate user-provided sources and, if authorized, external sources. | Must | Retrieval tools and source formats TBD. |
| FR-07 | Produce a research or investigation plan before retrieving evidence when research is enabled. | Must | Identify questions, unknowns, and candidate sources. |
| FR-08 | Preserve provenance for evidence and cited claims. | Must | Record source IDs/URLs or supplied-document references; never fabricate citations. |
| FR-09 | Evaluate uncertainties, assumptions, competing options, and trade-offs. | Must | Separate observations from conclusions. |
| FR-10 | Produce a structured outline before generating the full draft. | Must | Allow audience and document type to guide organization. |
| FR-11 | Generate readable, coherent, executive-quality content. | Must | Clearly present findings, implications, risks, and actions. |
| FR-12 | Critically review generated work for completeness, clarity, audience fit, and factual grounding. | Must | Review should be an explicit stage with actionable feedback. |
| FR-13 | Accept tone and output-format preferences. | Must | Markdown is the first sensible output; other formats are later decisions. |
| FR-14 | Make intermediate artifacts and execution status inspectable. | Target | Research plan, evidence set, outline, draft, review, final. |
| FR-15 | Support repeatable quality evaluations and comparisons of model/prompt configurations. | Future | Build evaluation criteria and representative test cases. |

### Request design

The public API should combine **structured behavioral controls** (document type, audience, research permission, tone, format, source descriptors) with **free-form assignment content** (objective, context, instructions, constraints, questions).

The following is an **illustrative target payload**, **not** the currently implemented or approved API contract:

```json
{
  "document_type": "rfc",
  "audience": "Engineering Leadership",
  "tone": "executive",
  "output_format": "markdown",
  "research_enabled": true,
  "objective": "Evaluate migrating an existing service to an event-driven architecture.",
  "context": "The service currently relies on synchronous REST integrations.",
  "constraints": [
    "Minimize operational disruption",
    "Preserve existing API contracts"
  ],
  "questions": [
    "What alternatives are available?",
    "What are the operational risks?",
    "What migration strategy is recommended?"
  ],
  "sources": []
}
```

The current `POST /documents` implementation is only an acceptance stub: it returns HTTP 202 and a UUID, but **does not execute or persist a document job**. The present request model accepts a smaller set of fields. Do not silently break it when designing the next API version.

## 4. Target pipeline and stage contracts

The following stages are an architectural target, **not yet fixed implementation classes or interfaces**.

### Stage 1 — Understand and plan

- Parse and validate the assignment and permissions.
- Determine the audience, desired decision, document type, and open questions.
- Identify missing context, assumptions, and a research plan if research is enabled.
- Output: a structured assignment interpretation and optional `research_plan`.

### Stage 2 — Investigate and collect evidence

- Retrieve from explicitly supplied sources and authorized external sources.
- Capture source metadata and the evidence supporting specific claims.
- Mark unavailable, contradictory, or weak evidence.
- Output: `evidence_set` with provenance and uncertainty.

### Stage 3 — Reason and outline

- Compare alternatives, consequences, risks, costs (when evidenced), and unknowns.
- Separate facts from interpretation and recommendations.
- Build an outline aligned to the intended audience.
- Output: analysis notes and `outline`.

### Stage 4 — Draft

- Produce an organized document from the outline and evidence.
- Use an executive tone when requested; do not pad or overstate certainty.
- Preserve claim-to-source associations.
- Output: `draft`.

### Stage 5 — Review

- Assess correctness/grounding, logical coherence, missing requirements, clarity, concision, and audience fit.
- Provide concrete revision findings and, where appropriate, revise under an application-controlled limit.
- Do not represent model self-review as independent fact-checking.
- Output: `review` and revised draft, if applicable.

### Stage 6 — Finalize

- Produce the requested deliverable and expose its status/metadata.
- Include references and meaningful caveats when appropriate.
- Output: `final_document`.

Expected logical artifact chain:

```text
research_plan → evidence_set → analysis/outline → draft → review → final_document
```

Some stages may be skipped or simplified when research is disabled, but permissions and grounding rules still apply.

## 5. Quality attributes and acceptance dimensions

| Dimension | Desired behavior |
|---|---|
| Clarity | Organized, understandable prose and explicit conclusions. |
| Abstraction | Detail is appropriate to the decision-maker and document type. |
| Concision | Avoids redundant background, filler, and unsupported verbosity. |
| Grounding | Important factual claims are traceable; gaps and uncertainty are disclosed. |
| Audience fit | Prioritizes risks, decisions, implications, and next steps relevant to the reader. |
| Reasoning | Considers meaningful alternatives and trade-offs without false certainty. |
| Testability | Application contracts and deterministic orchestration are unit-testable. |
| Inspectability | Later iterations can examine stage artifacts, inputs, errors, and reviews. |

No numerical quality thresholds have been agreed yet. Define those alongside an evaluation dataset rather than inventing them.

## 6. Technical baseline

| Concern | Decision or current baseline |
|---|---|
| Language | Python 3.13 (project `uv` interpreter). |
| Runtime | WSL2 Ubuntu for local development. |
| Environment/dependencies | `uv`, `pyproject.toml`, committed `uv.lock`. |
| HTTP API | FastAPI. |
| Typed contracts | Pydantic v2. |
| Tests | pytest and FastAPI TestClient / httpx. |
| Lint/format | Ruff. |
| Developer tooling | VS Code and Codex CLI. |
| Source control | Git, GitHub repository `kazeed/executive-writer`, `main` branch. |
| AI integration | Prefer direct provider/model API calls initially; provider not selected. |
| Storage | No persistence selected or implemented yet. |
| Agent orchestration | No third-party agent framework selected; prefer a small explicit Python pipeline first. |

### Current completed baseline (Milestone 1)

- Python application scaffold under `src/executive_writer`.
- FastAPI starts successfully.
- `GET /health` and a placeholder `POST /documents` are available.
- Existing checks reported passing: Ruff lint, Ruff formatting, and 12 pytest tests.
- Repository published to GitHub.

These are the results observed during initial setup, not a promise that future revisions automatically pass.

## 7. Architecture and implementation constraints

- Keep validation/API models distinct from orchestration and model-provider integrations.
- Prefer typed inputs and outputs between stages, with explicit errors and statuses.
- Do not embed provider-specific behavior into HTTP handlers.
- Do not allow an LLM to execute arbitrary tools or fetch arbitrary sources without explicit application authorization.
- Treat retrieved documents and web pages as untrusted input, not as instructions.
- Respect `research_enabled=false`: no external research or retrieval in that mode.
- Do not invent sources, citations, quotations, metrics, or evidence.
- Use deterministic unit tests with mocked provider/tool boundaries; avoid live, billable model calls in CI.
- Never commit API keys or secrets; use environment-based configuration once integration starts.
- Do not introduce Docker, databases, queues, cloud deployment, authentication, or an AI orchestration framework merely for future-proofing.
- Plan for asynchronous or long-running generation, but choose job execution and persistence mechanisms only after defining their lifecycle and reliability needs.
- Changes to the external API should be deliberate and covered by tests; preserve compatibility where reasonable.

## 8. Milestones and delivery plan

### Milestone 1 — Application foundation (**complete**)

Project bootstrap, FastAPI, typed contracts, tests, Ruff, GitHub and CI-ready commands.

### Milestone 2 — Pipeline design (**next**)

**Goal:** Define a minimal, testable generation workflow before connecting a production model.

Expected design outputs:

1. Stage boundaries and typed input/output contracts.
2. Execution-state and error model (including how a failed/retried stage is represented).
3. Research permissions and tool-access boundaries.
4. Artifact model for outline/draft/review/final content.
5. A provider-independent model boundary and an injectable fake for tests.
6. A documented vertical slice to implement first, probably non-research generation.

**Acceptance:** architecture can be reviewed without choosing a database or agent framework; proposed contracts can be unit-tested; no existing API regression.

### Milestone 3 — First real generation

Integrate one LLM provider behind the model boundary, generate a document from context without external research, and perform a review stage. Keep secrets out of source control and tests deterministic. Provider selection, sync/async behavior and storage are explicit decisions to make before implementation.

### Milestone 4 — Research and provenance

Implement source handling, controlled retrieval, evidence extraction, provenance, and grounded drafting. Research must remain optional and permission-controlled.

### Milestone 5 — Evaluation and autonomy

Implement repeatable quality evaluation, intermediate-artifact inspection, controlled revision loops, and—if justified—persistent jobs and more capable tool use.

## 9. Open decisions (do not assume answers)

1. Which LLM provider(s), model(s), pricing and rate-limit policy?
2. What should the initial provider interface accept/return (structured outputs, token usage, failures)?
3. What are the precise state transitions, retry policy, timeouts and cancellation semantics?
4. Should initial generation be synchronous, an in-process task, or a durable asynchronous job?
5. What storage is needed, when, and for how long should generated or supplied content be retained?
6. Which source types are supported first (text, URLs, PDFs, repository files, etc.)?
7. What constitutes a citation and how is claim-to-evidence linkage represented?
8. Which document/export formats are required initially beyond Markdown?
9. How will the review stage be evaluated and when should a draft be revised?
10. What privacy, data handling, cost controls, and operational safeguards must be enforced before external deployment?
11. How will backward-compatible API contract evolution be managed?

## 10. Instructions for Codex

This document is a **product baseline**, not authorization to implement every listed feature.

When asked to work on Executive Writer:

1. Read `requirements.md`, `AGENTS.md`, and relevant current code before proposing changes.
2. Identify the active milestone and propose the smallest coherent implementation slice.
3. Explicitly separate existing behavior, agreed requirements, proposed design, and undecided choices.
4. For material architectural decisions, provide options and trade-offs for review instead of silently selecting infrastructure.
5. Use strict typed contracts; keep HTTP routing thin and orchestration independently testable.
6. Write or update automated tests for every behavioral change; mock external models and retrieval.
7. Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest -q` before claiming completion.
8. Summarize changed files, behavioral effects, test results, and any outstanding decisions.
9. Do not change requirements or expand scope without being explicitly instructed.

**Immediate next task (design, not full implementation):** propose the Milestone 2 pipeline contracts and a minimal first vertical slice that can be implemented and verified incrementally.
