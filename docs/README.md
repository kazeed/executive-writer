# Technical documentation

Executive Writer v0.1.0 is a local FastAPI scaffold, not a functioning AI writer.
Milestone 2A adds engineering/container configuration but remains blocked on verification.
This baseline describes the current code and configuration; passing tests verify only their assertions.

- [Architecture and request lifecycle](architecture/overview.md)
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
