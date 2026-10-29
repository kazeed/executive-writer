# ADR 0005: In-Memory Artifact History and Internal-Only 2B Workflow

**Status:** Accepted in architecture discussion; implementation pending  
**Date:** 2026-10-29

## Context

Milestone 2B's goal is to validate execution architecture, not operate user jobs. The existing `POST /documents` currently acknowledges a placeholder request, without actual background execution or persistence. Exposing job status or wiring a potentially long-running workflow directly into an HTTP endpoint would introduce premature and possibly misleading contracts.

## Decision

Keep the new orchestrator private to the application in Milestone 2B, driven by tests and internal examples only. Do not expose job progress, results, or execution endpoints. Store typed, immutable/versioned artifacts in process memory for one execution and retain provenance and stage attempts in its result. Do not implement durable storage, queues, workers or a job registry. Maintain existing API behavior and document clearly that the current 202 response is a placeholder, not an executed or persisted job.

## Consequences

**Positive:** small milestone, deterministic tests, fewer infrastructure decisions, no premature operational promises.

**Negative:** process restarts lose execution data; no long-running durable jobs, multi-instance operation or user-facing progress; memory limits require attention once real models and large documents are introduced.

## Revisit when

A real provider and execution endpoint are introduced, or when users require cancellation, progress tracking, retries after restart, or retrieval of completed documents.
