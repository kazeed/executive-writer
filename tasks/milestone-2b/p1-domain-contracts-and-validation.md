# Executive Writer — M2B P1: Domain Contracts and Plan Validation

You are implementing **Milestone 2B, Phase 1 (M2B P1)** of Executive Writer.

## 1. Mandatory preparation

Before modifying code:

1. Read the repository's `AGENTS.md` and follow its engineering conventions.
2. Read `requirements.md` and the documentation index at `docs/README.md`.
3. Read the approved architecture specification:
   `docs/architecture/milestone-2b-technical-specification.md`
4. Read the three approved ADRs:
   - `docs/adr/0003-adaptive-bounded-orchestration.md`
   - `docs/adr/0004-execution-governance-and-outcomes.md`
   - `docs/adr/0005-in-memory-artifacts-and-internal-api.md`
5. Inspect the existing application structure, Pydantic models, configuration and tests.

**The approved specification and ADRs are authoritative.** Preserve their terminology, design decisions, constraints and intended behavior.

If actual filenames differ, locate the corresponding approved documents. Do not assume the paths above are necessarily exact.

If you discover a material contradiction between approved documents, or a decision that cannot be implemented without changing the agreed architecture, explain it before proceeding. Do not silently introduce a new architectural decision.

## 2. Objective

Implement the **typed domain contracts, workflow stage catalog, planning interfaces, plan validation and execution-policy definitions** needed by the future adaptive orchestration engine.

At the end of M2B P1, the application must be able to:

- Represent a normalized document brief.
- Represent a proposed workflow created by an AI planner.
- Validate and authorize that proposal using deterministic Python rules.
- Produce an approved execution plan.
- Reject malformed, unsupported or unauthorized proposals with explicit validation results.
- Define the typed artifacts and outcomes that later phases will consume.
- Exercise all these behaviors through deterministic automated tests.

**Do not implement workflow execution in this phase.**

## 3. Architectural rules

### 3.1 Planning

Planning is mandatory for every document request, including simple rewrites.

The planner proposes which optional stages are necessary. Python controls authorization and execution.

Define a typed asynchronous `Planner` interface using a Python `Protocol` or similarly lightweight abstraction.

A real LLM implementation is explicitly out of scope.

### 3.2 Allowed stages

Use a closed catalog of supported stages based on the approved specification.

The initial workflow has the following characteristics:

- Request normalization and planning always occur.
- Research, analysis and outlining may be selected conditionally.
- Drafting and review are mandatory for a completed document.
- Revision is a controlled transition triggered by review, not an arbitrary initial stage selected by the planner.

The approved execution plan must follow deterministic stage ordering and dependency rules.

Do not allow a planner to introduce arbitrary stages, Python function names, tools, modules, endpoints or executable commands.

### 3.3 Proposed versus approved plans

Model these as distinct concepts.

A `ProposedPlan` is untrusted planner output.

An `ApprovedPlan` represents a proposal that has passed authorization checks.

Ensure that downstream code cannot accidentally treat an unvalidated proposal as authorized simply because both models have similar fields.

Validation must not mutate the original proposal.

### 3.4 Execution permissions and policy

Define typed policy models for execution limits and permissions.

They should support the constraints established in the architecture specification, including, where applicable:

- Research authorization.
- Maximum planning corrections.
- Maximum review/revision cycles.
- Maximum research rounds.
- Maximum attempts per stage.
- Maximum execution duration.
- Model-call and token budgets.

Do not implement operational budget consumption or retry loops in P1. Define the contracts that will allow later phases to enforce them.

Do not invent provider-specific token accounting, pricing, external tool permissions or unsupported capability types.

### 3.5 Intermediate artifacts

Define typed, serializable contracts for the approved intermediate artifacts:

- Research plan.
- Evidence set.
- Analysis result.
- Document outline.
- Document draft.
- Review result and findings.

These models should support later versioning and auditability.

Represent evidence provenance and references explicitly where required by the specification.

Avoid arbitrary dictionaries when a meaningful domain type can express the contract.

Do not build an artifact repository or in-memory artifact store yet unless the approved specification specifically places that responsibility in P1.

### 3.6 Terminal outcomes

Define the relevant execution outcomes and result contracts for future implementation.

The architecture distinguishes between:

- Completed execution.
- Incomplete result, including unresolved critical review findings and the available draft.
- Failed execution, including unrecoverable planning or execution errors.
- Cancelled execution, where applicable.

Do not conflate workflow completion with document quality approval.

For an invalid plan whose permitted correction attempts are exhausted, the outcome must be an explicit validation failure. No automatic fallback workflow is authorized.

## 4. Validation requirements

Implement deterministic plan validation covering at least:

1. Unknown or unsupported stages.
2. Duplicate stages.
3. Invalid initial-stage ordering.
4. Missing mandatory stages, where the plan contract requires their explicit inclusion.
5. Invalid stage dependencies.
6. Research selected when external research is forbidden.
7. Requests exceeding configured execution-policy limits.
8. Planner attempts to broaden request permissions.
9. Attempts to insert review-driven revision into the initial execution plan.
10. Valid minimal and research-intensive workflows.

For every rejected proposal, return or raise a **typed, actionable validation result** identifying the relevant rule and reason.

Clearly separate:

- Structural/schema validation.
- Workflow semantic validation.
- Execution authorization.

Don't treat a successful Pydantic parse as sufficient authorization.

The validator must not attempt to determine whether model-generated factual claims are true. That belongs to later research and review behavior.

## 5. Code organization

Prefer the established repository conventions.

A reasonable starting point is:

```text
src/executive_writer/workflow/
├── models.py
├── stages.py
├── planning.py
├── validation.py
├── policies.py
└── errors.py
```

This layout is illustrative. Adapt it to existing repository structure where appropriate, rather than creating unnecessary abstractions or duplicating models.

Keep domain contracts independent of FastAPI request handling and provider SDKs.

Use modern Python 3.13 typing, Pydantic v2, and clear, narrow interfaces.

## 6. Tests

Create focused tests that prove the domain and authorization behavior.

Cover successful plans and every relevant validation failure, including adversarial planner output.

Important test scenarios:

- Simple memo with no research or standalone analysis.
- Internal architectural comparison requiring analysis but not external research.
- Research-intensive report with research authorized.
- Research requested but forbidden by policy.
- Duplicate, unknown or incorrectly ordered stages.
- Missing required stages or dependencies.
- Invalid budgets.
- An attempted privilege or permission escalation.
- A proposal that improperly includes revision.
- Serialization and deserialization of the principal Pydantic contracts.
- Immutability of approved plans and artifacts where specified.
- Clear validation error codes and diagnostics.

Tests must not require network access, API keys, a database, Docker or real model inference.

Maintain the existing project's coverage requirements.

## 7. Explicitly out of scope

Do not implement any of the following:

- Real LLM calls, prompts or provider SDKs.
- Stage execution or workflow orchestration.
- Review loops or retry execution.
- Fake research, drafting or reviewer implementations.
- Artifact persistence or databases.
- Background jobs, queues or workers.
- New public API endpoints.
- Changes to the current `POST /documents` behavior.
- Web search, external research or retrieval tools.
- LangChain, LangGraph, Celery, Redis or similar frameworks.
- An extensible plugin system.
- Any infrastructure changes not necessary for P1.

Avoid adding dependencies unless a clear requirement cannot be met with the existing stack.

## 8. Quality gates

Run and resolve failures for:

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
```

Preserve Python 3.13 compatibility and strict Pyright checking.

Do not loosen lint rules, type-checking settings, coverage thresholds or security checks to make the implementation pass.

## 9. Documentation

Follow the repository's project-documentation skill in `.agents/skills/project-documentation/SKILL.md`.

Update documentation to reflect the actual P1 implementation.

Preserve the approved architecture documents and ADR decisions. Do not rewrite them to justify a different implementation.

Document any material clarification or deviation explicitly.

Maintain the distinction between:

- Approved architecture.
- Implemented P1 functionality.
- Functionality deferred to M2B P2, P3 and later milestones.

## 10. Delivery requirements

Work on the current implementation feature branch.

Do not commit, push, merge or create a pull request unless explicitly authorized.

When finished, provide:

1. A concise implementation summary.
2. Files created or modified.
3. Key domain models and interfaces.
4. Validation rules implemented.
5. Tests added, with results.
6. Ruff, Pyright and pytest verification results.
7. Any unresolved questions, assumptions or deviations.
8. A clear statement of what remains for M2B P2.

**Completion criterion:** M2B P1 is complete when the repository can construct, validate and authorize structured workflow plans, represent the required domain artifacts, and reject invalid or unauthorized plans through well-tested Python code—without executing a workflow or invoking an AI model.
