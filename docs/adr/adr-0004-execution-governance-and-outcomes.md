# ADR 0004: Validation, Execution Governance, and Review Outcomes

**Status:** Accepted in architecture discussion; implementation pending  
**Date:** 2026-10-29

## Context

LLM-proposed plans and reviewer judgments cannot be allowed to grant permissions, expand budgets, or silently approve unsupported conclusions. Reports may require revision or additional evidence. Operational retries are different from intellectual revisions. Critical review defects may remain after resources are exhausted.

## Decision

1. Treat `ProposedPlan` as untrusted and `ApprovedPlan` as Python-authorized. The validator enforces a closed stage catalog, mandatory draft/review, canonical order, explicit permissions and trusted limits.
2. Allow bounded plan repairs with structured validation feedback. If the repair allowance expires, terminate with an explicit `PLAN_VALIDATION_FAILED` result; do not execute a fallback plan.
3. Allow bounded `REVISE -> REVIEW` and, if separately permitted, additional `RESEARCH -> ANALYZE -> DRAFT -> REVIEW`. Re-authorize transitions against existing permissions and budgets.
4. Track planner repairs, qualitative revisions, research rounds and operational retries with distinct counters. Enforce time/deadline and cancellation rules.
5. Maintain immutable/versioned in-memory artifacts during 2B; preserve stage attempts and provenance references.
6. Keep lifecycle outcome separate from document quality. `COMPLETED` requires review acceptance and mandatory deterministic checks. An unresolved critical defect returns `INCOMPLETE` with the latest draft, findings and limitations. If no usable draft can be produced, return `FAILED`. Cancellation returns `CANCELLED`.

## Consequences

**Positive:** policy cannot be bypassed through model output; bounded resource use; no false approval on exhaustion; useful partial work survives review failure; distinct operational diagnostics.

**Negative:** richer result modeling, more transition tests, and a future need for artifact retention/privacy controls and durable execution if workflows outgrow a process lifetime.

## Alternatives considered

- **Auto-correct or fallback invalid plans:** rejected due to potential silent scope/permission expansion.
- **Unbounded self-critique:** rejected due to cost and termination risk.
- **Mark final draft approved after maximum revisions:** rejected because budget exhaustion is not validation.
- **Drop rejected draft entirely:** rejected because latest draft plus findings is useful to a caller while clearly not approved.
