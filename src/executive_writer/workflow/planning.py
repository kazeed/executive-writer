"""Untrusted planning interface and serializable audit snapshot."""

from typing import Annotated, Protocol

from pydantic import Field

from executive_writer.workflow.contracts import Contract, Text, Texts
from executive_writer.workflow.errors import PlanIssue
from executive_writer.workflow.models import DocumentBrief, ResearchPlan
from executive_writer.workflow.policies import ExecutionLimits, ExecutionPolicy
from executive_writer.workflow.reporting import ComponentResult, ResourceBudget
from executive_writer.workflow.stages import Stage


class StageDependency(Contract):
    stage: Stage
    requires: Stage


class ProposedPlan(Contract):
    optional_stages: Annotated[tuple[Text, ...], Field(max_length=10)] = ()
    rationale: Text
    research_plan: ResearchPlan | None = None
    identified_gaps: Texts = ()
    dependencies: Annotated[tuple[StageDependency, ...], Field(max_length=20)] = ()
    requested_limits: ExecutionLimits | None = None


class PlanSnapshot(Contract):
    """Serializable audit data. Deserializing a snapshot does not authorize it."""

    brief: DocumentBrief
    policy: ExecutionPolicy
    proposal: ProposedPlan
    stages: tuple[Stage, ...]


class Planner(Protocol):
    @property
    def budget(self) -> ResourceBudget: ...

    async def propose(
        self,
        brief: DocumentBrief,
        policy: ExecutionPolicy,
        feedback: tuple[PlanIssue, ...] = (),
    ) -> ComponentResult[ProposedPlan]: ...
