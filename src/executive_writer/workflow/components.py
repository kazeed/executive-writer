"""Narrow component ports; no mutable coordinator or storage access."""

from dataclasses import dataclass
from typing import Protocol

from executive_writer.workflow.models import (
    AnalysisResult,
    DocumentBrief,
    DocumentDraft,
    DocumentOutline,
    EvidenceSet,
    ResearchPlan,
    ReviewResult,
)
from executive_writer.workflow.reporting import ComponentResult, ResourceBudget


class Researcher(Protocol):
    @property
    def budget(self) -> ResourceBudget: ...

    async def research(
        self, brief: DocumentBrief, plan: ResearchPlan
    ) -> ComponentResult[EvidenceSet]: ...


class Analyst(Protocol):
    @property
    def budget(self) -> ResourceBudget: ...

    async def analyze(
        self, brief: DocumentBrief, evidence: EvidenceSet | None
    ) -> ComponentResult[AnalysisResult]: ...


class Outliner(Protocol):
    @property
    def budget(self) -> ResourceBudget: ...

    async def outline(
        self, brief: DocumentBrief, evidence: EvidenceSet | None, analysis: AnalysisResult | None
    ) -> ComponentResult[DocumentOutline]: ...


class Drafter(Protocol):
    @property
    def budget(self) -> ResourceBudget: ...

    async def draft(
        self,
        brief: DocumentBrief,
        evidence: EvidenceSet | None,
        analysis: AnalysisResult | None,
        outline: DocumentOutline | None,
    ) -> ComponentResult[DocumentDraft]: ...


class Reviewer(Protocol):
    @property
    def budget(self) -> ResourceBudget: ...

    async def review(
        self, brief: DocumentBrief, draft: DocumentDraft, evidence: EvidenceSet | None
    ) -> ComponentResult[ReviewResult]: ...


@dataclass(frozen=True, slots=True)
class WorkflowComponents:
    drafter: Drafter
    reviewer: Reviewer
    researcher: Researcher | None = None
    analyst: Analyst | None = None
    outliner: Outliner | None = None
