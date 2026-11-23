# Implementation Status

**Audit date:** 2026-11-22. Status describes checked-in code, not deployment.

Legend: **Present** = source exists; **Partial** = some behavior exists but
does not satisfy the full requirement; **Missing** = not implemented or not
found; **Unverified** = code declares it but it has not been run against the
target environment.

## Documentation and coordination

| Area | Status | Evidence / notes |
|---|---|---|
| README / local demo | Partial | `README.md`; short instructions, but browser start commands precede frontend dev-server start |
| Existing architecture/decisions/deploy/defense docs | Present, brief | `docs/architecture.md`, `docs/decisions.md`, `docs/deployment.md`, `docs/defense-guide.md` |
| Existing reference summary | Partial | `docs/reference-analysis.md`; short summary only |
| Detailed architecture, UI, GraphQL, SAGA, traceability docs | Created in this documentation task | See `docs/` |
| Project coordination and prompt | Created in this documentation task | See `project-management/`, `prompts/frontend/`, `AGENTS.md` |

## Frontend

| Capability | Status | Evidence / gap |
|---|---|---|
| React + TypeScript + Vite | Present | `frontend/` |
| Overview, station list, wallet, flags, SAGA summary | Present | Four navigable screens, polling, loading/error/stale states, and responsive CSS |
| Environment selector | Partial | Dev uses `/graphql` through Vite proxy on host 8010; test/prod fail closed because no real endpoints exist |
| Station/connector selection | Present | Real station and connector IDs are selected; request is disabled for non-available connectors |
| Reservation/charge/activation form | Present | Declares exact GraphQL variables, validates positive amount, preserves idempotency key after network uncertainty |
| SAGA history and retry | Present with contract limits | Summary table and guarded `COMPENSATION_FAILED` retry; detail/timeline/pagination remain unavailable |
| Dev session cleanup | Present | `stopAndRelease` GraphQL mutation stops dispatch and releases the reservation in dev; it does not refund an already completed charge |
| Feature-flag display | Present | Read-only official flag names and enabled/disabled values |
| Telemetry | Present | Latest returned snapshot is labeled as non-historical |
| Responsive/accessibility system | Present | Responsive breakpoints, focus styles, semantic labels, table scroll, status text, and reduced-motion handling |
| Loading/empty/error/success/compensation states | Present | Dedicated query and mutation outcomes are surfaced; stale/error behavior remains per refresh |
| Frontend tests | Present | Vitest tests cover environment fail-close behavior and GraphQL route guards |
| Vite/API CORS or proxy | Present | Vite proxies relative `/graphql` to `http://localhost:8010/graphql`; no browser calls to REST service ports |

## Backend and GraphQL

| Capability | Status | Evidence / gap |
|---|---|---|
| FastAPI services for station, billing, dispatch | Present | `services/*/app.py` |
| Strawberry GraphQL gateway | Present | `gateway/app.py` |
| SAGA forward order | Present with limits | Reserve -> debit -> activate; persisted step state and same-key resume after uncertain outcomes |
| Compensation | Present with limits | Refund then release; checks downstream status; incomplete work remains retryable |
| Idempotency | Present with limits | Conditional SAGA create, payload fingerprint, execution lease, and service idempotency |
| Station availability lock | Present for demo catalog | Conditional connector lock and recoverable reservation/release states; inventory remains one hard-coded station/connector |
| Atomic wallet/ledger effects | Present | Wallet balance and charge/refund records use DynamoDB transactions; duplicate refunds are idempotent |
| Official environment feature flags | Partial | Three official names are read-only process values; hardware fault injection is gated; pricing/boost behavior is not implemented |
| SAGA detail/event history | Partial | Steps and compensation events persist on SAGA item; current GraphQL type exposes summary only |
| Telemetry | Partial | Activation and baseline telemetry persist together, and stop updates both; no hardware measurements or history contract |
| GraphQL live updates | Missing | No subscriptions/SSE/WebSocket |
| GraphQL CORS | Missing/unverified | No gateway middleware found |

Exact operation list and contract gaps: `docs/GRAPHQL_CONTRACTS.md`.

## Infrastructure, operations, and governance

| Capability | Status | Evidence / gap |
|---|---|---|
| Dockerfiles and Compose | Present, unverified end-to-end | Compose defines Floci, three services, gateway; no frontend service |
| Terraform bootstrap / workspaces / modules | Improved, not deployment-ready | Root and bootstrap validate locally; one shared state-bucket pattern and environment keys, fixed cluster naming, required EKS admin input, and normalized CloudWatch paths are present. Real account/region/state values and live AWS planning remain blocked. |
| EKS/ECR | Partial | Private EKS API, managed node group, ECR repositories, explicit authentication mode/access entries, Pod Identity and CloudWatch add-ons are declared; the real admin ARN and AWS runtime are unverified. |
| Kubernetes workloads | Present, locally rendered | Gateway plus three backend Deployments, four ClusterIP Services, ConfigMap, Namespace, ServiceAccounts, probes, resource bounds, and hardened container security contexts remain in root `k8s/` manifests |
| Kubernetes environment overlays | Present, locally rendered | `k8s/overlays/{dev,test,prod}` set environment labels, environment tables, ECR paths, image SHA placeholder, service-account role ARN placeholders, and replica counts; locally asserted, no deployment has been performed |
| Kubernetes canary routing | Partial / not deployed | Existing canary Ingress remains outside the root Kustomize graph; no verified stable/canary workloads, router, or request-level analysis is configured |
| Kubernetes private API integration | Partial | Private REST API, execute-api VPC endpoint and source-VPCE resource policy exist in Terraform; internal ALB Ingress and optional VPC Link integration are declared. LBC installation and ALB output are pending. |
| Kubernetes CI rendering | Present, locally rendered | Root validation retains `Path("k8s").glob("*.yaml")`; CI renders each overlay and adds pinned Kubeconform validation. Kubeconform was not run locally. |
| Kubernetes log forwarding | Declared, not runtime-verified | CloudWatch Observability add-on with Fluent Bit and retained log groups is in Terraform; no deployed collector evidence. |
| Prefect | Partial, implemented source updated in Phase 4 | Explicit three-environment private health checks, paginated SAGA/service scans, consistency summaries, and CloudWatch metrics exist; Prefect runtime IAM/network/dashboard remain unconfigured. |
| PR CI | Partial | pytest, frontend build, Terraform fmt/init/validate, Compose config; no integration/E2E/plan/lint pipeline |
| Environment promotion | Missing/partial | Push-based jobs do not enforce linear PR promotion and conditions require review |
| Branch protection helper | Partial | Script only prints a suggested GitHub command; it does not configure protection |
| Tests | Partial | Moto-backed service + GraphQL HTTP integration tests; no Docker/Floci/live AWS or browser E2E |
| AWS deployment | Not claimed | No evidence resources have been applied; Terraform was unavailable in earlier validation |

## Phase 0 baseline verification (2026-11-20)

| Check | Exact result |
|---|---|
| Git worktree | `git rev-parse --show-toplevel` and `git status --short --branch` failed with `fatal: not a git repository`; `.git` is absent. Uncommitted changes cannot be distinguished from the baseline. |
| Compose parse | `docker compose config --quiet` exited 0. |
| Docker CLI | Docker 28.5.2; Compose v2.40.3-desktop.1. |
| Docker engine | `docker info` and `docker compose ps -a` could not connect to `//./pipe/dockerDesktopLinuxEngine`. `docker compose up --build -d` failed with the same engine connection error while resolving the local billing image. The stack was not started. |
| Listening services | `Test-NetConnection` reported ports 8000, 8001, 8002, 8003, and 4566 all closed at inspection time. |
| Backend tests | Python 3.12.10; `python -m pytest -q`: 5 passed, 22 deprecation warnings, exit 0. |
| GraphQL introspection | Temporary Uvicorn gateway at `127.0.0.1:8000` with Moto; HTTP POST `/graphql` introspection returned 200, no GraphQL errors, roots `Query` and `Mutation`. Temporary gateway stopped. |
| Feature flags operation | HTTP query returned `canaryCharge=true` and `chargerFaultSimulation=false` with defaults. Changing process environment values changed the next query; no flag mutation exists. |
| Current frontend mutation | GraphQL validation against actual Strawberry schema returned `Variable '$station' is not defined` and `Variable '$key' is not defined`. |
| SDL snapshot | Saved at `docs/graphql/schema.graphql`; retrieved through introspection. It describes schema only, not downstream resolver readiness. |

The ASGI gateway introspection and flag query used Moto for its DynamoDB
startup table. They did not validate Docker networking, Floci, or calls to the
three downstream services. The SDL and contract document distinguish this
limited verification from a full local deployment.

## Phase 1 backend correctness verification (updated 2026-11-22)

| Check | Exact result |
|---|---|
| Pre-change baseline | `python -m pytest -q`: 5 passed, 22 deprecation warnings. |
| Full post-change suite | `python -m pytest -q`: **16 passed, 367 warnings**, exit 0. |
| 2026-11-22 revalidation | `python -m pytest -q -o faulthandler_timeout=15`: **20 passed, 367 warnings**, exit 0. |
| Replay reproducibility | Independent replay test: 1 passed. 20 separate pytest processes: **20 passed, 0 failed**. |
| Phase 1 report | `docs/PHASE_1_BACKEND_REPORT.md` records baseline, Windows diagnosis, test evidence, limitations, and blockers. |
| GraphQL and service integration | Tests use the actual Strawberry/FastAPI apps and route HTTP calls through in-process ASGI transports; DynamoDB operations use Moto. This is not Docker, Floci, or live AWS verification. |
| Compose syntax | `docker compose config --quiet`: passed after adding `ENVIRONMENT=dev` and official flag variables. |
| Compose runtime | Not started in Phase 1; the Phase 0 attempt was blocked by the unavailable Docker Desktop Linux engine. |
| Frontend | No frontend source was modified. The existing frontend mutation/configuration gaps remain. |
| Infrastructure | No Terraform, AWS, or Kubernetes operation was run. |

## Phase 2 Terraform readiness verification (2026-11-22)

| Check | Exact result |
|---|---|
| Terraform formatting | `terraform fmt -check -recursive`: passed |
| Root initialization | `terraform init -backend=false -input=false`: passed |
| Root validation | `terraform validate -no-color`: passed |
| Development tfvars | `terraform validate -no-color -var-file='envs/dev.tfvars'`: passed local validation |
| Bootstrap initialization | `terraform init -backend=false -input=false`: passed |
| Bootstrap validation | `terraform validate -no-color`: passed |
| Remote backend, plan, and apply | Not initialized or executed |
| AWS resources | No API call or resource mutation was performed |

The 16 tests cover full charging, insufficient balance, gated hardware-fault
compensation, failed compensation and retry, sequential/concurrent duplicate
SAGA requests, changed-payload conflict, concurrent connector reservations,
charge/refund idempotency, dispatch stop/telemetry state, lost charge responses
with same-key recovery, official flag values/validation, and environment table
isolation checks. The 367 warnings are deprecations from botocore UTC time,
Starlette/AnyIO, the existing FastAPI `on_event` startup hooks, and the
pytest-asyncio fixture-loop-scope configuration.

## Environment and flags verified

- Compose has only one GraphQL gateway (`8000/graphql`) and the three REST
  service ports (`8001` station, `8002` billing, `8003` dispatch); Floci is
  `4566`. No test/prod GraphQL endpoint is configured.
- Each service defaults `ENVIRONMENT` to `dev`; Compose explicitly sets `dev`
  and uses dev table names. Default table names derive from that environment;
  configured names are rejected unless they contain its exact token. The three Terraform `.tfvars` files are
  identical and the three backend HCL files contain `CHANGE_ME` bucket names.
  None demonstrates working test/prod isolation.
- Frontend source points at ports 8002/8003 as GraphQL defaults, which is
  incorrect. `.env.example` instead documents `VITE_GRAPHQL_URL`; the helper
  reads `VITE_GRAPHQL_DEV_URL`, `VITE_GRAPHQL_TEST_URL`, and
  `VITE_GRAPHQL_PROD_URL`. Vite's relative `/graphql` proxy targets the local
  gateway but the helper's absolute default bypasses it.
- The gateway exposes `ENABLE_DYNAMIC_SURGE_PRICING`,
  `ENABLE_FAST_CHARGE_BOOST`, and `SIMULATE_CHARGER_HARDWARE_FAULT` as
  read-only process configuration, all false by default. Local Compose passes
  these values to the dev gateway. Hardware fault injection requires both the
  flag and the existing per-request `chargeFault` input. Pricing/boost
  behavior and persistent flag management are not implemented.

## Phase 1 limitations requiring follow-up

- The course DOCX was not found inside the repository or persisted reference
  files during this phase. The exact official flag names came from the
  user-authorized task; no surge formula or boost rules were inferred.
- Local test/prod GraphQL gateways and data stores remain unavailable. Runtime
  separation depends on deployments setting distinct environment variables
  and tables; only the dev Compose configuration exists.
- SAGA recovery is retry-driven, not a background worker. Its execution lease
  is 120 seconds and its event list shares the DynamoDB item, which is subject
  to DynamoDB's 400 KB item limit.
- The station catalog and wallet initialization remain demo scaffolding.
  GraphQL `amount` is still a Float and billing remains USD; pricing and
  currency semantics need an approved contract.
- `FeatureFlag` returns process configuration but does not indicate whether a
  configured surge/boost behavior has a corresponding implementation.

## Existing files inventory

Top-level source/docs present: `README.md`, `requirements.txt`,
`docker-compose.yml`, `.gitignore`, `.github/workflows/{pr,deploy}.yml`,
`common/dynamodb.py`, `gateway/app.py`, `services/`, `frontend/`, `infra/`,
`k8s/`, `observability/prefect/audit_flow.py`, `scripts/`, `tests/`, and
`docs/`.

Existing docs before this audit: `docs/architecture.md`,
`docs/decisions.md`, `docs/defense-guide.md`, `docs/deployment.md`, and
`docs/reference-analysis.md`. The lowercase architecture file is the existing
Windows path completed as the requested `docs/ARCHITECTURE.md`; Windows is
case-insensitive.

Generated/local material observed in the tree includes `frontend/node_modules`,
`frontend/dist`, `frontend/tsconfig.tsbuildinfo`, `.pytest_cache`, and
`__pycache__`. These are not source-of-truth and must not be used as evidence
of completeness.

## Phase 4 infrastructure and observability (2026-11-23)

| Capability | Status | Evidence / gap |
|---|---|---|
| Private GraphQL API | Implemented in Terraform, integration gated | Private REST API, execute-api endpoint/policy and optional REST VPC Link integration are declared. Actual ALB and AWS behavior are not verified. |
| Internal GraphQL ALB ingress | Implemented in manifests, controller pending | Internal `ingressClassName: alb` routes `/graphql`, health target `/health`; AWS LBC IAM role/chart/controller are not installed. |
| EKS authentication | Implemented in Terraform, user configuration required | Kubernetes 1.37 and `API_AND_CONFIG_MAP`; at least one valid EKS administrator ARN is required. |
| Application IAM | Implemented in Terraform | IRSA trust is service-account scoped and DynamoDB actions map to observed calls; no AWS Access Analyzer/live validation. |
| CloudWatch pod logs | Declared in Terraform, AWS validation required | CloudWatch Observability and Pod Identity add-ons plus retained log groups are declared; no deployed collector evidence. |
| JSON request logs | Implemented in source | FastAPI middleware writes method/path/status/duration/environment/service/correlation JSON without bodies; no live CloudWatch parsing evidence. |
| Prefect audit | Implemented in source, runtime config required | Configured health probes for four workloads in dev/test/prod, paginated DynamoDB audits, compensation summaries and metrics; no Prefect runner IAM/network/dashboard. |
| Kubernetes schemas | Implemented in CI, not run locally | Kubeconform v0.8.0 image digest validates root and dev/test/prod render against Kubernetes 1.37. |

Targeted remediation and infrastructure readiness addendum: `docs/PHASE_4_REMEDIATION_READINESS.md`.
Detailed gaps, validation results, decisions, and required values: `docs/PHASE_4_INFRASTRUCTURE_OBSERVABILITY_REPORT.md`.
