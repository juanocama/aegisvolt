# AegisVolt Implementation Roadmap

**Purpose:** staged delivery plan after the initial implementation. This is a
roadmap, not an assertion that listed work is complete. Detailed current state
is in [project-management/IMPLEMENTATION_STATUS.md](./project-management/IMPLEMENTATION_STATUS.md).

## Delivery principles

- Preserve the existing code; make incremental, tested changes.
- Use the official project DOCX as the requirement authority and the live
  backend schema as the frontend contract.
- Do not add speculative GraphQL fields or silently substitute mocked data.
- Close correctness and environment-isolation risks before polishing the UI.
- Every phase ends with evidence: tests, schema, plans, demo, or review.
- Obtain user approval before starting a new implementation phase.

## Phase 0 — Baseline and contract freeze

**Status:** verification completed to the extent the environment allowed.
Python tests and GraphQL introspection passed; Compose configuration parses,
but full startup is blocked by Docker Desktop's unavailable Linux engine. The
project directory has no Git metadata, so clean/dirty status is unavailable.
Phase 1 was subsequently authorized and is now complete within the test/runtime
boundary described below.

- `python -m pytest -q`: 5 passed (22 deprecation warnings).
- `docker compose config --quiet`: passed.
- `docker compose up --build -d`: failed at Docker engine connection; no
  containers started.
- Gateway introspection via temporary Uvicorn + Moto: HTTP 200, no GraphQL
  errors; SDL saved to `docs/graphql/schema.graphql`.
- Current frontend charge mutation validation found undeclared `$station` and
  `$key`.
- The backend correctness phase was separately authorized; see Phase 1 below.

**Exit gate:** backend operation signatures, result/error semantics, environment
identity, and allowed UI actions are approved and tested.

## Phase 1 — Backend business correctness

**Status:** completed for the authorized scope (2026-11-20). `python -m
pytest -q` reports 16 passed, 367 deprecation warnings. Phase 1 HTTP
introspection returned 200 with no GraphQL errors; SDL definitions match
`docs/graphql/schema.graphql` ignoring declaration order. `docker compose
config --quiet` passed, but Compose was not started; Docker Desktop's Linux
engine remains unavailable. No frontend or infrastructure deployment work was
performed. See
`project-management/IMPLEMENTATION_STATUS.md` for exact evidence.

Implemented and tested:

- Conditional connector locking and recoverable reservation/release states.
- Atomic, idempotent wallet debit/refund transactions.
- Conditional SAGA creation, request fingerprinting, leases, uncertain-step
  retry, persisted compensation state, and downstream status checks.
- Official read-only flag names and fault-injection gating.
- The required Phase 1 service/GraphQL scenarios listed in
  `project-management/IMPLEMENTATION_STATUS.md`.

Not completed or not verifiable in Phase 1: surge/boost business behavior
(rules were not available), persistent flag control, background SAGA recovery,
multi-service health aggregation, telemetry freshness/history, production
station inventory, test/prod runtime, and Docker/Floci/live AWS verification.

**Approval boundary:** Phase 1 is stopped. Do not start Phase 2, frontend, or
deployment work until the user explicitly approves the next task.

## Phase 2 — GraphQL contract and integration tests

- Publish checked-in SDL and exact operation documents.
- Add only approved operations: flag read/write if authorized, SAGA details and
  cursor/filtering if needed, stop-session if required.
- Make all resolver errors explicit and stable.
- Verify CORS or same-origin local proxy configuration.
- Ensure integration tests use an isolated emulator/test environment.

**Exit gate:** schema snapshot and contract tests pass and GraphQL behavior is
consistent with docs.

## Phase 3 — Frontend implementation

- Follow `docs/FRONTEND_SPECIFICATION.md` and the copy-ready agent prompt at
  `prompts/frontend/FRONTEND_IMPLEMENTATION_PROMPT.md`.
- Implement the four screens, navigation, accessible components, responsive
  layouts, polling safety, form validation, and all loading/empty/error/
  compensated states.
- Use only verified operations. Keep missing-contract features visibly
  read-only/unavailable until backend changes land.
- Add component/interaction tests and test failure behavior.

**Exit gate:** all frontend acceptance criteria pass; user approves any scope
expansion.

## Phase 4 — Local developer experience and E2E

- Align `.env.example`, Compose ports, frontend configuration, readiness checks,
  and Windows PowerShell instructions.
- Decide whether to include a frontend container or maintain Vite as a separate
  development process.
- Add browser E2E for success, insufficient funds, charger failure/compensation,
  idempotent retry, endpoint unavailable, and environment mismatch.
- Verify UI never shows stale or cross-environment data as current.

**Exit gate:** clean local start and end-to-end demonstrations are repeatable.

## Phase 5 — Infrastructure and Kubernetes

- Add private/public subnet architecture, NAT or required endpoint routing,
  interface/gateway endpoints, endpoint policies, security groups, and private
  API integration.
- Align Terraform workspace backend key/locking, bootstrap, env tfvars, and
  CI backend paths.
- Complete service Deployment/Service/ConfigMap/IAM setup for all workloads.
- Run Terraform fmt/init/validate/plan and inspect provider compatibility.
- Do not apply real AWS resources until a user approves cost/security scope.

**Exit gate:** isolated plans for dev/test/prod and a tested local/emulator
deployment where emulator supports the resource set.

## Phase 6 — Observability and Prefect

- Emit structured correlated logs from all services.
- Create per-environment/per-service CloudWatch groups, alarms, and retention.
- Make Prefect check all environments/services and detect stale/inconsistent
  SAGA records through read-only queries.
- Publish health/audit metrics and artifacts; keep recovery opt-in.

**Exit gate:** injected failure produces searchable logs, a detectable SAGA
inconsistency, and a Prefect report.

## Phase 7 — Governance, CI/CD, canary, and defense

- Configure protected branches and required checks; verify settings in hosting
provider, not merely script output.
- Enforce feature/* -> dev -> test -> prod PR chain.
- Pre-merge: lint, builds, unit, integration, E2E, Docker validation, Terraform
  plan per target environment.
- Post-merge: apply/deploy only target workspace, deploy canary (10-20%),
  validate health/error thresholds, promote or rollback.
- Record evidence and update defense guide with honest environment caveats.

**Exit gate:** pipeline simulation proves merge gating, environment
isolation, canary success, and rollback.

## Priority order

1. Backend contract/correctness and environment decisions.
2. Frontend using the frozen contract.
3. Local E2E reliability.
4. IaC/networking and K8s completeness.
5. Observability and governance proof.

This order avoids building UI behavior against unavailable or unstable APIs.
