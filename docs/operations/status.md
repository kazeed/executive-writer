# Operations and security status

## Runtime configuration

[Settings](../../src/executive_writer/config.py) uses Pydantic Settings, with environment
variables only (no implicit `.env` file). Invalid values fail application construction;
validation errors hide input values. No credentials or unused service settings exist.

| Variable | Default | Behavior |
| --- | --- | --- |
| `EW_ENVIRONMENT` | `development` | Validated `development` or `production` label; does not enable additional controls |
| `EW_DOCS_ENABLED` | `true` | Boolean; false disables Swagger, ReDoc and OpenAPI routes |

The container sets production environment. Docs remain enabled to preserve the milestone's
explicit endpoint requirement. Before external exposure, disable them or protect access.
FastAPI debug is always false. Server host/port are Uvicorn arguments, not application settings.

## Container packaging

[Dockerfile](../../Dockerfile) uses Python 3.13.18 slim Debian trixie in both build and runtime
stages, uv 0.13.6 in the builder, locked noneditable production-only installation, and numeric
UID/GID 10001. Only the virtual environment enters the runtime. Source inputs are allowlisted
by [.dockerignore](../../.dockerignore); Git, local secrets, tests and caches are excluded.
Runtime files are root-owned and cannot be modified by the application user.
There are no added compilers or development tools in the final stage; the upstream Python
image still contains its own runtime utilities. Uvicorn runs directly as PID 1, binds
`0.0.0.0:8000`, ignores proxy headers, disables access/server headers and allows 10 seconds
to shut down after SIGTERM. The Python healthcheck queries local `/health` with a timeout.

```bash
docker build -t executive-writer:local .
docker run --rm --name executive-writer --read-only --cap-drop=ALL \
  --security-opt=no-new-privileges --pids-limit=64 --memory=256m --cpus=1 \
  -p 127.0.0.1:8000:8000 executive-writer:local
docker stop --time 15 executive-writer
bash scripts/container-smoke.sh
docker save executive-writer:local -o /tmp/image.tar
docker run --rm -v /tmp/image.tar:/image.tar:ro aquasec/trivy:0.69.3 image \
  --input /image.tar --scanners vuln --severity HIGH,CRITICAL --exit-code 1
```

Read-only filesystem, capability dropping, no-new-privileges and resource ceilings are runtime
options, not enforceable by a Dockerfile alone. The smoke script applies them and tests health,
document response, documentation, UID, Docker health status and a zero exit after stopping.
The local host port is dynamically assigned to avoid conflicts. Container verification is
**blocked**, not proven; see [results](milestone-2a.md).

Image references are version-pinned, **not digest-pinned**: registry access was unavailable.
Before release, resolve and review multi-platform digests for Python, uv and scanner images,
record them in Dockerfile/workflow, build and scan, then repeat smoke verification. Do not invent
digests. Periodically update pins and rerun all gates to receive OS/Python patches. Hosting
remains undecided and there is no deployment automation.

## Threats, controls and residual gaps

| Threat/boundary | Implemented control and tests | Residual/deployment requirement |
| --- | --- | --- |
| Untrusted JSON | Existing Pydantic document schema; original API tests preserved | No body/text size ceilings yet; gateway and application limits needed before exposure |
| Error disclosure | Validation returns only `loc`/`type`; generic 500 with debug off; foundation tests | Review server exception logging before confidential use; no claim of complete log redaction |
| Browser/cache handling | `nosniff`, DENY framing, no-referrer and no-store on responses; header tests | No blanket CSP because external Swagger/ReDoc assets must work; tailor CSP before browser/public exposure |
| Cross-origin requests | No CORS middleware or grants; negative test | CORS does not authenticate or prevent direct API requests |
| Proxy spoofing | Container disables forwarded-header trust | TLS/HSTS, trusted hosts and precise proxy policy belong to selected deployment; unverified |
| Supply chain | Locked application dependencies; CI scanners fail on findings | Scans blocked locally; dev-tool lock and image digests remain unfinished |
| Container privilege | Numeric non-root user, root-owned environment; smoke checks authored | Actual execution blocked; enforce capability/filesystem/resource options in deployment |
| Identity and abuse | Absent; no sensitive stored resource or expensive integration yet | Authentication, object/function authorization, quotas, rate/concurrency/cost limits before future generation exposure |
| External/LLM/tool use | No integrations or tool execution | SSRF protections, injection boundaries, budgets, cancellation and safe output rendering needed when added |
| Persistence | Absent; UUID/202 do not establish a job | Ownership, encryption, retention, deletion and recovery required before storing content |

No OWASP certification or public-production readiness is claimed. Before release, verify TLS,
headers/CSP, proxy/host policy, access controls, scanning gates, incident/rotation procedures,
monitoring, tested image digest, rollback and data lifecycle where applicable. Mark these
infrastructure-owned or blocked until verified in the chosen environment.

## M2B P1 internal planning boundary

**Implemented:** strict bounded immutable contracts; deterministic stage/dependency
validation; research permission intersection with trusted policy; ceiling checks;
safe typed planning diagnostics. [P1 tests and verification](../architecture/milestone-2b-p1.md)
cover malicious planner fields, excessive budgets and unauthorized research.
No LLM, network, artifact persistence or workflow execution is introduced. Runtime
budget consumption, cancellation, retries, artifact retention and review routing
remain **planned**. Existing public API protection gaps above remain applicable.
