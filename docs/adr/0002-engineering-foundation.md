# ADR 0002: Foundation configuration and security gates

**Status:** Implemented configuration; verification and tool locking incomplete.
**Date:** 2026-10-28 (Milestone 2A).

## Context

The milestone explicitly requires Pyright, validated environment settings, CI security gates and
portable production container packaging while preserving placeholder document behavior.

## Decision

Use strict Pyright for `src`, Pydantic Settings with `EW_` environment variables, and independent
quality, test, security and container CI jobs. Use pip-audit, Bandit, Gitleaks and Trivy without
blanket suppressions. Audit all locked Python dependencies; fail container scanning on HIGH or
CRITICAL vulnerabilities, including findings without an available fix. Tests target 90% coverage.

Preserve docs/schema by default as explicitly requested, with a switch to disable them. Redact
validation error entries to location/type and return generic internal errors. Add conservative
response headers; defer CSP/HSTS to a concrete browser/TLS deployment rather than break API docs.

## Alternatives considered

Manual environment parsing would duplicate validation already provided by Pydantic. A new task
runner, deployment provider, authentication service or background framework is unnecessary for
this scaffold and outside scope. Tools in isolated uv environments currently keep the application
lock valid while unavailable tools cannot be resolved; this is a temporary incomplete state,
not the desired final reproducible developer setup.

## Consequences and review

Validation error metadata is deliberately reduced; success responses are unchanged. Runtime
settings add one established library already present transitively in the original lockfile.
Tool dependencies must still be installed and locked with uv; image digests need registry access.
CI and full tests/scans remain unverified. Review these explicit gaps and rerun gates before
accepting the milestone. No storage, model, hosting or public-exposure decisions are made here.
