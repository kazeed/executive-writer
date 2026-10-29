"""Immutable, versioned workflow artifacts and terminal outcome contracts."""

from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from executive_writer.models.documents import DocumentType
from executive_writer.workflow.contracts import (
    Body,
    Contract,
    Count,
    Identifier,
    Identifiers,
    Positive,
    Text,
    Texts,
)
from executive_writer.workflow.errors import ExecutionError
from executive_writer.workflow.policies import Permissions
from executive_writer.workflow.stages import Stage


class DocumentConstraints(Contract):
    max_words: Positive | None = None
    required_sections: Texts = ()


class SourceReference(Contract):
    source_id: Identifier
    reference: Text
    kind: Literal["supplied", "external", "synthetic"]


class DocumentBrief(Contract):
    objective: Text
    document_type: DocumentType
    audience: Text | None = None
    context: Body | None = None
    instructions: Body | None = None
    supplied_content: Annotated[tuple[SourceReference, ...], Field(max_length=100)] = ()
    permissions: Permissions = Permissions()
    constraints: DocumentConstraints = DocumentConstraints()


class Artifact(Contract):
    artifact_id: UUID
    version: Positive


class ResearchQuestion(Contract):
    question: Text
    priority: Literal["high", "medium", "low"]


class ResearchPlan(Artifact):
    kind: Literal["research_plan"] = "research_plan"
    questions: Annotated[tuple[ResearchQuestion, ...], Field(max_length=100)] = ()
    gaps: Texts = ()


class Evidence(Contract):
    evidence_id: Identifier
    claim_or_excerpt: Text
    source: SourceReference
    observed_at: AwareDatetime | None = None
    retrieved_at: AwareDatetime | None = None
    uncertainty: Text
    provenance: Text


class EvidenceSet(Artifact):
    kind: Literal["evidence_set"] = "evidence_set"
    evidence: Annotated[tuple[Evidence, ...], Field(max_length=100)] = ()

    @model_validator(mode="after")
    def unique_evidence(self) -> Self:
        if len({item.evidence_id for item in self.evidence}) != len(self.evidence):
            raise ValueError("evidence IDs must be unique")
        return self


class AnalysisResult(Artifact):
    kind: Literal["analysis_result"] = "analysis_result"
    findings: Texts = ()
    assumptions: Texts = ()
    comparisons: Texts = ()
    unresolved_gaps: Texts = ()
    evidence_ids: Identifiers = ()


class OutlineSection(Contract):
    title: Text
    key_argument: Text
    evidence_ids: Identifiers = ()


class DocumentOutline(Artifact):
    kind: Literal["document_outline"] = "document_outline"
    sections: Annotated[tuple[OutlineSection, ...], Field(min_length=1, max_length=100)]


class Citation(Contract):
    claim_reference: Text
    evidence_id: Identifier


class DocumentDraft(Artifact):
    kind: Literal["document_draft"] = "document_draft"
    body: Body
    citations: Annotated[tuple[Citation, ...], Field(max_length=100)] = ()


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ReviewDecision(StrEnum):
    ACCEPTED = "ACCEPTED"
    CHANGES_REQUIRED = "CHANGES_REQUIRED"


class ReviewFinding(Contract):
    category: Literal["grounding", "structure", "clarity", "requirements", "other"]
    severity: Severity
    target: Text
    corrective_action: Text
    rationale: Text


class ReviewResult(Artifact):
    kind: Literal["review_result"] = "review_result"
    draft_id: UUID
    decision: ReviewDecision
    findings: Annotated[tuple[ReviewFinding, ...], Field(max_length=100)] = ()

    @model_validator(mode="after")
    def acceptance_has_no_critical_findings(self) -> Self:
        if self.decision == ReviewDecision.ACCEPTED and any(
            finding.severity == Severity.CRITICAL for finding in self.findings
        ):
            raise ValueError("critical findings prevent review acceptance")
        return self


type ArtifactPayload = Annotated[
    ResearchPlan | EvidenceSet | AnalysisResult | DocumentOutline | DocumentDraft | ReviewResult,
    Field(discriminator="kind"),
]


class AttemptReference(Contract):
    stage: Stage
    attempt_number: Positive


class ArtifactRecord(Contract):
    payload: ArtifactPayload
    producer: AttemptReference
    consumed_artifact_ids: tuple[UUID, ...] = ()
    created_at: AwareDatetime


class Usage(Contract):
    model_calls: Count = 0
    tokens: Count = 0
    planning_corrections: Count = 0
    revision_cycles: Count = 0
    research_rounds: Count = 0


class AttemptOutcome(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"


class StageAttempt(AttemptReference):
    started_at: AwareDatetime
    ended_at: AwareDatetime
    outcome: AttemptOutcome
    source_artifact_ids: tuple[UUID, ...] = ()
    produced_artifact_ids: tuple[UUID, ...] = ()
    usage: Usage = Usage()
    error: ExecutionError | None = None

    @model_validator(mode="after")
    def chronological(self) -> Self:
        if self.ended_at < self.started_at:
            raise ValueError("attempt end precedes start")
        return self


class Lifecycle(StrEnum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    REVIEWING = "REVIEWING"
    COMPLETED = "COMPLETED"
    INCOMPLETE = "INCOMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ExecutionResult(Contract):
    status: Literal[
        Lifecycle.COMPLETED, Lifecycle.INCOMPLETE, Lifecycle.FAILED, Lifecycle.CANCELLED
    ]
    latest_draft: DocumentDraft | None = None
    review: ReviewResult | None = None
    mandatory_checks_passed: bool = False
    limitations: Texts = ()
    artifacts: tuple[ArtifactRecord, ...] = ()
    attempts: tuple[StageAttempt, ...] = ()
    usage: Usage = Usage()
    error: ExecutionError | None = None

    @model_validator(mode="after")
    def terminal_invariants(self) -> Self:
        if self.review is not None and (
            self.latest_draft is None or self.review.draft_id != self.latest_draft.artifact_id
        ):
            raise ValueError("review must reference the latest draft")
        if self.status == Lifecycle.COMPLETED and (
            self.latest_draft is None
            or self.review is None
            or self.review.decision != ReviewDecision.ACCEPTED
            or not self.mandatory_checks_passed
            or self.error is not None
        ):
            raise ValueError("completion requires an accepted draft and mandatory checks")
        if self.status == Lifecycle.INCOMPLETE and self.latest_draft is None:
            raise ValueError("incomplete results must retain a draft")
        if self.status == Lifecycle.FAILED and self.error is None:
            raise ValueError("failed results require a safe error classification")
        return self
