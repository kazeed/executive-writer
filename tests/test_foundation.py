import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from executive_writer.config import Settings
from executive_writer.main import create_app


def test_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EW_ENVIRONMENT", "production")
    monkeypatch.setenv("EW_DOCS_ENABLED", "false")
    settings = Settings()
    assert settings.environment == "production"
    assert settings.docs_enabled is False
    client = TestClient(create_app(settings))
    for path in ("/docs", "/openapi.json", "/redoc"):
        assert client.get(path).status_code == 404
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize(
    ("name", "value"), [("EW_ENVIRONMENT", "invalid"), ("EW_DOCS_ENABLED", "invalid")]
)
def test_invalid_settings(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError) as error:
        Settings()
    assert "input_value" not in str(error.value)


@pytest.mark.parametrize("path", ["/health", "/docs", "/openapi.json", "/missing"])
def test_headers(path: str) -> None:
    response = TestClient(create_app(Settings())).get(
        path, headers={"Origin": "https://example.org"}
    )
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert "access-control-allow-origin" not in response.headers


def test_validation_redacts_input() -> None:
    response = TestClient(create_app()).post(
        "/documents", json={"objective": "Confidential material", "document_type": "private-value"}
    )
    assert response.status_code == 422
    assert "private-value" not in response.text
    assert "Confidential" not in response.text


def test_internal_error() -> None:
    app = create_app()

    @app.get("/failure")
    def failure() -> None:
        raise RuntimeError("Confidential internal detail")

    response = TestClient(app, raise_server_exceptions=False).get("/failure")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers["cache-control"] == "no-store"
