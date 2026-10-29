from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from executive_writer.workflow.errors import ErrorCode, ExecutionError
from executive_writer.workflow.models import (
    AnalysisResult,
    ArtifactPayload,
    ArtifactRecord,
    AttemptOutcome,
    AttemptReference,
    Citation,
    DocumentBrief,
    DocumentConstraints,
    DocumentDraft,
    DocumentOutline,
    Evidence,
    EvidenceSet,
    ExecutionResult,
    Lifecycle,
    OutlineSection,
    ResearchPlan,
    ReviewDecision,
    ReviewFinding,
    ReviewResult,
    Severity,
    SourceReference,
    StageAttempt,
    Usage,
)
from executive_writer.workflow.stages import Stage


@pytest.fixture
def draft():
    return DocumentDraft(
        artifact_id=uuid4(),
        version=1,
        body="A supported recommendation.",
        citations=(Citation(claim_reference="recommendation", evidence_id="e1"),),
    )


@pytest.fixture
def critical():
    return ReviewFinding(
        category="grounding",
        severity=Severity.CRITICAL,
        target="recommendation",
        corrective_action="Supply evidence or qualify",
        rationale="Missing evidence",
    )


def test_artifact_round_trips(draft, critical):
    source = SourceReference(source_id="s1", kind="synthetic", reference="Test fixture only")
    evidence = Evidence(
        evidence_id="e1",
        claim_or_excerpt="Synthetic claim",
        source=source,
        uncertainty="Synthetic; not verified",
        provenance="Deterministic fixture",
        observed_at=datetime.now(UTC),
        retrieved_at=datetime.now(UTC),
    )
    artifacts = (
        ResearchPlan(artifact_id=uuid4(), version=1),
        EvidenceSet(artifact_id=uuid4(), version=1, evidence=(evidence,)),
        AnalysisResult(artifact_id=uuid4(), version=1, findings=("Finding",), evidence_ids=("e1",)),
        DocumentOutline(
            artifact_id=uuid4(),
            version=1,
            sections=(OutlineSection(title="Decision", key_argument="Compare"),),
        ),
        draft,
        ReviewResult(
            artifact_id=uuid4(),
            version=1,
            draft_id=draft.artifact_id,
            decision=ReviewDecision.CHANGES_REQUIRED,
            findings=(critical,),
        ),
    )
    adapter = TypeAdapter(ArtifactPayload)
    for artifact in artifacts:
        assert adapter.validate_json(adapter.dump_json(artifact)) == artifact
        record = ArtifactRecord(
            payload=artifact,
            producer=AttemptReference(stage=Stage.DRAFT, attempt_number=1),
            created_at=datetime.now(UTC),
            consumed_artifact_ids=(uuid4(),),
        )
        assert ArtifactRecord.model_validate_json(record.model_dump_json()) == record
        with pytest.raises(ValidationError):
            artifact.version = 2
    with pytest.raises(ValidationError):
        EvidenceSet(artifact_id=uuid4(), version=1, evidence=(evidence, evidence))


def test_brief_bounds_and_normalization():
    brief = DocumentBrief(
        objective="  Rewrite  ",
        document_type="memo",
        constraints=DocumentConstraints(max_words=100, required_sections=("Decision",)),
    )
    assert brief.objective == "Rewrite"
    assert not brief.permissions.external_research
    assert DocumentBrief.model_validate_json(brief.model_dump_json()) == brief
    for objective in (" ", "x" * 4001, 42):
        with pytest.raises(ValidationError):
            DocumentBrief(objective=objective, document_type="memo")
    with pytest.raises(ValidationError):
        DocumentConstraints(max_words=0)
    with pytest.raises(ValidationError):
        SourceReference(source_id="../bad", reference="Content", kind="supplied")


def test_completed_requires_review_and_checks(draft, critical):
    review = ReviewResult(
        artifact_id=uuid4(), version=1, draft_id=draft.artifact_id, decision=ReviewDecision.ACCEPTED
    )
    completed = ExecutionResult(
        status=Lifecycle.COMPLETED, latest_draft=draft, review=review, mandatory_checks_passed=True
    )
    assert ExecutionResult.model_validate_json(completed.model_dump_json()) == completed
    for changes in (
        {"mandatory_checks_passed": False},
        {"review": None},
        {"latest_draft": None},
        {"error": ExecutionError(code=ErrorCode.BUDGET_EXHAUSTED)},
    ):
        with pytest.raises(ValidationError):
            ExecutionResult.model_validate(completed.model_dump() | changes)
    with pytest.raises(ValidationError):
        ReviewResult(
            artifact_id=uuid4(),
            version=1,
            draft_id=draft.artifact_id,
            decision=ReviewDecision.ACCEPTED,
            findings=(critical,),
        )
    rejected = ReviewResult(
        artifact_id=uuid4(),
        version=1,
        draft_id=draft.artifact_id,
        decision=ReviewDecision.CHANGES_REQUIRED,
        findings=(critical,),
    )
    with pytest.raises(ValidationError):
        ExecutionResult(
            status=Lifecycle.COMPLETED,
            latest_draft=draft,
            review=rejected,
            mandatory_checks_passed=True,
        )
    incomplete = ExecutionResult(
        status=Lifecycle.INCOMPLETE,
        latest_draft=draft,
        review=rejected,
        limitations=("Critical evidence gap remains",),
    )
    assert incomplete.latest_draft == draft
    assert incomplete.review.findings == (critical,)


def test_other_terminal_invariants(draft):
    with pytest.raises(ValidationError):
        ExecutionResult(status=Lifecycle.INCOMPLETE)
    with pytest.raises(ValidationError):
        ExecutionResult(status=Lifecycle.FAILED)
    with pytest.raises(ValidationError):
        ExecutionResult(status=Lifecycle.EXECUTING)
    review = ReviewResult(
        artifact_id=uuid4(), version=1, draft_id=uuid4(), decision=ReviewDecision.ACCEPTED
    )
    with pytest.raises(ValidationError):
        ExecutionResult(status=Lifecycle.INCOMPLETE, latest_draft=draft, review=review)
    failed = ExecutionResult(
        status=Lifecycle.FAILED, error=ExecutionError(code=ErrorCode.PLAN_VALIDATION_FAILED)
    )
    assert failed.latest_draft is None
    assert ExecutionResult.model_validate_json(failed.model_dump_json()) == failed
    assert ExecutionResult(status=Lifecycle.CANCELLED).latest_draft is None


def test_attempt_contract():
    now = datetime.now(UTC)
    attempt = StageAttempt(
        stage=Stage.DRAFT,
        attempt_number=1,
        started_at=now,
        ended_at=now,
        outcome=AttemptOutcome.SUCCEEDED,
        usage=Usage(model_calls=1, tokens=20),
    )
    assert StageAttempt.model_validate_json(attempt.model_dump_json()) == attempt
    with pytest.raises(ValidationError):
        StageAttempt.model_validate(attempt.model_dump() | {"ended_at": now - timedelta(seconds=1)})
    with pytest.raises(ValidationError):
        StageAttempt.model_validate(attempt.model_dump() | {"started_at": now.replace(tzinfo=None)})
    with pytest.raises(ValidationError):
        Usage(tokens=-1)
