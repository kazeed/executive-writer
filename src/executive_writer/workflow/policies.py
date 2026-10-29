"""Trusted capability and resource ceilings, supplied by application code."""

from executive_writer.workflow.contracts import Contract, Count, Positive


class Permissions(Contract):
    external_research: bool = False


class ExecutionLimits(Contract):
    # Required values deliberately avoid establishing product budget defaults.
    max_planning_corrections: Count
    max_revision_cycles: Count
    max_research_rounds: Count
    max_attempts_per_stage: Positive
    max_duration_seconds: Positive
    max_model_calls: Count
    max_tokens: Count


class ExecutionPolicy(Contract):
    permissions: Permissions = Permissions()
    limits: ExecutionLimits
