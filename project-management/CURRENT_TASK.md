# Current Task

**Status:** Phase 1 backend correctness, frontend implementation, and Phase 2
Terraform consistency work have completed their recorded local verification.
Phase 3 Kubernetes base/overlays now render locally, but the full backend suite
remains blocked by the Windows TestClient socket startup hang. AWS/EKS
deployment remains outside scope pending approval.
**Last updated:** 2026-11-23.

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
- Git metadata was available for the Phase 3 task. The checkout was on
  `feature/phase-3-kubernetes` at `e1cf059`; `.git` write access was denied, so
  remote refs could not be refreshed. See the Phase 3 report for this
  verification boundary.

## Phase 2 Terraform verification

- Terraform 1.17.2 was available.
- `terraform fmt -check -recursive` passed.
- Root `terraform init -backend=false -input=false` passed.
- Root `terraform validate -no-color` passed.
- Development tfvars passed local Terraform validation.
- Bootstrap `terraform init -backend=false -input=false` passed.
- Bootstrap `terraform validate -no-color` passed.
- AWS provider 5.100.0 and TLS provider 4.4.2 were reused from the local lock
  files; no AWS API or remote backend operation was performed.
- Details are recorded in
  [docs/PHASE_2_TERRAFORM_REPORT.md](../docs/PHASE_2_TERRAFORM_REPORT.md).

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

## Phase 3 Kubernetes implementation status

- The root base remains directly under `k8s/`; its Kustomize entry point and
  root YAML discovery behavior are unchanged.
- `k8s/overlays/{dev,test,prod}` reference the eight root base YAML files
  directly. Overlay rendering requires
  `kubectl kustomize --load-restrictor LoadRestrictionsNone ...` because the
  shared files are outside each overlay directory. This option is scoped to
  the checked-in repository overlays; the root render keeps the default
  restriction. Each overlay adds an `environment` label to resource metadata
  and pod templates.
- Root render, all three overlay renders, local environment/table/image/
  replica/probe/resource/service assertions, the embedded CI root manifest
  validator, workflow YAML parsing, and `git diff --check` passed locally.
- `python -m pytest -q tests/test_services.py`: 5 passed. Full pytest was
  attempted with faulthandler and reproduced a Windows Proactor socket-pair
  hang in `tests/test_compensation.py::test_retry_compensation_rejects_non_failed_saga`;
  the run was interrupted without changing application code or tests.
- Current local HEAD is `58353ff`, the same as locally recorded `origin/dev`,
  and includes CI repair commit `9509b3a`. The feature branch is reported six
  commits ahead of its local `origin/feature/phase-3-kubernetes` tracking ref.
  No fetch was done; GitHub CLI is unavailable, so live PR/check/review state
  and fresh remote ancestry remain unverified.
- ECR account/region/SHA and IRSA account identifiers remain placeholders;
  no EKS admin principal is configured; production sizing, private API Gateway
  integration, pod log collection, AWS/EKS provisioning, and deployment are
  not complete.
- GitHub Actions itself was not run; the workflow overlay shell step could not
  execute locally because Windows denied `bash.exe` access. Details and exact
  commands are in `docs/PHASE_3_KUBERNETES_REPORT.md`.
- Kubernetes manifests parsed and rendered, but API-server schema validation
  was not available locally; no invalid fields were found in the static audit.

## Phase 4 infrastructure and observability status

- Work is in `feature/phase-4-infrastructure-observability`, branched from the refreshed `origin/dev`; changes are local and have not been committed or pushed.
- Audit, architecture decisions, prioritized gap matrix, required values, and implementation boundaries are recorded in `docs/PHASE_4_INFRASTRUCTURE_OBSERVABILITY_REPORT.md`.
- The HTTP API shell was replaced by private REST API Gateway, execute-api VPC endpoint/policy, and an optional GraphQL VPC Link integration. The integration is disabled until the internal AWS LBC ALB ARN and DNS name exist.
- EKS now declares Kubernetes 1.37 and `API_AND_CONFIG_MAP`; at least one validated real admin ARN is required before provisioning. Service IRSA policies are reduced to the DynamoDB calls each service actually makes.
- CloudWatch Observability and Pod Identity add-ons and retained log groups are declared. FastAPI writes JSON request metadata with a propagated correlation ID; Prefect audits require explicit private config for all three environments and report SAGA event/consistency summaries.
- CI now includes strict kubeconform schema validation pinned by image digest for root and all three overlays. Gateway Ingress is internal and serves `/graphql`; `/health` is used for ALB health checks.
- `terraform fmt -check -recursive`, `terraform init -backend=false -input=false -reconfigure` (AWS provider 6.73.0), `terraform validate -no-color`, and `python -m compileall -q common gateway services tests observability/prefect` passed. `tests/test_services.py` plus `tests/test_phase4_observability.py`: 9 passed, 68 warnings.
- Full `python -m pytest -q -o faulthandler_timeout=10` did not finish; it reproduced the Windows Proactor socket-pair hang at `tests/test_compensation.py::test_retry_compensation_rejects_non_failed_saga` and was interrupted. No tests were weakened or removed.
- Root and all overlays rendered and parsed: 15 root resources and 14 per overlay. CI workflow YAML parsed. Kubeconform itself could not run locally because it is not installed and Docker Desktop denied access to its engine pipe.
- No AWS API, S3 backend, plan/apply, Kubernetes deployment, or runtime CloudWatch validation was performed.
- Remaining integration requirements: install/configure AWS Load Balancer Controller with its upstream IAM policy through a private cluster-connected runner, deploy with immutable ECR image SHAs, then set the ALB inputs and enable the API integration. Provide region/account/state bucket and real EKS admin principal. Prefect needs private URLs and a read-only DynamoDB/CloudWatch role.
- Official course DOCX is unavailable in the inspected files. Phase 4 rubric percentages differ from the older traceability snapshot; the discrepancy is documented, not resolved.

## Phase 4 targeted remediation update

- `common/observability.py` validates/normalizes correlation IDs and logs route templates instead of dynamic URL paths; malformed or missing IDs receive a generated UUID. Added focused privacy/propagation tests.
- Prefect now distinguishes fresh active SAGA states from stale nonterminal states using `updated_at`, the existing lease, and configurable `SAGA_STALE_AFTER_SECONDS` (default 300). Compensation attempts/retries use the actual `compensation` and `compensation_retry` events.
- Routine audit scans the paginated SAGA table and BatchGets only downstream records referenced by SAGA items. Exhaustive orphan detection is explicitly optional with `SAGA_FULL_ORPHAN_SCAN_ENABLED=true`; disabled results say the audit is incomplete, not zero. Existing key-only DynamoDB model still prevents efficient incremental SAGA/orphan discovery; see `docs/PHASE_4_REMEDIATION_READINESS.md` for the required index/cursor design and cost limits.
- CI pins the Kubeconform schema source to Kubernetes 1.37.0 strict schema ref; image digest, strict mode and root/dev/test/prod validation are retained.
- `compileall` passed; seven synchronous focused tests passed. Async middleware tests and full suite remain blocked locally by Windows Proactor socket-pair loop startup; WSL access is denied. No AWS calls or resource changes were performed.
- Readiness plan records endpoint/NAT matrix, exact LBC v3.6.3 upstream IAM policy source and Pod Identity install sequence, EKS role ARN inference/mismatch, add-on version lookup steps, and private frontend/CORS decisions. AWS configuration remains unmodified.

## Phase 4 execution update (2026-11-23)

- Fixed Prefect BatchGet serialization bug (crashed against real DynamoDB) and missing `ACTIVATION_UNCERTAIN` active state; added Moto-backed tests. Updated stale gateway `/health` assertion. Full suite: 36 passed on Windows.
- Verified AWS identity and real EKS admin role ARN; account has no AegisVolt resources yet. Pinned EKS 1.37 add-on versions, added ELB/Monitoring endpoints, configured dev tfvars and backends (`aegisvolt-tfstate-065656773005-us-east-1`).
- Read-only dev plan: create-only, no NAT. **Blocked on owner approval:** state bucket creation and dev apply (~USD 235/month estimate). Details in `docs/PHASE_4_REMEDIATION_READINESS.md`.

## Phase 4 temporary AWS dev deployment (2026-11-23)

- User-authorized same-day `dev` deployment (USD 4 ceiling, no credits) was applied, tested end-to-end and destroyed. Evidence: `docs/PHASE_4_DEV_DEPLOYMENT_EVIDENCE.md`.
- Added: frontend container/manifests with dedicated internal ALB, LBC Pod Identity role + ECR mirror, Session Manager access host, single-AZ endpoint option, dev cost settings.
- Live run found and fixed: billing IAM `UpdateItem`, CloudWatch agent crash-loop, REST API policy drift, nginx TLS verify depth, dev overlay region/ingress gaps.
- Teardown independently verified; only the Terraform state bucket remains. No commit/push performed.
- Remaining: Client VPN not implemented (SSM port forwarding documented as substitute); full local pytest still blocked by Windows hang.

## Phase 5 rubric completion (branch `feature/phase-5-rubric-completion`, 2026-11-23)

Authority: official PDF (`Proyecto Final - Patrones Arquitectónicos Avanzados (AegisVolt)`), which does not require a VPN; Session Manager remains the private access path.

- Feature flags moved to per-environment DynamoDB tables `aegisvolt-<env>-flags` (Terraform-seeded, runtime toggle via `scripts/set_feature_flag.py`, no redeploy). `SIMULATE_CHARGER_HARDWARE_FAULT` alone forces activation failure and compensation (spec 2.3); `chargeFault` is a deprecated no-op. Frontend shows a fault warning instead of a per-request checkbox.
- Logs routed by Fluent Bit to `/aegisvolt/<env>/<service>` (config validated with `fluent-bit --dry-run`); metric filters, 5xx alarm and dashboard per environment.
- Prefect flow publishes table/markdown artifacts, reports unavailable environments explicitly, and checks state-specific SAGA invariants; run recorded on the project Prefect server (Compose profile `observability`, port 4201).
- CI rewritten: promotion-guard, lint-build, unit-tests, integration-tests, e2e-tests (Compose), terraform-static, terraform-plan (target-branch workspace, OIDC read-only role), kubernetes. Post-merge `deploy.yml`: branch → workspace apply, SHA images, SSM tunnel, LBC, canary 20% with CloudWatch gate and auto rollback, post-deploy E2E.
- Fixed pre-existing defects: kubeconform schema URL (404) and arm64-only image digest; refund replay returning stale `charged`; flaky log-privacy assertion; Prefect false positives for refunded/stopped records; ALB names colliding across environments.
- Verification: pytest full suite in Linux container; Compose E2E 6/6; kubeconform strict 84/84; CI kubernetes validators; terraform fmt/validate; actionlint; frontend lint/test/build. No Terraform was applied in this phase (per user instruction).
