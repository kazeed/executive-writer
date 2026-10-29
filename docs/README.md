# Technical documentation

Executive Writer v0.1.0 is a local FastAPI scaffold, not a functioning AI writer.
Milestone 2A adds engineering/container configuration but remains blocked on verification.
M2B P1 adds internal workflow contracts and plan authorization; it does not execute workflows.
This baseline describes the current code and configuration; passing tests verify only their assertions.

- [Architecture and request lifecycle](architecture/overview.md)
- [M2B P1 contracts, validation and verification](architecture/milestone-2b-p1.md)
- [Approved M2B specification (later execution remains planned)](architecture/milestone-2b-technical-specification.md)
- [ADR 0003: Adaptive bounded orchestration](adr/adr-0003-adaptive-bounded-orchestration.md)
- [ADR 0004: Execution governance and outcomes](adr/adr-0004-execution-governance-and-outcomes.md)
- [ADR 0005: Internal workflow and in-memory artifacts](adr/adr-0005-in-memory-artifacts-and-internal-api.md)
- [API contracts](api/reference.md)
- [Development and verification](development/guide.md)
- [Operations and security status](operations/status.md)
- [Milestone 2A verification and blockers](operations/milestone-2a.md)
- [ADR 0002: Foundation configuration and security gates](adr/0002-engineering-foundation.md)
- [ADR 0001: OCI packaging direction](adr/0001-oci-packaging.md)
- [Product requirements](requirements.md) — desired behavior and future milestones
- [Engineering conventions](../AGENTS.md) — standards, not implemented protections

Use the repository-local [project-documentation skill](../.agents/skills/project-documentation/SKILL.md)
in bootstrap mode for a new baseline or update mode after a development task or milestone.
