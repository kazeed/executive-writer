from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from executive_writer.workflow.models import (
    AnalysisResult,
    ArtifactRecord,
    AttemptReference,
    DocumentDraft,
)
from executive_writer.workflow.repository import ArtifactConflict, InMemoryArtifactRepository
from executive_writer.workflow.stages import Stage


def record(payload=None, sources=(), created_at=None, stage=Stage.DRAFT):
    return ArtifactRecord(
        payload=payload or DocumentDraft(artifact_id=uuid4(), version=1, body="Initial text"),
        producer=AttemptReference(stage=stage, attempt_number=1),
        consumed_artifact_ids=sources,
        created_at=created_at or datetime.now(UTC),
    )


def test_append_snapshot_and_consecutive_versions():
    repository = InMemoryArtifactRepository()
    first = record()
    repository.append(first)
    snapshot = repository.records()
    second = record(
        DocumentDraft(artifact_id=uuid4(), version=2, body="Revised text"),
        sources=(first.payload.artifact_id,),
        stage=Stage.REVISE,
    )
    repository.append(second)
    assert snapshot == (first,)
    assert repository.records() == (first, second)
    with pytest.raises(ValidationError):
        repository.records()[0].payload.body = "Mutated"


@pytest.mark.parametrize(
    "defect",
    [
        "duplicate_id",
        "unknown_input",
        "duplicate_input",
        "version_gap",
        "missing_predecessor",
        "wrong_producer",
        "future_input",
        "unchecked_payload",
    ],
)
def test_reject_invalid_append_atomically(defect):
    repository = InMemoryArtifactRepository()
    first = record()
    repository.append(first)
    second = record(
        DocumentDraft(artifact_id=uuid4(), version=2, body="Second"),
        sources=(first.payload.artifact_id,),
    )
    if defect == "duplicate_id":
        second = second.model_copy(update={"payload": first.payload})
    elif defect == "unknown_input":
        second = second.model_copy(update={"consumed_artifact_ids": (uuid4(),)})
    elif defect == "duplicate_input":
        second = second.model_copy(
            update={"consumed_artifact_ids": (first.payload.artifact_id,) * 2}
        )
    elif defect == "version_gap":
        second = second.model_copy(
            update={"payload": second.payload.model_copy(update={"version": 3})}
        )
    elif defect == "missing_predecessor":
        second = second.model_copy(update={"consumed_artifact_ids": ()})
    elif defect == "wrong_producer":
        second = second.model_copy(
            update={"producer": AttemptReference(stage=Stage.REVIEW, attempt_number=1)}
        )
    elif defect == "future_input":
        second = second.model_copy(update={"created_at": first.created_at - timedelta(seconds=1)})
    elif defect == "unchecked_payload":
        second = second.model_copy(
            update={"payload": second.payload.model_copy(update={"version": True})}
        )
    with pytest.raises(ArtifactConflict):
        repository.append(second)
    assert repository.records() == (first,)


def test_versions_are_per_artifact_kind():
    repository = InMemoryArtifactRepository()
    repository.append(record())
    analysis = AnalysisResult(artifact_id=uuid4(), version=1)
    repository.append(record(analysis, stage=Stage.ANALYZE))
    assert repository.records()[-1].payload == analysis
