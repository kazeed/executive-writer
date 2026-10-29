"""Deterministic simulations: never model inference, retrieval or fact checking."""

from dataclasses import dataclass
from uuid import uuid4

from executive_writer.workflow.components import WorkflowComponents
from executive_writer.workflow.errors import PlanIssue
from executive_writer.workflow.models import (
    AnalysisResult,
    Citation,
    DocumentBrief,
    DocumentDraft,
    DocumentOutline,
    Evidence,
    EvidenceSet,
    OutlineSection,
    ResearchPlan,
    ResearchQuestion,
    ReviewDecision,
    ReviewFinding,
    ReviewResult,
    Severity,
    SourceReference,
)
from executive_writer.workflow.planning import ProposedPlan
from executive_writer.workflow.policies import ExecutionPolicy
from executive_writer.workflow.reporting import ComponentResult, ModelUsage, ResourceBudget


@dataclass(frozen=True)
class FakePlanner:
    optional_stages: tuple[str, ...] = ()

    @property
    def budget(self) -> ResourceBudget:
        return ResourceBudget(model_calls=1, tokens=10)

    async def propose(
        self,
        brief: DocumentBrief,
        policy: ExecutionPolicy,
        feedback: tuple[PlanIssue, ...] = (),
    ) -> ComponentResult[ProposedPlan]:
        research_plan = None
        if "RESEARCH" in self.optional_stages:
            research_plan = ResearchPlan(
                artifact_id=uuid4(),
                version=1,
                questions=(ResearchQuestion(question="Synthetic test question", priority="high"),),
            )
        return ComponentResult(
            value=ProposedPlan(
                optional_stages=self.optional_stages,
                rationale="Synthetic plan",
                research_plan=research_plan,
            ),
            usage=ModelUsage(model_calls=1, tokens=10, synthetic=True),
        )


@dataclass(frozen=True)
class FakeStages:
    decision: ReviewDecision = ReviewDecision.ACCEPTED
    body: str | None = None

    @property
    def budget(self) -> ResourceBudget:
        return ResourceBudget(model_calls=1, tokens=10)

    def _reported[T](self, value: T) -> ComponentResult[T]:
        return ComponentResult(
            value=value, usage=ModelUsage(model_calls=1, tokens=10, synthetic=True)
        )

    def components(self) -> WorkflowComponents:
        return WorkflowComponents(
            drafter=self,
            reviewer=self,
            researcher=self,
            analyst=self,
            outliner=self,
        )

    async def research(
        self,
        brief: DocumentBrief,
        plan: ResearchPlan,
    ) -> ComponentResult[EvidenceSet]:
        return self._reported(
            EvidenceSet(
                artifact_id=uuid4(),
                version=1,
                evidence=(
                    Evidence(
                        evidence_id="synthetic-evidence-1",
                        claim_or_excerpt="Synthetic example; not a real fact",
                        source=SourceReference(
                            source_id="synthetic-source-1",
                            kind="synthetic",
                            reference="Deterministic simulation; no retrieval",
                        ),
                        uncertainty="Synthetic and unverified",
                        provenance="FakeStages.research simulation",
                    ),
                ),
            )
        )

    async def analyze(
        self,
        brief: DocumentBrief,
        evidence: EvidenceSet | None,
    ) -> ComponentResult[AnalysisResult]:
        return self._reported(
            AnalysisResult(
                artifact_id=uuid4(),
                version=1,
                findings=("Synthetic analysis",),
                evidence_ids=tuple(item.evidence_id for item in evidence.evidence)
                if evidence
                else (),
            )
        )

    async def outline(
        self,
        brief: DocumentBrief,
        evidence: EvidenceSet | None,
        analysis: AnalysisResult | None,
    ) -> ComponentResult[DocumentOutline]:
        return self._reported(
            DocumentOutline(
                artifact_id=uuid4(),
                version=1,
                sections=(OutlineSection(title="Summary", key_argument="Synthetic outline"),),
            )
        )

    async def draft(
        self,
        brief: DocumentBrief,
        evidence: EvidenceSet | None,
        analysis: AnalysisResult | None,
        outline: DocumentOutline | None,
    ) -> ComponentResult[DocumentDraft]:
        sections = brief.constraints.required_sections or ("Summary",)
        body = (
            self.body
            if self.body is not None
            else "\n\n".join(
                f"## {section}\nSynthetic draft; no real inference or fact verification."
                for section in sections
            )
        )
        return self._reported(
            DocumentDraft(
                artifact_id=uuid4(),
                version=1,
                body=body,
                citations=tuple(
                    Citation(claim_reference="Synthetic example", evidence_id=item.evidence_id)
                    for item in evidence.evidence
                )
                if evidence
                else (),
            )
        )

    async def review(
        self,
        brief: DocumentBrief,
        draft: DocumentDraft,
        evidence: EvidenceSet | None,
    ) -> ComponentResult[ReviewResult]:
        findings = (
            ()
            if self.decision == ReviewDecision.ACCEPTED
            else (
                ReviewFinding(
                    category="grounding",
                    severity=Severity.CRITICAL,
                    target="Synthetic draft",
                    corrective_action="Resolve the simulated evidence gap",
                    rationale="Synthetic review finding; no real fact checking",
                ),
            )
        )
        return self._reported(
            ReviewResult(
                artifact_id=uuid4(),
                version=1,
                draft_id=draft.artifact_id,
                decision=self.decision,
                findings=findings,
            )
        )
