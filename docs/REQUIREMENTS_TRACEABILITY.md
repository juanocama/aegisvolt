# Requirements Traceability

**Authority:** `Proyecto Final - Patrones Arquitectónicos Avanzados (AegisVolt).docx`.
Status reflects repository inspection on 2026-11-20. `Partial` means code exists
but does not demonstrate the complete requirement; `Missing` means not found;
`Unverified` means a declaration exists but execution has not been demonstrated.

| ID | Official requirement | Current evidence | Status | Gap / next validation |
|---|---|---|---|---|
| REQ-BIZ-01 | EV fleet charging platform; reserve, authorize funds, activate energy, audit telemetry | Three FastAPI services and GraphQL gateway; activation and simulated telemetry state persist | Partial | Business models remain demo-level; telemetry is not measured hardware data and has no timestamp/history; run against local stack |
| REQ-UI-01 | Real-time station and connector status | UI polls every 4 s; real station data, connector-lock state, and telemetry snapshot are displayed | Partial | Polling is not push live data; only one hard-coded station/connector exists and there is no telemetry history |
| REQ-UI-02 | UI flow to reserve and activate charge | Four-screen UI sends the exact reserve mutation with a real selected connector, positive amount validation, and idempotency-key retention | Present for contract | Hardware fault remains dev-only demo input; session stop and reservation-only flows remain unimplemented |
| REQ-UI-03 | Show feature flags for selected environment | Read-only official flags are displayed from the GraphQL gateway | Partial | Only local `dev` is provisioned; no test/prod endpoints or flag mutation; pricing/boost flags do not yet change behavior |
| REQ-UI-04 | Show transaction history and compensations | SAGA summary table and guarded `COMPENSATION_FAILED` retry are integrated | Partial | No event timeline, compensation attempt counts, filtering, sorting, pagination, or timestamps |
| REQ-BE-01 | Unified GraphQL API: station/telemetry queries and reservation/payment/session mutations | Strawberry gateway has station, telemetry, wallet, flags, SAGA queries, charge activation/retry, and dev stop/release mutations | Partial | No flag mutation or production session stop/compensation contract; query fields lack paging/detail |
| REQ-BE-02 | At least three independent Dockerized services deployed on Kubernetes | Three service Dockerfiles; EKS and gateway K8s manifests | Partial | Only gateway is represented in checked-in K8s workload; no complete app deployment verified |
| REQ-FLAG-01 | Independent environment feature flags for surge, fast-charge boost, simulated hardware fault | Exact official names are read-only process values; hardware-fault request injection is gated by the corresponding flag | Partial | Local Compose is dev only; no persisted flag control plane; surge/boost behavior needs approved rules |
| REQ-SAGA-01 | Reserve -> debit -> activate across three services | Gateway orchestrates all three; step state is persisted; service operations are idempotent | Partial | Moto/in-process integration passes, but Docker/Floci/AWS end-to-end behavior remains unverified |
| REQ-SAGA-02 | On activation failure refund then release connector | Refund is confirmed before release; failure and pending compensation are persisted; retry is state-guarded | Partial | Event log is stored on the SAGA item but not exposed through GraphQL; no background recovery worker |
| REQ-SAGA-03 | On insufficient funds release reservation | HTTP 402 is treated as a business failure; release must return confirmed `cancelled` before SAGA becomes compensated | Partial | Real downstream runtime is not available in this environment |
| REQ-IAC-01 | Terraform modules for cloud infrastructure | Root modules and bootstrap exist | Partial | Modules are minimal; Terraform executable unavailable during prior verification; validate and plan before claim |
| REQ-IAC-02 | S3 remote state with versioning/backups | Bootstrap defines versioning; root has S3 backend block | Partial/unverified | Backend HCL uses three `CHANGE_ME` buckets while bootstrap creates one supplied bucket; reconcile names, locking, workspace key, and bootstrap/apply sequence |
| REQ-IAC-03 | Separate Terraform workspaces `dev/test/prod`, names include workspace | `local.prefix` uses `terraform.workspace`; backend/env files exist | Partial | No workspace guard/validation; identical tfvars; workflow path mismatch and no plan gate by PR target |
| REQ-IAC-04 | VPC with public/private subnets and private endpoints to API Gateway, cluster, S3, DynamoDB, CloudWatch | Network module creates VPC and two public subnets | Missing | Add private subnets/routing, endpoint resources/security policies, private API service path |
| REQ-DATA-01 | DynamoDB only, database per service, isolated per environment | Services use separate tables; default names derive from `ENVIRONMENT`, and explicit names must include the active environment token | Partial | Only dev Compose tables are configured; test/prod deployments and Terraform-to-service naming are not verified |
| REQ-OBS-01 | Structured CloudWatch logs per environment/service with SAGA correlation id | Terraform one log group; app logs not structured | Missing/partial | Add JSON correlation/environment/service logs and groups/retention per environment |
| REQ-OBS-02 | Prefect health of three environments, audit orphan/inconsistent/compensated SAGA, dashboard metrics | One Prefect flow checks one gateway and counts states/publishes metrics | Partial | No three-env matrix, service checks, orphan/cross-table consistency audit, or report artifacts |
| REQ-CI-01 | Protected dev/test/prod branches; no direct/force push | `scripts/set_branch_protection.ps1` prints a suggested command | Missing/unverified | Script does not configure protection; apply and verify host rules for all three required branches |
| REQ-CI-02 | feature -> dev -> test -> prod linear PR promotion | Deploy workflow triggers on environment branch pushes | Missing | Rework gating to promotion-only; current conditions can skip dependencies or bypass intended ordering |
| REQ-CI-03 | PR checks: lint/build, unit/integration/E2E, Terraform plan | PR workflow does pytest, frontend build, Terraform fmt/init/validate, Compose config | Partial | No separate integration/E2E suites or Terraform plan; npm lint omitted |
| REQ-CI-04 | Post-merge apply only target environment | Workflow has three jobs, each with init/apply | Partial | Job conditions/dependencies need correction; backend HCL path must be tested; no PR promotion proof |
| REQ-DEPLOY-01 | Canary 10-20% traffic, health/CloudWatch error checks, promote or rollback | K8s ingress weight 10; script checks rollout and restarts | Partial | No checked-in base ingress, CloudWatch/error threshold, traffic verification, or promotion/rollback procedure in pipeline |
| REQ-DEPLOY-02 | No downtime during rollout | Gateway stable/canary resources present | Unverified | Need service selector/ingress and rollout test under load |
| REQ-TEST-01 | Unit, integration, end-to-end tests across layers | 16 Phase 1 tests cover GraphQL over FastAPI, all three in-process services, Moto persistence, failure compensation, concurrency, and retries | Partial | Tests do not exercise Docker/Floci/live AWS or browser workflows |
| REQ-DOC-01 | Explain architecture and defend design choices | README, architecture/decision/deployment/defense docs, and expanded planning documents | Partial | Documentation set now includes requirements and handoff; implementation evidence and validated deployment/runbook still need completion |

## Phase 0 runtime evidence

- Python 3.12.10, `python -m pytest -q`: **5 passed**, 22 deprecation
  warnings.
- `docker compose config --quiet`: **passed**. Compose startup was attempted
  but failed because Docker could not connect to
  `//./pipe/dockerDesktopLinuxEngine`; no containers started.
- Gateway HTTP introspection using temporary Uvicorn + Moto: **HTTP 200**, no
  GraphQL errors. Exact SDL is `graphql/schema.graphql`.
- Current frontend charge mutation validation: **failed** because `$station`
  and `$key` are not declared in the operation.
- Git status: unavailable because the project directory is not a Git worktree.

## Phase 1 backend evidence

- Baseline before implementation: `python -m pytest -q`: **5 passed**.
- Final Phase 1 suite: `python -m pytest -q`: **16 passed**. It uses
  Moto-backed DynamoDB, actual FastAPI service apps, and GraphQL HTTP requests
  routed over in-process ASGI; it does not prove Docker/Floci/AWS behavior.
- `docker compose config --quiet`: **passed** with the Phase 1 dev environment
  and official feature-flag variables.
- Compose was not started in Phase 1; the Docker Desktop Linux engine remained
  unavailable from the documented Phase 0 attempt.
- Verified scenarios include successful charging, insufficient balance,
  hardware-fault compensation, failed compensation and retry, sequential and
  concurrent idempotency, concurrent connector reservation, duplicate
  refunds, dispatch state/telemetry, uncertain response recovery, official
  flag parsing, and environment-table mismatch rejection.
- The official DOCX was not found inside the repository or persisted reference
  files during this phase. The exact flag names were provided in the
  authorized Phase 1 request. No pricing or fast-charge behavior was inferred.

## Frontend acceptance mapping

See [FRONTEND_SPECIFICATION.md](./FRONTEND_SPECIFICATION.md). The screens
implementable against existing operations are Overview, Stations & charging,
SAGA summary history, and read-only flags. Interactive flag management,
accurate per-environment isolation, true live subscriptions, and detailed
compensation timeline are blocked by missing backend contracts.

## Official evaluation weights

The official document weights the defense by architectural layer:

| Layer | Weight | Current evidence/gap |
|---|---:|---|
| IaC, S3, and networking | 30% | Terraform is a partial scaffold; private routing/endpoints and tested state recovery are missing |
| CI/CD, environment promotion, and canary | 25% | Workflow/branch promotion and measured canary are partial |
| Architecture patterns, SAGA, and feature flags | 25% | Core reservation/billing/SAGA correctness and official flag names are addressed; surge/boost behavior and runtime environment proof remain incomplete |
| Observability and presentation | 20% | One Prefect health/count flow and minimal UI; correlated CloudWatch and full UI states are missing |

These are defense topics requiring live evidence, not merely files in the tree.
