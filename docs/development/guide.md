# Development and verification

## Environment

Run commands from the repository root. The selected interpreter is Python 3.13 in
[.python-version](../../.python-version); [pyproject.toml](../../pyproject.toml) declares
`requires-python = ">=3.13"`. This lower bound does not demonstrate testing on every newer version.
Use uv for dependency and environment management.

```bash
uv python install 3.13
uv sync --locked
uv run uvicorn executive_writer.main:app --reload
```

The development server defaults to loopback port 8000. Check `/health` or visit `/docs`.
The reload server is a local development command, not a production deployment procedure.

## Dependencies and layout

`pyproject.toml` declares runtime dependencies `fastapi[standard]>=0.162.0` and
`pydantic>=2.14.1`. The build backend is `uv_build>=0.13.6,<0.14.0`.
Development dependencies are httpx, pytest and Ruff. [uv.lock](../../uv.lock) pins the resolved
dependency set; installed transitive libraries do not imply application integrations.

- `src/executive_writer/main.py`: ASGI entry point.
- `src/executive_writer/api/`: route handlers.
- `src/executive_writer/models/`: Pydantic request/response models.
- `tests/test_api.py`: synchronous FastAPI TestClient API tests.

## Checks and tested scope

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Ruff targets `py313`, uses a 100-character line length and selects `E`, `F`, `I`, `B`, `UP`.
The [test suite](../../tests/test_api.py) contains 12 cases after parametrization:
one health case, six valid requests (three types, with/without optional fields), and five invalid
requests. Valid cases check status, UUID v4 and complete response shape. Invalid cases check
status and error location. Tests do not require live providers or internet access.

No coverage measurement, strict type checker, CI workflow, SAST, dependency audit or secret-scanning
configuration exists in this checkout. Those are engineering goals, not active gates.
See [AGENTS.md](../../AGENTS.md) for conventions and required checks.

## Documentation maintenance

Apply [project-documentation](../../.agents/skills/project-documentation/SKILL.md) after material
changes to interfaces, behavior, dependencies or architecture. Keep product intent in
[requirements](../requirements.md) separate from current implementation. Report discrepancies
rather than silently altering requirements. Update only affected pages and documentation links.
