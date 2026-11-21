# AegisVolt Handoff

**Handoff date:** 2026-11-20  
**Current state:** Phase 0 verification and contract snapshot completed;
Phase 1 implementation is paused for user approval.

## What exists

- Working source for React/Vite, FastAPI + Strawberry gateway, three
  microservices, DynamoDB access, Terraform scaffold, a gateway Kubernetes
  stable/canary example, Prefect flow, workflows, and a small Python test suite.
- Existing setup/architecture/defense/decision/reference notes.
- New detailed frontend specification, architecture, GraphQL contract, SAGA
  design, requirement traceability, reference analysis, roadmap, project
  coordination, and agent protocol documents.
- Copy-and-paste frontend task prompt:
  `prompts/frontend/FRONTEND_IMPLEMENTATION_PROMPT.md`.
- Introspected SDL snapshot: `docs/graphql/schema.graphql`.

## Main findings

- UI is one page and only partially covers official minimums.
- The reserve mutation in the UI is malformed: `$station` and `$key` are used
  but not declared, and the chosen id is a station while connector is fixed to
  `c-1`.
- Frontend has no telemetry panel, complete async states, responsive styles, or
  browser/component tests.
- Only one GraphQL gateway is available in Compose; test/prod client defaults
  point at REST service ports, and backend flags are not environment-isolated.
  Vite has a local `/graphql` proxy, but the current client bypasses it with
  absolute URLs; gateway CORS is not configured for remote origins.
- `docker compose config --quiet` passed, but the Docker engine was unavailable
  and no Compose container was started. Do not claim a full-stack local run.
- Python 3.12.10 tests: 5 passed, 22 deprecation warnings.
- The directory has no `.git` metadata, so `git status` cannot establish a
  clean worktree or enumerate prior uncommitted edits.
- Introspection via temporary Uvicorn + Moto returned HTTP 200 without GraphQL
  errors. A current frontend mutation validation error reported undefined
  `$station` and `$key`.
- Official feature flags, details/pagination for SAGA history, and a stop
  session operation are absent.
- SAGA/service correctness, Terraform network/private API, K8s service
  deployments, Prefect coverage, and CI promotion are all partial; see the
  traceability matrix.
- The reference archive has no clear license file; analysis recommends
  architectural inspiration only.

## Recommended next task (not started)

With explicit user approval, begin Phase 1 backend contract and correctness
work. First decisions needed:

1. Define how environment endpoints/data are isolated and whether test/prod are
   local, remote, or not part of local demo.
2. Confirm how the required official flags are stored and whether UI writes are
   permitted.
3. Confirm charge amount/currency semantics and acceptable SAGA history scope.

Then remediate station locking/data filtering, atomic/idempotent billing,
compensation HTTP/status handling, retry eligibility, and SAGA duplicate-key
behavior. Version/test the resulting schema. Do not begin frontend work until
the contract and environment decisions are approved.

Then implement the frontend using the standalone prompt and actual approved
schema.

## Do not assume

- Terraform declarations are applied or valid.
- AWS or Floci is running.
- Three isolated GraphQL endpoints exist.
- The current frontend's charge flow works.
- Existing tests cover browser behavior or all compensation cases.
- Any code in the example ZIP is licensed for copying.

Wait for the user to approve Phase 1.
