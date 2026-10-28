# Development and verification

Use Python 3.13 and uv from the repository root:

```bash
uv python install 3.13
uv sync --locked
uv run uvicorn executive_writer.main:app --reload
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

[pyproject.toml](../../pyproject.toml) configures Ruff (`py313`), strict Pyright for `src`,
Bandit targets and a 90% coverage threshold. Runtime dependencies are FastAPI, Pydantic,
pydantic-settings and Uvicorn. FastAPI's standard extras were removed to exclude unused CLI,
cloud and optional server dependencies. Development dependencies remain httpx, pytest and Ruff.
[uv.lock](../../uv.lock) was regenerated with uv, without manual changes.

## Tool installation gap

The implementation environment cannot resolve PyPI, and its cache does not contain Pyright,
pytest-cov, pip-audit or Bandit. They are **not installed or locked development dependencies**.
Once network access is available, finish integration using:

```bash
uv add --dev pyright==1.1.407 pytest-cov==7.0.0 pip-audit==2.9.0 bandit==1.8.6
uv run pyright
uv run pytest -q --cov --cov-report=term-missing --cov-report=xml
```

Then replace the isolated `uvx`/`--with` CI invocations with `uv run` commands. Until then,
`uv run pyright` cannot work in a fresh synced checkout. This is an explicit unfinished
Milestone 2A requirement, not a passing gate. The versions in CI are explicit bootstrap pins;
review available releases and advisories when locking them.

## Local security checks

The [CI workflow](../../.github/workflows/ci.yml) runs these isolated tool commands:

```bash
uv export --locked --no-emit-project --format requirements-txt -o /tmp/audit.txt
uvx pip-audit==2.9.0 -r /tmp/audit.txt --disable-pip --no-deps
uvx bandit==1.8.6 -r src
# Requires Docker; scans full Git history, redacting findings:
docker run --rm -v "$PWD:/repo:ro" ghcr.io/gitleaks/gitleaks:v8.28.0 git --redact --source=/repo
# Also scan current uncommitted source before committing:
docker run --rm -v "$PWD:/repo:ro" ghcr.io/gitleaks/gitleaks:v8.28.0 dir --redact /repo
```

The audit export includes development dependencies and hashes; the local project is omitted
because it is not a published dependency. No advisories or Bandit rules are ignored.
Pip-audit fails on known vulnerabilities; Bandit fails on its default findings; Gitleaks fails
on any detected secrets. Treat infrastructure/download failures as failures, never clean scans.
See official [pip-audit](https://github.com/pypa/pip-audit),
[Bandit](https://bandit.readthedocs.io/), [Pyright](https://github.com/microsoft/pyright),
[Gitleaks](https://github.com/gitleaks/gitleaks) and
[Trivy installation](https://trivy.dev/latest/getting-started/installation/) guidance.
Gitleaks currently receives security maintenance; reassess its successor during tool updates.

## CI

[CI](../../.github/workflows/ci.yml) triggers on PRs to main and pushes to main:

| Job | Gates |
| --- | --- |
| quality | Python 3.13, uv 0.13.6, lock check, locked sync, Ruff lint/format, strict Pyright |
| tests | Locked sync, pytest, coverage threshold and XML artifact |
| security | Locked export audit, Bandit, full-history Gitleaks |
| container | Image build, smoke test, Trivy HIGH/CRITICAL vulnerability gate |

Actions use full commit pins; permissions are contents-read only; checkout does not persist
credentials. No deployment, paid service, application secrets or privileged PR events are used.
Tool transitive dependencies are not yet locked; scanner images use version tags pending digest
resolution. CI has not been executed on GitHub from this task.

## Tests and documentation

Existing API tests are preserved. [Foundation tests](../../tests/test_foundation.py) cover
settings, disabled documentation, safe errors, security headers and absence of CORS grants.
Default tests need neither credentials nor internet. See the
[verification record](../operations/milestone-2a.md) for actual results and blockers.
Apply [project-documentation](../../.agents/skills/project-documentation/SKILL.md) after material
changes; keep [requirements](../requirements.md) separate from implemented behavior.
