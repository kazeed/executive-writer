"""Per-call resource reservations and explicit component usage reports."""

from executive_writer.workflow.contracts import Contract, Count


class ResourceBudget(Contract):
    """Trusted component's maximum resource requirement for one invocation."""

    model_calls: Count
    tokens: Count


class ModelUsage(ResourceBudget):
    synthetic: bool


class ComponentResult[T](Contract):
    value: T
    usage: ModelUsage
