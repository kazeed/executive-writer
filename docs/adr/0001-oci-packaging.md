# ADR 0001: Docker-compatible OCI packaging

**Status:** Accepted direction; implementation pending.

## Context

[AGENTS.md, section 12](../../AGENTS.md#12-production-engineering-delivery-and-architecture-governance)
explicitly selects Docker-compatible OCI packaging while leaving hosting undecided.
The [README](../../README.md#docker-packaging-and-usage-planned) also records this direction.
This ADR transcribes that existing decision; it does not authorize packaging or deployment.
The original decision date and additional historical rationale are unknown.

## Decision

Package the application as a Docker-compatible OCI container when the container milestone is
explicitly scoped. Keep application logic independent of a hosting provider. No Dockerfile or
container runtime configuration is currently implemented.

## Alternatives considered

No historical comparison of alternatives is recorded. Do not infer that particular hosts or
packaging alternatives were evaluated or rejected.

## Consequences

Future packaging work must include locked dependency installation, a minimal runtime, non-root
execution, exclusion of secrets/local artifacts, and build/startup/health/termination verification.
A successful image build alone will not establish deployability. Hosting selection and public
exposure require separate decisions and authorization.

## Relevant constraints

Preserve the Python 3.13 baseline and uv lockfile. Do not bake credentials or private documents into
images. Do not assume persistent local disk. Deployment must address TLS, proxy trust, access and
abuse controls. These are requirements for future implementation, not active container protections.
