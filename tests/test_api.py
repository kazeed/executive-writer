from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from executive_writer.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("document_type", ["memo", "report", "briefing"])
@pytest.mark.parametrize("include_optional", [False, True])
def test_valid_document(document_type: str, include_optional: bool) -> None:
    payload = {"objective": "Summarize quarterly results", "document_type": document_type}
    if include_optional:
        payload.update(
            audience="Executive team",
            context="Revenue increased this quarter.",
            instructions="Keep the document concise.",
        )

    response = client.post("/documents", json=payload)

    assert response.status_code == 202
    body = response.json()
    assert UUID(body["document_id"]).version == 4
    assert body == {
        "document_id": body["document_id"],
        "status": "accepted",
        "document_type": document_type,
    }


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"document_type": "memo"}, "objective"),
        ({"objective": "", "document_type": "memo"}, "objective"),
        ({"objective": " \t\n", "document_type": "memo"}, "objective"),
        ({"objective": "Summarize results", "document_type": "email"}, "document_type"),
        ({"objective": "Summarize results"}, "document_type"),
    ],
)
def test_invalid_document(payload: dict[str, str], field: str) -> None:
    response = client.post("/documents", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", field]
