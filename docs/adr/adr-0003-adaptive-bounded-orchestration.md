# ADR 0003: Adaptive, Bounded Orchestration

**Status:** Accepted in architecture discussion; implementation pending  
**Date:** 2026-10-29

## Context

Executive Writer must support requests ranging from rewrites with supplied facts to research-intensive decision reports. A single prompt is insufficient for traceable evidence, structured analysis and review; a rigid full pipeline performs unnecessary work for simple assignments. Fully autonomous agents introduce hard-to-bound execution, security and testing complexity.

## Decision

Use a Python-owned, asynchronous workflow with mandatory planning for every request. A planner proposes optional stages from a closed catalog (`RESEARCH`, `ANALYZE`, `OUTLINE`) and an intellectual work plan. Python validates permissions, dependencies, ordering and ceilings before creating an approved plan. The workflow always drafts and reviews before completion. Stage implementations are narrow typed interfaces, simulated with deterministic fakes in Milestone 2B. There is no general-purpose DAG engine or autonomous agent framework.

## Consequences

**Positive:** adaptive cost/complexity; explicit authorization; predictable control flow; testable without LLM; provider independence; greater auditability.

**Negative:** planning has fixed overhead; optional paths enlarge the test matrix; future research parallelism or novel stage types may need architecture evolution; model judgments about sufficiency remain imperfect.

## Alternatives considered

- **Single prompt:** simple but insufficient stage isolation and traceability.
- **Fixed full pipeline:** predictable but inefficient for simple requests.
- **Unrestricted agent:** flexible but difficult to authorize, debug, bound and evaluate.
- **General DAG engine:** extensible but unnecessary complexity for current requirements.

## Revisit when

Parallel research, durable long-running jobs, or independently planned sub-workflows become demonstrated requirements.
