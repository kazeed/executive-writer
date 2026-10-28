"""FastAPI application entry point."""

from fastapi import FastAPI

from executive_writer.api.documents import router as documents_router

app = FastAPI(title="Executive Writer", version="0.1.0")
app.include_router(documents_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
