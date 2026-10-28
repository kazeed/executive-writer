# Refresh version pins and resolve immutable registry digests before a release.
FROM python:3.13.18-slim-trixie AS base
FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable --compile-bytecode

FROM base AS runtime
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 EW_ENVIRONMENT=production
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD ["/app/.venv/bin/python", "-c", "import urllib.request; r = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2); assert r.status == 200"]
STOPSIGNAL SIGTERM
CMD ["uvicorn", "executive_writer.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-server-header", "--no-access-log", "--timeout-graceful-shutdown", "10"]
