"""Document job placeholder endpoint."""

from uuid import uuid4

from fastapi import APIRouter, status

from executive_writer.models.documents import DocumentRequest, DocumentResponse

router = APIRouter()


@router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
def create_document(request: DocumentRequest) -> DocumentResponse:
    return DocumentResponse(
        document_id=uuid4(),
        status="accepted",
        document_type=request.document_type,
    )
