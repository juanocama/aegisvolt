# Current Task

**Status:** Phase 1 backend correctness changes and tests are complete within
the available local verification boundary. Await explicit user approval before
starting Phase 2, deployment work, or frontend implementation.  
**Last updated:** 2026-11-20.

## Phase 1 implementation

- Station reservations now use persisted, conditional connector locks and
  recoverable `reserving`/`cancelling` states. Replays are fingerprinted;
  concurrent requests cannot take the same demo connector.
- Wallet debits and charge records, and refunds and refund records, are
  atomic DynamoDB transactions. Charge/refund idempotency is enforced and
  insufficient balance returns HTTP 402.
- Dispatch persists activation and initial telemetry together. Stop preserves
  activation/telemetry state; hardware failures are persisted and return a
  failure response.
- SAGA creation is conditional and payload-fingerprinted. A 120-second lease,
  persisted step/compensation events, same-key retry after uncertain
  downstream responses, and state-guarded compensation retry are implemented.
- Official feature-flag names are returned read-only from process environment
  with false defaults. The hardware-fault request hook is gated by its flag.
  Surge pricing and fast-charge boost are configuration-only until business
  rules are approved.
- GraphQL operation signatures remain unchanged. The SDL and contract docs
  describe the updated resolver/service behavior and remaining gaps.
- Frontend source, Terraform, AWS, and Kubernetes were not changed or run.

## Verification

- Before implementation: `python -m pytest -q` — **5 passed**.
- After implementation: `python -m pytest -q` — **16 passed, 367 warnings**.
- Coverage includes GraphQL/service success, insufficient funds, activation
  failure, successful and failed compensation/retry, sequential/concurrent
  duplicate SAGA calls, payload conflicts, concurrent connector reservations,
  duplicate charges/refunds, dispatch stop/telemetry state, uncertain response
  retry/recovery, official flag parsing, and environment table validation.
- Tests use Moto-backed DynamoDB, actual FastAPI apps, and in-process ASGI
  HTTP routing. They do not prove Docker/Floci/live AWS behavior.
- `docker compose config --quiet` passed. Compose runtime was not started;
  Phase 0 recorded that Docker could not connect to
  `//./pipe/dockerDesktopLinuxEngine`.
- No Terraform command/apply, AWS operation, Kubernetes deployment, or
  frontend build was run.
- No `.git` metadata exists, so Git cannot establish clean/dirty status.

## Remaining limitations and decisions

1. Local test/prod GraphQL gateways and stores are not configured. Separate
   deployments must set `ENVIRONMENT`, environment-matching table names, and
   flag values; only local dev Compose exists.
2. No pricing formula or fast-charge boost behavior was found in the repository
   or persisted reference files. The official DOCX was not available in those
   locations; do not infer those behaviors.
3. Flag values are read-only process configuration. No persistent flag store
   or management mutation was added.
4. SAGA recovery is retry-driven, not a background worker; event history is
   kept on one DynamoDB item and is subject to the 400 KB item limit.
5. The station catalog and default USD wallet remain demo scaffolding.
   GraphQL amount/currency semantics need product approval.
6. SAGA events are persisted internally but are not exposed in the GraphQL
   type. Test/prod isolation and true telemetry remain unverified.

## Approval boundary

Phase 1 is stopped here. The next suggested task is to review/approve the
remaining pricing/boost rules, environment topology, amount/currency rules,
and SAGA history scope. Only after approval should Phase 2 contract work or
frontend implementation begin.
