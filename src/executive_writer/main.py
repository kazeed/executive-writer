"""FastAPI application entry point."""

from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from executive_writer.api.documents import router as documents_router
from executive_writer.config import Settings


class SecurityHeaders:
    """Apply headers at ASGI send, including framework-generated error responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"cache-control", b"no-store"),
                    ]
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


def health() -> HealthResponse:
    return HealthResponse()


def validation_error(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        return internal_error(_request, exc)
    # Input and validator context can contain confidential text or exception objects.
    details = [{"loc": error["loc"], "type": error["type"]} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": details})


def internal_error(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers={
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "no-store",
        },
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()
    application = FastAPI(
        title="Executive Writer",
        version="0.1.0",
        debug=False,
        docs_url="/docs" if config.docs_enabled else None,
        redoc_url="/redoc" if config.docs_enabled else None,
        openapi_url="/openapi.json" if config.docs_enabled else None,
    )
    application.add_middleware(SecurityHeaders)
    application.add_exception_handler(RequestValidationError, validation_error)
    application.add_exception_handler(Exception, internal_error)
    application.include_router(documents_router)
    application.add_api_route("/health", health, response_model=HealthResponse, methods=["GET"])
    return application


app = create_app()
