# Milestone 2A verification record

Working-tree implementation on 2026-10-28; no commits, pushes, deployment or CI runs performed.
**Milestone incomplete:** required development tools cannot be installed/locked in this sandbox,
full tests hang, and container/scanner verification is blocked. No clean security result is claimed.

uv's normal cache is read-only here. Checks used `UV_CACHE_DIR=/tmp/ew-uv`, populated from the
existing cache, and uv-managed Python 3.13.18. This changes no repository dependency policy.

| Exact command (with writable cache prefix for uv) | Result |
| --- | --- |
| `uv sync --locked` | Passed |
| `uv lock --check` | Passed |
| `uv run ruff check .` | Passed after formatting |
| `uv run ruff format --check .` | Passed |
| `uv run pyright` | Blocked: executable absent; network DNS unavailable and package not cached |
| `uv run pytest -q` | Stalled on first original TestClient health request; no passing suite result |
| `timeout 25s env UV_CACHE_DIR=/tmp/ew-uv uv run pytest -q -o faulthandler_timeout=10` | Timeout; stack waits in AnyIO thread portal / event loop |
| `uv run pytest -q tests/test_foundation.py -k invalid_settings` | 2 passed, 7 deselected; one Starlette httpx deprecation warning |
| `uv export --locked --no-emit-project --format requirements-txt -o /tmp/ew-audit.txt` | Passed |
| `UV_TOOL_DIR=/tmp/ew-tools uvx --offline pip-audit==2.9.0` | Blocked: tool absent from cache; online install also failed DNS |
| `UV_TOOL_DIR=/tmp/ew-tools uvx --offline bandit==1.8.6 -r src` | Blocked: tool absent from cache |
| `docker build -t executive-writer:local .` | Blocked: buildx config read-only; repeat with `DOCKER_CONFIG=/tmp/ew-docker` reached daemon permission denial |
| `docker run --rm -p 127.0.0.1:8000:8000 executive-writer:local` | Blocked: Docker socket permission denied |
| `bash scripts/container-smoke.sh` | Blocked: Docker socket permission denied |
| Gitleaks / Trivy Docker invocations in operations guide | Blocked: Docker socket permission denied |
| `bash -n scripts/container-smoke.sh` | Passed |
| `git diff --check` | Passed |
| TOML parsing and `app.openapi()` assertions for `/health`, `/documents` | Passed; not an HTTP smoke test |

CI YAML has been inspected, but no actionlint or workflow execution was available. Coverage was
not measured. API route behavior and graceful container termination remain unverified here.
Do not bypass sandbox restrictions. Re-run all gates in a network-enabled authorized development
environment with Docker access; investigate TestClient hanging before accepting the milestone.

## Remaining engineering acceptance work

1. Install and lock Pyright, pytest-cov, pip-audit and Bandit with uv; make `uv run pyright` work
   and use locked tools in CI. Fix all actual strict diagnostics; checking is configured but unrun.
2. Resolve immutable registry digests; review scanner versions and action pins against upstream.
3. Execute full tests, coverage, audits, secret/image scans, build and smoke checks. Investigate
   findings rather than adding blanket suppressions. No vulnerability exceptions were added.
4. Validate CI with actionlint and a real GitHub run. Protect main with required checks once scoped.
5. Complete the deployment prerequisites in [security status](status.md) before public exposure.
