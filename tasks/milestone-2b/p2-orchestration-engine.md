# Codex task — M2B P2: orchestration engine

## Preparation and authority

Work on a **new feature branch** based on the latest `main` (e.g. `feature/milestone-2b-p2-orchestration`). Read `AGENTS.md`, `requirements.md`, `docs/README.md`, `docs/architecture/milestone-2b-technical-specification.md`, ADRs 0003–0005 (locate actual filenames), the P1 implementation record, and the project documentation skill. Inspect existing `src/executive_writer/workflow/` contracts and tests before changing them. Follow approved decisions; report material conflicts or architectural gaps instead of silently inventing policy.

**Roadmap clarification approved after the original specification:** M2B P2 remains *in memory*, with no public job API. A newly inserted **M2B P3** will add SQLite, SQLAlchemy/Alembic, a dedicated worker, durable queue and PostgreSQL portability; prior P3 review loops become P4 and final verification becomes P5. Avoid tight coupling between the executor and artifact storage, but do not build SQL/queue adapters now. Document this roadmap clarification; do not silently rewrite/supersede existing ADRs. Flag any need for a new ADR as a follow-up.

## Objective

Build an **internal, asynchronous, provider-neutral workflow executor** for the P1 domain contracts. Execute valid, validator-issued plans with deterministic simulated components; enforce execution state, budgets, bounded plan correction, timeouts, cancellation, stage attempts and immutable append-only artifact history. The existing HTTP API remains unchanged.

## Implementation requirements

1. **Entry point and authorization.** An internal service takes a `DocumentBrief`, trusted `ExecutionPolicy`, and injected `Planner` / stage components. Always invoke planning, including rewrites. Validate each proposal with existing `PlanValidator`. Return an approved-plan-driven execution only; never execute a raw proposal or a stage selected outside the approved catalog. If validation fails, pass typed safe issues back for at most `max_planning_corrections` additional proposals; exhaust to `FAILED` with `PLAN_VALIDATION_FAILED`, never a fallback. Count planner calls and corrections toward applicable limits.
2. **Stage composition.** Define narrow async `Protocol` interfaces and an explicit typed `WorkflowComponents` container for research, analysis, outline, draft and review. A lightweight fake planner/stages set is needed for deterministic integration tests, with no API keys/network. Do not give stages mutable executor state or a general `run(stage, dict)` mechanism. Provide typed optional inputs when earlier stages were skipped. Preserve `UNDERSTAND`, `PLAN`, `VALIDATE` bookkeeping (do not pretend they made model calls if they did not).
3. **Execution path.** Execute approved initial optional stages in canonical order, then mandatory `DRAFT` and `REVIEW`. A review `ACCEPTED` result alone is insufficient for `COMPLETED`: add narrow deterministic mandatory checks supported by existing contracts (e.g. required sections/length and valid evidence references as applicable). Make missing evidence/unsupported citations visible, never fabricate verification. A rejected review should result in `INCOMPLETE` with its latest draft/findings for P2; **do not implement review-driven revision or research re-entry yet** (now P4).
4. **Artifact store boundary.** Add a small in-memory, append-only repository abstraction suited to later durable storage. Retain immutable `ArtifactRecord`s, stable IDs and versioned payloads, producer attempt and consumed-artifact provenance. No overwriting, no fake artifacts for omitted stages. Validate stage outputs at runtime, including unchecked model instances; reject wrong artifact types, invalid provenance or inconsistent version/ID semantics.
5. **Governance and errors.** Centralize counters for model calls/tokens (synthetic usage is reported explicitly by fake stages, never guessed), planning corrections, research rounds and attempts. Enforce ceilings *before* each stage/attempt and after usage is reported; no stage may run after exhausted budget. Apply deadline/timeout across awaited work; observe external asyncio cancellation without swallowing it or launching later stages. Retry only explicitly classified transient failures within `max_attempts_per_stage`; distinguish retry attempts from quality revisions. Record `StageAttempt` outcomes and safe error codes; never expose secrets or raw document text in diagnostic messages.
6. **Terminal results.** Build `ExecutionResult` consistently with existing P1 model invariants: `COMPLETED` only with accepted review and passing mandatory checks; `INCOMPLETE` keeps available draft and findings/limitations when quality is unresolved; `FAILED` for irrecoverable planning/execution errors without viable draft; `CANCELLED` for cancellation. Resolve any contract gaps narrowly, explain consequential choices, and keep types strict.

## Tests / acceptance

Add deterministic tests covering: minimal rewrite; analysis-only workflow; research-authorized path with **synthetic-labeled** evidence; forbidden research; invalid-plan repair and exhausted repair; canonical stage order and skipped stages; artifact IDs/versions/provenance and immutability; wrong stage output; accepted/rejected review and deterministic quality gates; exhausted limits; retryable vs permanent failures; deadline/timeout; mid-stage cancellation; no execution after cancellation/budget exhaustion. Tests must be fast and need no network, DB, Docker or model provider. Keep public API behavior unchanged.

Run:

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run --with pytest-cov==7.0.0 pytest -q --cov --cov-report=term-missing
```

Maintain >=90% coverage and existing CI security gates. Follow project documentation skill; document only what is implemented and explicitly defer persistence/job infrastructure to P3 and review routing to P4. No real models, external retrieval, SQLAlchemy, Alembic, queue/worker, new endpoints, parallel DAG, Celery/Redis/LangGraph, or deployment changes.

## Delivery

Report modified files, principal interfaces, execution/authorization guarantees, tests/coverage, full gate results and unresolved design issues. **Do not commit, push, open a PR or merge without explicit permission.**
