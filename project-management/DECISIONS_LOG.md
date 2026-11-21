# Decisions Log

| ID | Date | Decision | Rationale / evidence | Status |
|---|---|---|---|---|
| D-001 | 2026-11-20 | The official DOCX is the requirements authority; the running source/schema defines only current behavior | Avoid treating reference features or proposed operations as implemented | Accepted |
| D-002 | 2026-11-20 | Preserve the current codebase; complete planning and coordination docs before the next implementation task | User explicitly paused implementation and requested audit/documentation | Accepted |
| D-003 | 2026-11-20 | Keep the current GraphQL gateway as the planned browser boundary; do not call domain REST services from UI | Preserves service boundary and existing architecture | Accepted |
| D-004 | 2026-11-20 | Frontend must not invent GraphQL operations. Missing official flag writes, SAGA details, stop-session, paging, and subscriptions are contract gaps | The inspected `gateway/app.py` does not declare these operations | Accepted |
| D-005 | 2026-11-20 | Treat environment selection as unconfigured unless a real isolated endpoint is supplied; fail closed | Compose exposes only one gateway; helper defaults for test/prod point at REST service ports | Accepted |
| D-006 | 2026-11-20 | Do not copy substantial code from the reference ZIP until reuse conditions are known | No clear top-level license/notice was found in the inspected archive | Accepted |
| D-007 | 2026-11-20 | Next recommended code phase is backend contract/correctness remediation, not UI polish | Current malformed mutation and absent environment/flag contracts prevent reliable UI behavior | Proposed; awaiting user approval |
| D-008 | 2026-11-20 | Treat local Compose as dev only; test/prod endpoints are unavailable until real, isolated GraphQL gateways are configured | Compose exposes one GraphQL gateway at 8000; ports 8002/8003 serve REST; Terraform environment values are placeholders/identical | Accepted for Phase 0 |
| D-009 | 2026-11-20 | Record SDL v1 generated from actual gateway introspection; do not infer schema only from UI operations | Temporary Uvicorn gateway + Moto returned HTTP 200 and no introspection errors; snapshot is `docs/graphql/schema.graphql` | Accepted |
| D-010 | 2026-11-20 | Do not claim repository clean/dirty status because `.git` metadata is absent | `git rev-parse` and `git status` fail with “not a git repository” | Verified limitation |
| D-011 | 2026-11-20 | Do not claim Compose runtime readiness | Compose config parses, but Docker engine cannot connect to its named pipe; no ports were listening and no containers were started | Verified limitation |
| D-012 | 2026-11-20 | Current flags are read-only process environment values, not official environment-scoped feature flags | HTTP query returns `canaryCharge`/`chargerFaultSimulation`; no GraphQL mutation or DynamoDB flag access exists | Accepted |

## Open decisions

| ID | Decision needed | Options / evidence needed | Owner |
|---|---|---|---|
| O-001 | How local dev/test/prod GraphQL endpoints are provided | Separate Compose stacks/ports, one gateway with explicit env switching, or remote endpoints; each must isolate data and flags | User/architecture |
| O-002 | Whether operators may mutate feature flags from UI | Official requirement asks to display status; current backend has read-only flags; agree security/role policy before adding mutation | User/backend |
| O-003 | Whether charge-fault injection is exposed in UI | Current argument is per request, not persisted flag; restrict to dev/test or use actual environment-scoped flag | User/backend |
| O-004 | Scope of SAGA history detail | Summary only vs. event timeline, compensation details, filters, and pagination; requires approved GraphQL schema | User/backend |
| O-005 | Currency and amount semantics | Current `amount` is numeric and wallet is demo USD; do not assume energy pricing model | User/product |
| O-006 | Real AWS vs local emulator for final defense | Terraform scope, networking, costs, and emulator support differ | User/instructor constraints |
| O-007 | Source ZIP reuse rights | Obtain license or written permission before substantial code-level adaptation | User |
| O-008 | Local demo endpoint policy | Confirm whether test/prod remain unavailable locally or will have separately provisioned gateways | User |
| O-009 | Official flag update policy | Confirm whether changing flags from UI is required/authorized, and define ownership/guardrails | User |
| O-010 | SAGA request contract | Confirm amount/currency constraints and desired compensation/event-history detail | User |

Record future decisions here with date, alternatives, consequences, and
implementation/doc links.
