# ADR 0001: Docker-compatible OCI packaging

**Status:** Accepted direction; packaging authored in Milestone 2A, verification blocked.

## Context

[AGENTS.md, section 12](../../AGENTS.md#12-production-engineering-delivery-and-architecture-governance)
explicitly selects Docker-compatible OCI packaging while leaving hosting undecided.
The [README](../../README.md#docker-packaging-and-usage) also records this direction.
This ADR originally transcribed that existing decision. The current Milestone 2A request
authorizes repository packaging work, not public deployment.
The original decision date and additional historical rationale are unknown.

## Decision

Package the application as a Docker-compatible OCI container when the container milestone is
explicitly scoped. Keep application logic independent of a hosting provider. A multi-stage [Dockerfile](../../Dockerfile) now installs locked runtime dependencies using uv,
then runs Uvicorn as UID 10001. See [operations](../operations/status.md) and
[verification blockers](../operations/milestone-2a.md).

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
abuse controls. Runtime/container controls and their verification status are recorded in the operations guide.
