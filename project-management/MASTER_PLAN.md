# AegisVolt Master Plan

**Baseline:** 2026-11-20  
**Project state:** initial implementation exists; this is a stabilization and
completion plan, not a greenfield restart.

## Goal

Deliver a demonstrable, independently maintainable cloud-native EV charging
platform that meets the official course specification and can be defended by
explaining its UI, GraphQL contracts, microservices, SAGA, persistence,
Terraform, Kubernetes, observability, and promotion workflow.

## Requirement authorities

1. Official project DOCX: mandatory course requirements.
2. Actual source and running GraphQL schema: behavior currently available to
   the frontend.
3. This plan/specification: approved implementation target, subordinate to the
   official DOCX and explicit user decisions.
4. Reference ZIP: inspiration only; no wholesale reuse and no substantial
   verbatim copying while licensing is unclear.

## Outcomes and gates

| Workstream | Intended outcome | Gate / evidence |
|---|---|---|
| Current-state and contract audit | Known gaps, verified GraphQL operations, file ownership | Traceability matrix and SDL snapshot |
| Backend correctness | Safe reservations, wallet accounting, idempotency, SAGA compensation, environment flags | Unit + integration + GraphQL contract tests |
| Frontend | Four accessible responsive operator-console screens | Build/lint/tests and contract-backed browser flows |
| Local stack | Repeatable Windows-friendly local demo | Clean Compose/Vite start and end-to-end run |
| Infrastructure | Workspace-isolated Terraform and private network path | fmt/validate/plan per environment; approved AWS apply only |
| Kubernetes/canary | Deployable services with measurable rollout and rollback | Automated canary success/failure demonstration |
| Observability | Correlated CloudWatch logs and Prefect environment/SAGA audit | Failure injection yields report and metrics |
| Governance/CI | Protected, linear feature -> dev -> test -> prod promotion | Verified required checks and target-only deploy |
| Defense/documentation | Accurate architecture, limitations, and evidence | Reproducible demo script and oral-defense notes |

## Immediate sequence

1. Freeze and correct backend/API contracts and multi-environment configuration.
2. Implement frontend against the approved real contract, using
   `prompts/frontend/FRONTEND_IMPLEMENTATION_PROMPT.md`.
3. Add browser E2E and improve local integration behavior.
4. Complete and validate Terraform/Kubernetes networking and deployments.
5. Complete Prefect/CloudWatch and CI/CD governance.
6. Re-run traceability review and defense rehearsal.

## Working rules

- Work only in the current repository. Do not copy the example archive wholesale.
- Preserve existing code and unrelated user changes.
- Keep each task small and reviewable; update directly related docs and tests.
- Never describe a resource as deployed or a feature as complete based only on
  Terraform/manifests being present.
- No production credentials, real AWS provisioning, branch-rule changes, or
  cost-incurring resources without explicit user approval.
- Stop at the task's defined scope and hand off before starting the next phase.

## Current approval boundary

Phase 0 baseline verification is complete to the extent the environment
allowed, and the contract snapshot is recorded. Full local Compose startup
remains blocked by the unavailable Docker Desktop engine, and the directory
has no Git metadata. The next recommended implementation task is Phase 1
backend contract/correctness remediation (see `CURRENT_TASK.md` and
`HANDOFF.md`); it has not been started. Wait for explicit user approval.
