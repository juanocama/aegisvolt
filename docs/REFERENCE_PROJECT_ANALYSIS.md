# Reference Project Analysis

**Reference archive:** `C:\Users\iamju\Downloads\aegisvolt.zip`  
**Inspection snapshot:** `C:\Users\iamju\.copilot\session-state\a7ef9301-927e-48d2-9b08-4feb3ba1a97e\files\aegisvolt-reference\aegisvolt`  
**License status:** no clear top-level LICENSE/COPYING/NOTICE file was found in
the inspected archive. Do not reproduce substantial source verbatim unless
reuse permission is established.

## 1. Scope and method

The archive was inspected by inventorying its project structure while
excluding dependency/generated noise, then reading representative frontend,
GraphQL/SAGA, service, Terraform, Kubernetes/canary, CI, Prefect, README, and
architecture files. The archive is a reference implementation, not the
academic requirements or the working project. The working implementation is
the separate repository at `C:\Users\iamju\Desktop\patrones\aegisvolt`.

Decision labels used below are: **Reuse and adapt**, **Reimplement based on the
reference**, **Use only as architectural inspiration**, **Reject**, and **Not
relevant**. No whole service/application file is approved for direct copying.

## 2. Component evaluation

| Reference file/component | Original responsibility | Useful idea or functionality | Decision | Adaptation required | Final destination |
|---|---|---|---|---|---|
| `services/graphql-gateway/graphql_gateway/saga.py` | Orchestrated reserve/charge/dispatch SAGA, persistence, compensation and retry | Persist step state, reverse-order compensation, idempotency-aware design, uncertainty discussion | Use only as architectural inspiration | Independently implement against current services; fix correctness before any reuse; add concurrency, failure, and replay tests | `gateway/app.py`, `docs/SAGA_DESIGN.md`, future tests |
| `services/graphql-gateway/graphql_gateway/schema.py`; `schema.graphql` | Strawberry schema and type mapping for operations | Stable GraphQL boundary between UI and services | Reimplement based on the reference | Current schema is a different contract; use actual current gateway as source, version SDL and test introspection | `gateway/app.py`, `docs/GRAPHQL_CONTRACTS.md` |
| `frontend/src/App.tsx`; `frontend/src/api.ts`; `frontend/src/styles.css` | React operations console and GraphQL client | Environment-oriented operator console, status and SAGA visibility | Use only as architectural inspiration | No substantial code copying due license uncertainty; current UI is simpler and must match its actual schema | `frontend/`; frontend specification/prompt |
| `services/station-reservation`, `billing-wallet`, `energy-dispatch` | Domain service separation and DynamoDB ownership | Database-per-service boundaries and narrow service responsibilities | Use only as architectural inspiration | Validate atomicity, idempotency, API semantics, table keys, and environment config independently | Current `services/` and architecture docs |
| `libs/aegis_common/` | Shared configuration, AWS clients, feature flags, logging, seed | Centralized config/logging patterns | Reimplement based on the reference | Keep service ownership clear; no hidden fallback; explicit environment and error behavior | `common/` if separately approved |
| `infra/modules/network`, `dynamodb`, `api_gateway`, `eks`, `k8s_ingress`, `observability`, `ecr` | AWS Terraform modules | Modular IaC and workspace-based naming | Use only as architectural inspiration | Validate all provider arguments, IAM, subnet routing, endpoints, private API integration, and cost/security before adopting | Current `infra/` and `docs/architecture.md` |
| `k8s/templates/deployment.yaml`; `scripts/canary_deploy.sh` | Stable/canary workloads and rollout analysis | Separate canary track and health-gated promotion concept | Use only as architectural inspiration | Current repo has a different minimal ingress; implement a measured, tested promotion and rollback path | `k8s/`, `scripts/`, CI after approval |
| `.gitlab-ci.yml`; `scripts/ci/*` | Pre-merge checks and post-merge environment deployments | Separate plan/test from apply; serialize environment state changes | Reimplement based on the reference | The academic assignment uses PR promotion requirements; align chosen GitHub/GitLab provider, protect branches, and require plans | `.github/workflows/` and governance docs |
| `observability/prefect/flows.py`; `audit.py` | Health and cross-table SAGA audit with Prefect artifacts | Task-oriented health and consistency reporting | Reimplement based on the reference | Current flow checks one gateway and counts state only; implement with explicit auth/read-only behavior and tests | `observability/prefect/` |
| `tests/unit`, `tests/integration`, `tests/e2e` | SAGA, DynamoDB, and GraphQL HTTP tests | Test layering and failure-scenario coverage | Reimplement based on the reference | Add tests matched to current service contracts; do not import test code blindly | `tests/` |
| `docker-compose.yml`, Dockerfiles, scripts | Local Floci development and convenience tasks | Local-first integration environment | Use only as architectural inspiration | Pin images, ensure health/readiness ordering, configuration consistency, and Windows instructions | Compose and docs |
| `README.md`, `docs/arquitectura.md`, `docs/sustentacion.md`, setup docs | Setup, architecture, defense and provider instructions | Defense-oriented explanation and documented local run path | Use only as architectural inspiration | Write project-specific, English documentation reflecting actual implementation status | `README.md`, `docs/`, `project-management/` |
| `frontend/node_modules`, Terraform `.terraform/`, state files, caches, logs, bytecode, generated artifacts | Build/dependency/runtime data | None to reuse as application source | Reject | Keep out of source repository; never copy state, credentials, or binary dependencies | Exclude via ignore rules |

## 3. Reuse and provenance statement

The working project does not intentionally incorporate substantial source code
from the reference archive. Similarity is limited to common architecture
patterns required by the assignment: GraphQL aggregation, three domain
services, DynamoDB separation, orchestrated SAGA, Terraform modules, and
stable/canary deployment concepts. Where prior architecture decisions were
influenced by reference behavior, this is documented as architectural
inspiration, not independent invention.

Before any code-level adaptation:

1. Establish license/reuse permission.
2. Record exact original path and lines/revision.
3. Identify the retained behavior, changes, and official requirement supported.
4. Add tests against AegisVolt's contracts.
5. Record validation results in this document and
   `project-management/DECISIONS_LOG.md`.

## 4. Explicit exclusions

Do not import the archive wholesale, its generated `node_modules`, Terraform
provider caches or `.terraform` directories, `terraform.tfstate` files, logs,
Python bytecode, local environment files, credentials, or machine-specific
scripts. Do not infer correctness or deployability from the reference README.
