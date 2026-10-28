# Operations and security status

## Current operating model

This checkout supports local development only. There is no Dockerfile, `.dockerignore`, deployment
manifest or CI workflow. OCI packaging is an [approved direction](../adr/0001-oci-packaging.md),
not an available build procedure. Hosting is undecided.

[Application code](../../src/executive_writer/main.py) has no settings loader or application-specific
environment variables. Title/version are literals. Server host/port are controlled through the
Uvicorn invocation; see the [development guide](../development/guide.md). No provider credentials
are currently needed. [.gitignore](../../.gitignore) excludes `.env`; this is not secret scanning
or proof that credentials cannot be committed.

## Controls and gaps

Statuses below describe this repository, not a verified deployment.

| Concern | Status | Evidence and limitation |
| --- | --- | --- |
| Input boundary | Implemented | [Pydantic models](../../src/executive_writer/models/documents.py) enforce required fields, types, document types and nonblank objective; no application length/body limits |
| Authentication/authorization | Planned; absent | No identity, ownership or permission checks in [routes](../../src/executive_writer/api/documents.py); no user/tenant isolation |
| API abuse controls | Planned; absent | No rate limits, quotas, concurrency budgets or gateway configuration |
| HTTP protections | Deployment-dependent; unverified | No configured TLS, trusted-host/proxy policy, CORS middleware, security headers or sensitive-response cache policy; public deployment requires explicit configuration and verification |
| API documentation exposure | Implemented | FastAPI defaults expose schema and interactive documentation; no access controls |
| External network/resources | No application integration | Handlers do not fetch URLs or access external services; SSRF protection is not implemented or established by this absence |
| LLM/tool execution | Planned; absent | No provider or tools, prompts, workflow execution or model budgets; requirements do not create runtime controls |
| Persistence/background work | Absent | No storage or workers; UUID/202 acceptance has no durable job semantics |
| Dependencies | Implemented lockfile | [uv.lock](../../uv.lock) records resolved dependencies; no configured vulnerability scan or evidence of vulnerability-free dependencies |
| Container security | Planned | No container image/build to inspect; non-root runtime and image scanning remain future work |
| Logging/sensitive data | Unverified beyond source inspection | No application logging setup, correlation IDs or redaction; framework/server logs and validation error payloads need review before sensitive use |

[Tests](../../tests/test_api.py) exercise a limited set of input failures and response contracts.
They do not verify authorization, resource-exhaustion resistance, log redaction or deployed network
controls. No OWASP compliance or production-readiness claim follows from these checks.

## Before public exposure

[AGENTS.md](../../AGENTS.md) requires appropriate authentication/authorization, request and cost
limits, abuse controls, safe errors/logging, HTTPS, precise proxy trust, security headers and
deployment verification. Their control locations and verification remain to be established when
exposure is scoped. Data retention, encryption and deletion need decisions before user content or
credentials are persisted. Provider, job lifecycle, storage and hosting choices remain open in
[requirements](../requirements.md). No public deployment has been verified for this baseline.
