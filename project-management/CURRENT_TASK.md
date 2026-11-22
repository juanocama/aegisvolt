# Current Task

**Status:** Phase 1 backend correctness and the integrated frontend implementation
are complete within the available local verification boundary. AWS/deployment
work remains outside scope pending approval.  
**Last updated:** 2026-11-22.

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
- The React/Vite frontend now has four screens and uses the real local GraphQL gateway.
- Terraform, AWS, and Kubernetes were not changed or run.

## Verification

- Before implementation: `python -m pytest -q` — **5 passed**.
- After implementation: `python -m pytest -q` — **16 passed, 367 warnings**.
- 2026-11-22 verification: `python -m pytest -q -o faulthandler_timeout=15`
  — **20 passed, 367 warnings**. All service, SAGA, compensation, replay, and
  canary-readiness tests completed; the earlier Windows TestClient hang did not
  reproduce in this run.
- Replay test repeated in 20 separate pytest processes: **20 passed, 0 failed**.
- Details are recorded in
  [docs/PHASE_1_BACKEND_REPORT.md](../docs/PHASE_1_BACKEND_REPORT.md).
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

## Frontend verification

- `npm run build`: passed; Vite production bundle generated.
- `npm test`: 2 test files and 3 tests passed.
- `npm run lint`: passed.
- Vite dev server: running on `http://localhost:5173`.
- Vite `/graphql` proxy: forwards to `http://localhost:8010/graphql`.
- A real mutation through the proxy completed with state `COMPLETED`; wallet
  changed from 100.00 to 75.00 USD, connector became `reserved`, and dispatch
  telemetry became `active` in the local dev environment.
- No Lovable or Lovable-specific branding/configuration remains in the
  frontend source.

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

Frontend integration is complete for the current dev contract. Remaining work
requires separate approval: test/prod gateways, surge/boost rules, persistent
flag management, SAGA detail/pagination, infrastructure, and deployment.

## Phase 4 canary readiness status

**Audit date:** 2026-11-21. The Phase 4 repository audit and deployment guide
are in `docs/PHASE4_CANARY_READINESS_AUDIT.md` and
`docs/PHASE4_CANARY_DEPLOYMENT_GUIDE.md`. Canary deployment remains blocked:
the checked-in NGINX Ingress is not part of Kustomize and no traffic router,
private deployment runner, EKS deployment role, or request-level analysis
metrics are configured. The `canary-readiness.yml` workflow is a non-deploying
fail-closed gate. No AWS/GitHub live inspection or infrastructure mutation was
performed. Repository-side Phase 4 code does not authorize live AWS/Kubernetes
deployment; those operations still require separate approval.
