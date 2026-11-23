# Requirements Traceability

**Authority:** `Proyecto Final - Patrones Arquitectónicos Avanzados (AegisVolt)` (PDF provided 2026-11-23; same content as the DOCX).
Status reflects repository inspection on 2026-11-23. `Partial` means code exists
but does not demonstrate the complete requirement; `Missing` means not found;
`Unverified` means a declaration exists but execution has not been demonstrated.

| ID | Official requirement | Current evidence | Status | Remaining gap |
|---|---|---|---|---|
| REQ-BIZ-01 | Reserve bays, authorize funds, activate energy, audit telemetry | Three FastAPI services + GraphQL gateway; live AWS dev E2E (2026-11-23) and Compose E2E | Implemented | Telemetry is simulated state (no hardware/history) |
| REQ-UI-01 | Real-time station/connector status | React polls every 4 s; Compose E2E serves SPA through nginx | Implemented (polling) | No WebSocket/subscription |
| REQ-UI-02 | Reserve-and-activate flow triggering the SAGA | Stations page mutation; E2E happy path/replay/stop | Implemented | — |
| REQ-UI-03 | Flags per environment visible | Flags page reads per-env DynamoDB flags; fault warning in charge flow | Implemented | — |
| REQ-UI-04 | Transaction history and compensation state | SAGA table + guarded retryCompensation | Implemented (summary) | No event timeline/timestamps in GraphQL |
| REQ-BE-01 | Unified GraphQL (queries stations/telemetry; mutations reserve/pay/session) | Strawberry schema; snapshot gate in `lint-build` | Implemented | No paging |
| REQ-BE-02 | ≥3 Dockerized services on Kubernetes | 5 images; deployed and verified on EKS 1.37 (dev) | Implemented | test/prod not provisioned (cost) |
| REQ-FLAG-01 | Independent per-environment flags (DynamoDB/AppConfig/…) | `aegisvolt-<env>-flags` tables (Terraform, seeded, ignore_changes); runtime toggle without redeploy; isolation tests; E2E toggle | Implemented | Surge/boost have no business rule (display only) |
| REQ-SAGA-01 | Reserve → debit → activate | Orchestrated in gateway, persisted steps, idempotent services; AWS E2E | Implemented | — |
| REQ-SAGA-02 | Activation failure (or fault flag) → refund then release | Flag alone triggers fault; refund atomic then release; integration + E2E | Implemented | — |
| REQ-SAGA-03 | Insufficient funds → release | 402 → release; integration + E2E | Implemented | — |
| REQ-IAC-01 | All infra in Terraform modules | network, dynamodb, observability, api_gateway, eks_ecr, access_host, github_actions_*; apply/destroy evidence | Implemented | State bucket created by CLI bootstrap (documented) |
| REQ-IAC-02 | S3 remote state with versioning | `aegisvolt-tfstate-…` versioned, encrypted, lockfile; 38 dev state versions | Implemented | — |
| REQ-IAC-03 | One workspace per env, names from `terraform.workspace` | workspace guard; `env:/dev/…` state key; tfvars for dev/test/prod | Implemented | test/prod never applied |
| REQ-IAC-04 | VPC public/private subnets; VPCE to API GW and cluster; S3/DynamoDB/CloudWatch endpoints | execute-api, eks-auth, ecr, sts, logs, monitoring, ec2, elb interface + S3/DynamoDB gateway endpoints; private API + VPC Link + internal ALB verified live | Implemented | — |
| REQ-DATA-01 | DynamoDB only, database per service, per env | `aegisvolt-<env>-{stations,wallets,dispatch,sagas,flags}` | Implemented | — |
| REQ-OBS-01 | JSON logs with correlation_id/env/service in `/aegisvolt/<env>/…` | Request middleware; Fluent Bit routes to `/aegisvolt/<env>/<service>` (config dry-run validated); metric filters, alarm, dashboard; correlation id traced live in CloudWatch | Implemented | New log-group routing not yet exercised in AWS (dev ran with Container Insights groups) |
| REQ-OBS-02 | Prefect flows: health of 3 envs, SAGA audit (orphan/compensated), metrics in Prefect dashboard | Flow + tasks; Prefect artifacts (health, SAGA audit, summary); CloudWatch metrics; run against local Prefect server | Implemented | Live run against AWS envs needs private connectivity |
| REQ-CI-01 | Protected dev/test/prod (no force/direct push, required checks) | GitHub rules configured by the owner; required check names documented | Implemented (GitHub settings) | — |
| REQ-CI-02 | Linear feature → dev → test → prod | `promotion-guard` job | Implemented | — |
| REQ-CI-03 | PR: lint/build, unit, integration, e2e, terraform plan by target workspace | `ci.yml` jobs with those names | Implemented | `terraform-plan` needs OIDC bootstrap + repo variables |
| REQ-CI-04 | Post-merge apply only for merged branch | `deploy.yml` (`github.ref_name` → workspace, env-scoped OIDC role) | Implemented | Needs OIDC bootstrap; not yet executed in GitHub |
| REQ-DEPLOY-01 | Canary 10–20 %, CloudWatch error gate, promote or auto-rollback | Weighted ALB target groups, `canary_deploy.py`, metric filters, unit-tested gate | Implemented | Not yet executed against a live cluster |
| REQ-DEPLOY-02 | No downtime | maxUnavailable 0 + readiness probes; canary for gateway | Implemented | — |
| REQ-TEST-01 | Unit, integration, E2E | 56+ pytest tests (Linux), 6 E2E (Compose), frontend Vitest | Implemented | — |
| REQ-DOC-01 | Explain and defend design | `docs/DEFENSE_GUIDE.md`, `docs/CICD_PIPELINE.md`, deployment evidence | Implemented | — |

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

## Evaluation weights supplied in Phase 4 request (official DOCX unverified)

The Phase 4 request supplied the following approximate distribution. The
official course DOCX was not present in the repository or persisted reference
files during prior audits. The earlier table below records different weights
(including 20% for observability); keep this discrepancy explicit until the
course rubric is checked.

| Layer | Supplied weight |
|---|---:|
| Infrastructure as Code | 30% |
| CI/CD, Git, and Canary | 25% |
| Backend, microservices, Kubernetes, GraphQL, SAGA, and feature flags | 25% |
| Observability | 12% |
| Frontend | 8% |

## Prior traceability snapshot (not confirmed against official DOCX)

Earlier traceability notes recorded this distribution but did not preserve a
locally verifiable rubric excerpt:

| Layer | Weight | Current evidence/gap |
|---|---:|---|
| IaC, S3, and networking | 30% | Terraform is a partial scaffold; private routing/endpoints and tested state recovery are missing |
| CI/CD, environment promotion, and canary | 25% | Workflow/branch promotion and measured canary are partial |
| Architecture patterns, SAGA, and feature flags | 25% | Core reservation/billing/SAGA correctness and official flag names are addressed; surge/boost behavior and runtime environment proof remain incomplete |
| Observability and presentation | 20% | One Prefect health/count flow and minimal UI; correlated CloudWatch and full UI states are missing |

These are defense topics requiring live evidence, not merely files in the tree.

## Official rubric (PDF, section 5.2) — supersedes the weights above

| Layer | Weight |
|---|---|
| IaC (Terraform, workspaces, S3 backups, VPC/VPCE, DynamoDB) | 30 % |
| CI/CD, Git governance, static environments, canary | 25 % |
| Backend, microservices, Kubernetes, GraphQL, SAGA, feature flags | 25 % |
| Observability (CloudWatch + Prefect) | 12 % |
| Frontend | 8 % |

Question bank answers and demo commands: [DEFENSE_GUIDE.md](./DEFENSE_GUIDE.md).
The PDF does not mention a VPN; private access uses Session Manager tunnels.
