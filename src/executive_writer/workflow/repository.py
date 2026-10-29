"""Append-only artifact port and execution-local memory implementation."""

from typing import Protocol

from pydantic import ValidationError

from executive_writer.workflow.models import ArtifactRecord
from executive_writer.workflow.stages import Stage


class ArtifactConflict(ValueError):
    """Invalid artifact identity, version or provenance; contains no source text."""


class ArtifactRepository(Protocol):
    def append(self, record: ArtifactRecord) -> None: ...

    def records(self) -> tuple[ArtifactRecord, ...]: ...


_PRODUCERS = {
    "research_plan": (Stage.VALIDATE,),
    "evidence_set": (Stage.RESEARCH,),
    "analysis_result": (Stage.ANALYZE,),
    "document_outline": (Stage.OUTLINE,),
    "document_draft": (Stage.DRAFT, Stage.REVISE),
    "review_result": (Stage.REVIEW,),
}


class InMemoryArtifactRepository:
    def __init__(self) -> None:
        self._records: list[ArtifactRecord] = []

    def records(self) -> tuple[ArtifactRecord, ...]:
        return tuple(self._records)

    def append(self, record: ArtifactRecord) -> None:
        try:
            record = ArtifactRecord.model_validate(record)
        except ValidationError as error:
            raise ArtifactConflict("Invalid artifact record") from error
        payload = record.payload
        existing = {item.payload.artifact_id: item for item in self._records}
        if payload.artifact_id in existing:
            raise ArtifactConflict("Artifact IDs cannot be reused")
        if len(set(record.consumed_artifact_ids)) != len(record.consumed_artifact_ids):
            raise ArtifactConflict("Duplicate consumed artifact IDs")
        if any(identifier not in existing for identifier in record.consumed_artifact_ids):
            raise ArtifactConflict("Consumed artifacts must already exist")
        previous = [item for item in self._records if item.payload.kind == payload.kind]
        if payload.version != len(previous) + 1:
            raise ArtifactConflict("Artifact versions must increase consecutively within kind")
        if previous and previous[-1].payload.artifact_id not in record.consumed_artifact_ids:
            raise ArtifactConflict("A new version must consume its preceding version")
        if record.producer.stage not in _PRODUCERS[payload.kind]:
            raise ArtifactConflict("Artifact kind does not match producer stage")
        if any(
            existing[identifier].created_at > record.created_at
            for identifier in record.consumed_artifact_ids
        ):
            raise ArtifactConflict("Artifact cannot precede its inputs")
        self._records.append(record)
