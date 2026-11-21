# Implementation Status

**Audit date:** 2026-11-20. Status describes checked-in code, not deployment.

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
| Overview, station list, wallet, flags, SAGA summary in one screen | Partial | `frontend/src/main.tsx`; no screen navigation; static/simple layout |
| Environment selector | Partial | Buttons exist, but local stack has only one gateway; test/prod defaults point to service REST ports |
| Station/connector selection | Partial | Selection is by station id, connector hard-coded as `c-1` |
| Reservation/charge/activation form | Failing | GraphQL variables are undeclared in the operation; no request error state |
| SAGA history and retry | Partial | Summary list exists; detail/events/compensation outcomes absent; retry errors not surfaced |
| Feature-flag display | Partial | Read-only and not official flag names or independent stored environments |
| Telemetry | Missing from UI | Gateway query exists but UI does not consume it |
| Responsive/accessibility system | Missing/partial | No breakpoints, focus system, or complete semantic states |
| Loading/empty/error/success/compensation states | Missing/partial | One message string; no robust per-query/per-mutation state |
| Frontend tests | Missing | `npm test` exists but no frontend test source was found |
| Vite/API CORS or proxy | Partial | Vite proxies relative `/graphql` to localhost:8000, but helper uses absolute URLs and bypasses it; gateway has no CORS middleware |

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
| Terraform bootstrap / workspaces / modules | Partial | Modules exist; private subnets, VPC endpoints and API integration missing; bootstrap creates one supplied bucket while per-env backend HCL names three `CHANGE_ME` buckets |
| EKS/ECR | Partial | EKS and repositories declared; no node group/full app workloads |
| Kubernetes stable/canary | Partial | Only gateway manifests; canary ingress lacks a checked-in base ingress; script checks health/restarts, not required CloudWatch/traffic gates |
| Prefect | Partial | One gateway health check + SAGA counts; no three-environment cross-table audit |
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

## Phase 1 backend correctness verification (2026-11-20)

| Check | Exact result |
|---|---|
| Pre-change baseline | `python -m pytest -q`: 5 passed, 22 deprecation warnings. |
| Full post-change suite | `python -m pytest -q`: **16 passed, 367 warnings**, exit 0. |
| GraphQL and service integration | Tests use the actual Strawberry/FastAPI apps and route HTTP calls through in-process ASGI transports; DynamoDB operations use Moto. This is not Docker, Floci, or live AWS verification. |
| Compose syntax | `docker compose config --quiet`: passed after adding `ENVIRONMENT=dev` and official flag variables. |
| Compose runtime | Not started in Phase 1; the Phase 0 attempt was blocked by the unavailable Docker Desktop Linux engine. |
| Frontend | No frontend source was modified. The existing frontend mutation/configuration gaps remain. |
| Infrastructure | No Terraform, AWS, or Kubernetes operation was run. |

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
