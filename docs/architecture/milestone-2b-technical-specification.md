# Executive Writer — Milestone 2B Technical Specification

**Status:** Approved for implementation — not yet implemented.
**Scope:** Internal adaptive, bounded document workflow with deterministic fake stages
**Version:** 1.0 — 2026-10-29

## 1. Objective

Establish a testable, provider-independent Python orchestration core for executive document generation. An AI planner will ultimately propose intellectual work and optional stages; Python will validate and authorize an execution plan and enforce all transitions, limits, and terminal outcomes. In this milestone the AI-facing components are deterministic fakes. There are no actual model calls or external research.

### Decisions already agreed

- Planning is mandatory for **every** document request, including rewrites.
- The planner proposes stages; Python validates and authorizes execution.
- A rejected plan may be repaired only within a bounded allowance. If still invalid, execution ends with an explicit plan-validation failure, not a fallback workflow.
- Review can trigger bounded revision or additional research **only if permitted**; otherwise unresolved issues are recorded.
- Intermediate artifacts are in-memory, immutable/versioned, with no durable storage in 2B.
- An unresolved critical review finding produces an `INCOMPLETE` result retaining the latest draft and findings, not an approved document.
- Orchestration is internal; the current public API behavior is not extended to expose execution/job semantics.

## 2. Architectural boundaries

```
Existing API (unchanged)
       |
       | [future adapter; not wired to execution in 2B]
       v
DocumentBrief -> Planner -> ProposedPlan -> PlanValidator -> ApprovedPlan
                                                    |
                                                    v
                                           WorkflowExecutor
                                                    |
                                +-------------------+------------------+
                                | Stage implementations (fake in 2B)   |
                                | research / analyze / outline /      |
                                | draft / review / revise             |
                                +-------------------+------------------+
                                                    |
                                                    v
                                     ExecutionResult + Artifact History
```

- **API layer:** owns HTTP request and response validation; unchanged in 2B.
- **Domain contracts:** typed, serializable input, output, artifact, and status schemas; no vendor SDK types.
- **Planner:** proposes optional stages plus intellectual plan and rationale; proposal is untrusted data.
- **PlanValidator:** enforces stage catalog, canonical ordering, capabilities, dependencies, and configured limits; authorizes only valid plans.
- **WorkflowExecutor:** owns sequence, transitions, state, cancellation, deadline checks, artifact versions, and terminalization.
- **ExecutionPolicy:** trusted code/configuration defining allowed capabilities and maxima; cannot be overridden by model output.
- **Stages:** typed, asynchronous interfaces. Fakes in 2B; future provider integrations only behind explicit interfaces.
- **Artifact history:** append-only in-memory records holding versioned immutable snapshots, with provenance links between produced and consumed artifacts.

Avoid general DAG engines, arbitrary executable plans, plugin discovery, agent frameworks, queues, and databases.

## 3. Domain contracts (conceptual, not frozen Python signatures)

### DocumentBrief

- `objective`, `document_type`, `audience`, `context`, `instructions`, and references to supplied content (optional as appropriate).
- Explicit permission/capability policy (e.g. external research allowed/forbidden). Absence of permission means **denied**; planner intent is not authorization.
- Document constraints such as length and required sections, independently validated.
- The model must not be allowed to alter supplied requirements, capabilities, or budget ceilings.

### Planning contracts

- `ProposedPlan`: research questions, identified gaps, rationale, requested optional stages. It may request `RESEARCH`, `ANALYZE`, and/or `OUTLINE` once each; it cannot request `REVISE`, arbitrary tools, execution privileges, or stage parameters granting new authority.
- `ApprovedPlan`: validator-issued, normalized plan with canonical order, permissions, requirements, and enforced budget reference/snapshot. Use an explicit construction boundary so proposed input is never implicitly treated as approved.
- Always perform `UNDERSTAND` (deterministic brief normalization), `PLAN`, and `VALIDATE`; always include `DRAFT` and `REVIEW` on a path to a completed document. Optional execution stages occur in canonical order `RESEARCH -> ANALYZE -> OUTLINE` before drafting.
- A proposal can identify research needs when execution of research is prohibited. Such a plan must not execute research; where adequate evidence is unavailable, the workflow must report limitations rather than invent facts.

### Artifacts

Typed, immutable, individually versioned and serializable objects:

- `ResearchPlan`: questions, priorities, gaps.
- `EvidenceSet`: stable evidence/source IDs, claim or excerpt, source reference, observed/retrieved time when available, uncertainty and provenance. In 2B, fake evidence **must be clearly labeled synthetic**.
- `AnalysisResult`: findings, assumptions, comparisons, unresolved evidence gaps.
- `DocumentOutline`: ordered sections and key argument.
- `DocumentDraft`: document body, revision/version ID, citations or evidence references as appropriate.
- `ReviewResult`: decision plus structured findings (`category`, `severity`, target/reference, required corrective action, and rationale).
- `ArtifactRecord`: unique artifact ID, kind, version, producing stage attempt, consumed artifact IDs, creation timestamp, immutable payload.

A stage never mutates a previous artifact; revision creates a new version. If an optional stage is skipped, downstream stages explicitly receive absence/optional inputs, not fabricated placeholder artifacts.

### Execution and results

- `ExecutionContext` (internal mutable coordinator): brief, approved plan, policy, lifecycle, counters, current stage, and append-only artifact/attempt records. Stage implementations are not given unrestricted mutation access.
- `StageAttempt`: stage, attempt number, start/end, outcome, source artifacts, produced artifact IDs, safe error classification and usage counters.
- `ExecutionResult`: terminal status, latest draft (when available), review decision/findings, limitations, artifact history/summary, attempt/usage accounting, and error details safe to surface.

## 4. Status model

**Lifecycle states:** `CREATED -> PLANNING -> EXECUTING <-> REVIEWING -> {COMPLETED, INCOMPLETE, FAILED, CANCELLED}`. A planning validation failure terminates as `FAILED` with `PLAN_VALIDATION_FAILED` (distinct from transient infrastructure failures). A deadline or budget failure is recorded with a specific reason; if a viable draft exists with unresolved quality requirements, terminal status is `INCOMPLETE`, otherwise `FAILED`.

**Quality outcome is separate from lifecycle status.** Completing Python control flow is not equivalent to approving the document. `COMPLETED` requires review acceptance and deterministic mandatory checks; noncritical disclosed uncertainties need not prohibit completion. An unresolved critical finding always prevents `COMPLETED`.

**Stage attempt outcomes:** `SUCCEEDED`, `FAILED`, `TIMED_OUT`, `CANCELLED`; a skipped optional stage is tracked as a plan decision, not a successful attempt.

No fake asynchronous background job is implied by these internal statuses.

## 5. Plan validation and repair

Validate the proposal **before** stage execution:

1. Pydantic/schema validation and bounded field sizes.
2. Known stage names, uniqueness, allowed selection and canonical ordering.
3. Explicit permissions, requirements, dependencies, and budget ceilings.
4. Required draft/review safety gates cannot be removed or reordered.
5. No unapproved tool targets, arbitrary code, paths, network access, or privilege escalation.

Invalid plans may receive structured validation feedback and at most a policy-defined number of re-proposals (suggested initial default: **one repair attempt**, a configurable hypothesis rather than a fixed product requirement). Each attempt counts toward execution budgets. On exhaustion, produce `FAILED` with typed planning error; **no automatic fallback plan**. Unauthorized research is never silently authorized by repair.

## 6. Workflow algorithm

1. Normalize and validate brief; attach trusted execution policy.
2. Invoke planner fake, validate proposed plan, and optionally request one bounded repair.
3. Construct `ApprovedPlan`; create execution record.
4. Execute selected optional stages in canonical order; validate outputs and append artifact versions.
5. Draft (mandatory) and review (mandatory).
6. If review accepted and deterministic checks pass, return `COMPLETED`.
7. Otherwise classify findings and choose **one permitted bounded route**:
   - Writing/structure issue: `REVISE -> REVIEW`.
   - Critical evidence gap: `RESEARCH -> ANALYZE -> DRAFT -> REVIEW` **only** when research permission, stage availability, prerequisites and budgets allow. If no research capability, avoid inventing new evidence; use revision to qualify/remove unsupported claims if possible, then review again.
   - Other blocked/unknown critical defect or exhausted budget: `INCOMPLETE` with latest draft and findings.
8. Unexpected stage exception, invalid output, cancellation or timeout: record reason, perform cleanup, and transition according to clearly defined policy. Do not convert errors into review approval.

In 2B, no network research exists. A simulated authorized research stage can be used for deterministic tests; all fake evidence is explicitly synthetic and must never be served as verified external evidence.

### Boundedness and retries

Keep independent counters for planner repairs, qualitative revision cycles, research rounds, operational retry attempts, model calls/tokens (synthetic in 2B), and elapsed time. Check budgets **before** each stage/transition, and enforce timeouts around awaited work. Cancellation must not be swallowed; subsequent stages must not start. Retry only explicitly transient failures and only within the attempt limit. Exhausted revision budgets cannot turn a rejected review into acceptance.

**Suggested first test-policy values (not fixed product defaults):** one plan repair; two revision cycles; one additional research round; bounded stage retries and deadline. Any future model expenditure cap requires actual provider usage reporting to enforce correctly.

## 7. Minimal interfaces and package layout

Prefer focused `Protocol` interfaces for planner, researcher, analyst, outliner, drafter, reviewer, and reviser. Each method receives only the brief, relevant typed artifacts, and narrow read-only runtime metadata/capability context; never the executor's mutable state. Choose an explicit `WorkflowComponents` dependency container. Avoid a universal `run(stage, dict)` interface or speculative frameworks.

Proposed file layout (flexible if it reduces boilerplate):

```
src/executive_writer/workflow/
    models.py        # domain contracts
    stages.py        # stage protocols and dependency composition
    planning.py      # planning boundary
    validation.py    # plan validator
    policies.py      # trusted capability and budget rules
    executor.py      # async orchestration/state transitions
    errors.py        # typed error categories

tests/workflow/
    test_planning.py
    test_validation.py
    test_execution.py
    test_review_loops.py
    test_failures.py
```

No real provider adapter or public controller integration in 2B.

## 8. Security and observability invariants

- All model-supplied plans, stage outputs, uploaded documents, and future external content are untrusted data.
- Tool/network access is unavailable by default and authorized by Python code/policy only.
- No secrets or full sensitive document content in routine logs. Capture safe stage IDs, durations, errors and counters. Full artifact inspection is internal/test-only in 2B.
- Avoid implying that fake citations, research, token counts, or review judgments are verified.
- Never trust the reviewer to elevate permissions or override budget/quality gates.
- Capture enough metadata to inspect why a route was selected, without promising exact reproducibility of eventual model output.

## 9. Acceptance criteria

**Architecture and contracts**
- [ ] The agreed 2B models validate and serialize with strict types; no vendor-specific SDK dependency leaks into domain objects.
- [ ] Every execution invokes the planner; proposals and approvals are different concepts and authorization is explicit.
- [ ] An approved plan selects only the allowed optional stages in canonical order; mandatory draft and review cannot be bypassed.

**Policy and validation**
- [ ] Unknown/duplicate/invalid stages, inappropriate dependencies, unauthorized research, and excessive budgets are rejected.
- [ ] Invalid plans can be repaired only within a configured bound; exhaustion returns typed planning failure without a fallback.
- [ ] Model outputs cannot grant new capabilities or increase configured limits.

**Execution, artifacts and review**
- [ ] Fake workflows cover rewrite, supplied-evidence comparison, and research-intensive reports.
- [ ] Stage outputs are validated and stored in immutable, versioned, in-memory history with producer/consumer provenance.
- [ ] Review acceptance is necessary but not by itself sufficient for `COMPLETED`; deterministic mandatory checks also apply.
- [ ] Rejected writing/structure issues can follow a bounded revise/review route.
- [ ] Authorized research gaps can follow a bounded additional-research route using fakes; forbidden research never executes.
- [ ] Unresolved critical finding or exhausted quality budget yields `INCOMPLETE`, preserves latest draft and structured findings, and is never labeled approved.
- [ ] An execution that cannot produce a usable draft produces `FAILED` with a safe error classification.
- [ ] Cancellation, timeout, stage errors and operational retries are recorded with separate bounded counters; cancellation does not launch subsequent stages.

**Integration and engineering quality**
- [ ] No production LLM, external research, durable persistence, job queue, streaming, new public execution endpoint or agent framework is introduced.
- [ ] Existing API contracts and documented behavior remain unchanged.
- [ ] Ruff lint/format, strict Pyright, pytest and project CI checks pass or any pre-existing blocker is transparently documented; no security gate is disabled.
- [ ] Docs and ADRs accurately reflect implementation; test doubles are clearly identified as synthetic.

## 10. Explicitly deferred and open design questions

**Deferred:** model provider, LLM prompt strategy, external search/retrieval, citation verification against real sources, public async API/job lifecycle, durable artifact store, queue/worker, payment/cost metering, exports, general workflow DAG, parallel research, UI/progress streaming.

**To settle in implementation design, not unilaterally invent:** exact schema fields/enums; whether rejected plans always use `FAILED` vs a more specialized terminal status (this spec chooses `FAILED` with typed reason); evidence sufficiency thresholds; deterministic mandatory quality checks; reviewer finding prioritization when multiple defects coexist; whether plan-declared `RESEARCH` stage availability is mandatory for a later research route; exact budget defaults; retryable error taxonomy; artifact content retention bounds and memory-pressure behavior. Any departure from the agreed principles requires explicit review.
