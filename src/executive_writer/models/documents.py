"""Request and response models for document jobs."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator

type DocumentType = Literal["memo", "report", "briefing"]


class DocumentRequest(BaseModel):
    objective: str
    document_type: DocumentType
    audience: str | None = None
    context: str | None = None
    instructions: str | None = None

    @field_validator("objective")
    @classmethod
    def validate_objective(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("objective must not be blank")
        return value


class DocumentResponse(BaseModel):
    document_id: UUID
    status: Literal["accepted"]
    document_type: DocumentType
