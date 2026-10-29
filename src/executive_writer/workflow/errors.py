"""Safe, structured planning feedback and future execution error classifications."""

from enum import StrEnum

from executive_writer.workflow.contracts import Contract, Identifier, Text


class ValidationLayer(StrEnum):
    SCHEMA = "SCHEMA"
    SEMANTIC = "SEMANTIC"
    AUTHORIZATION = "AUTHORIZATION"


class PlanErrorCode(StrEnum):
    INVALID_SCHEMA = "INVALID_SCHEMA"
    UNKNOWN_STAGE = "UNKNOWN_STAGE"
    DUPLICATE_STAGE = "DUPLICATE_STAGE"
    INVALID_ORDER = "INVALID_ORDER"
    INVALID_SELECTION = "INVALID_SELECTION"
    INVALID_DEPENDENCY = "INVALID_DEPENDENCY"
    RESEARCH_FORBIDDEN = "RESEARCH_FORBIDDEN"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"


class PlanIssue(Contract):
    layer: ValidationLayer
    code: PlanErrorCode
    field: Text
    reason: Text


class ErrorCode(StrEnum):
    PLAN_VALIDATION_FAILED = "PLAN_VALIDATION_FAILED"
    STAGE_FAILED = "STAGE_FAILED"
    INVALID_STAGE_OUTPUT = "INVALID_STAGE_OUTPUT"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    CANCELLED = "CANCELLED"


class ExecutionError(Contract):
    code: ErrorCode
    reference: Identifier | None = None
    planning_issues: tuple[PlanIssue, ...] = ()
