"""Typed runtime failures, separating transient retries from cancellation."""

import asyncio

from executive_writer.workflow.errors import ErrorCode
from executive_writer.workflow.models import ExecutionResult
from executive_writer.workflow.reporting import ModelUsage


class ComponentFailure(Exception):
    """An adapter explicitly classifies a failure and reports incurred usage."""

    def __init__(self, *, transient: bool, usage: ModelUsage) -> None:
        super().__init__("Component invocation failed")
        self.transient = transient
        self.usage = usage


class ExecutionStopped(Exception):
    def __init__(self, code: ErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


class WorkflowCancelled(asyncio.CancelledError):
    """Cancellation stays cancellation; callers may inspect the terminal snapshot."""

    def __init__(self, result: ExecutionResult) -> None:
        super().__init__("Workflow cancelled")
        self.result = result
