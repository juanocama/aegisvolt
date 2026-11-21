# Decisions Log

| ID | Date | Decision | Rationale / evidence | Status |
|---|---|---|---|---|
| D-001 | 2026-11-20 | The official DOCX is the requirements authority; the running source/schema defines only current behavior | Avoid treating reference features or proposed operations as implemented | Accepted |
| D-002 | 2026-11-20 | Preserve the current codebase; complete planning and coordination docs before the next implementation task | User explicitly paused implementation and requested audit/documentation | Accepted |
| D-003 | 2026-11-20 | Keep the current GraphQL gateway as the planned browser boundary; do not call domain REST services from UI | Preserves service boundary and existing architecture | Accepted |
| D-004 | 2026-11-20 | Frontend must not invent GraphQL operations. Missing official flag writes, SAGA details, stop-session, paging, and subscriptions are contract gaps | The inspected `gateway/app.py` does not declare these operations | Accepted |
| D-005 | 2026-11-20 | Treat environment selection as unconfigured unless a real isolated endpoint is supplied; fail closed | Compose exposes only one gateway; helper defaults for test/prod point at REST service ports | Accepted |
| D-006 | 2026-11-20 | Do not copy substantial code from the reference ZIP until reuse conditions are known | No clear top-level license/notice was found in the inspected archive | Accepted |
| D-007 | 2026-11-20 | Next recommended code phase was backend contract/correctness remediation, not UI polish | The malformed frontend mutation and absent environment/flag contracts blocked reliable UI behavior; Phase 1 has since been authorized and completed | Superseded for sequencing by D-018 |
| D-008 | 2026-11-20 | Treat local Compose as dev only; test/prod endpoints are unavailable until real, isolated GraphQL gateways are configured | Compose exposes one GraphQL gateway at 8000; ports 8002/8003 serve REST; Terraform environment values are placeholders/identical | Accepted for Phase 0 |
| D-009 | 2026-11-20 | Record SDL v1 generated from actual gateway introspection; do not infer schema only from UI operations | Temporary Uvicorn gateway + Moto returned HTTP 200 and no introspection errors; snapshot is `docs/graphql/schema.graphql` | Accepted |
| D-010 | 2026-11-20 | Do not claim repository clean/dirty status because `.git` metadata is absent | `git rev-parse` and `git status` fail with “not a git repository” | Verified limitation |
| D-011 | 2026-11-20 | Do not claim Compose runtime readiness | Compose config parses, but Docker engine cannot connect to its named pipe; no ports were listening and no containers were started | Verified limitation |
| D-012 | 2026-11-20 | Phase 0 observed flags were read-only process environment values with non-official names | Baseline HTTP query returned `canaryCharge`/`chargerFaultSimulation`; Phase 1 replaced them with official names while retaining process-level read-only configuration | Superseded by D-015 |
| D-013 | 2026-11-20 | Reserve each station/connector using a conditional connector-lock item and recoverable reservation states | Moto-backed concurrent reservation test allows only one request to acquire the connector; retry resumes `reserving`/`cancelling` states | Accepted for current demo catalog |
| D-014 | 2026-11-20 | Persist wallet balance and charge/refund ledger effects atomically with DynamoDB transactions | Service tests verify replay does not repeat debit/refund effects; insufficient balance is an explicit 402 response | Accepted |
| D-015 | 2026-11-20 | Use the official flags as read-only process configuration, all false by default; gate hardware-fault injection with its official flag | User specified exact flag names but no approved persistence/control-plane model or pricing/boost rules were available; do not invent these | Accepted for Phase 1; pricing/boost behavior remains open |
| D-016 | 2026-11-20 | Make SAGA create conditional and request-fingerprinted; use a 120-second execution lease and retry-driven recovery | Integration tests cover concurrent same-key calls and recovery after uncertain downstream responses; service writes are idempotent | Accepted with a documented need to assess event item size and background recovery |
| D-017 | 2026-11-20 | Keep the Phase 0 SDL v1 snapshot; no SDL version bump in Phase 1 | Phase 1 HTTP introspection returned 200 with no GraphQL errors; SDL definitions match the snapshot ignoring declaration order | Verified |
| D-018 | 2026-11-20 | Stop after Phase 1 and require explicit approval before Phase 2, frontend, or deployment work | User authorized Phase 1 only; final suite reports 16 passed, and Docker/Floci/live AWS remain unverified | Accepted |

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
| O-011 | Surge pricing and fast-charge boost rules | Provide the official formula/eligibility, units, bounds, and expected interaction with wallet charges before implementing behavior | User/product |

Record future decisions here with date, alternatives, consequences, and
implementation/doc links.
