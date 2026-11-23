# AegisVolt Phase 3 Kubernetes Report

**Date:** 2026-11-23  
**Branch:** `feature/phase-3-kubernetes`  
**Audited HEAD:** `58353ff` (`origin/dev`)  
**Scope:** Kubernetes manifests, environment overlays, static validation, and related documentation. No AWS/EKS deployment, Terraform operation, commit, or push was performed.

## Summary

Environment overlays render from the existing manifests directly under `k8s/`. The root Kustomize entry point and direct-root YAML discovery remain unchanged. The overlays use `LoadRestrictionsNone` because their repository-relative resource paths intentionally leave the overlay directory to load the shared root YAML files. The flag is used only with the checked-in `k8s/overlays/{dev,test,prod}` trees; root rendering keeps Kustomize's default restriction. This audit added an `environment` metadata and pod-template label to each overlay and CI assertions for each rendered environment.

The root build, all three overlays, the existing embedded CI Kubernetes validator, focused overlay assertions, workflow YAML parse, and focused service tests passed. The full backend suite was attempted and reproduced a Windows asyncio Proactor socket-pair startup hang in `tests/test_compensation.py::test_retry_compensation_rejects_non_failed_saga`; it was interrupted after faulthandler captured the blocked socket accept. Placeholder AWS account, region, IRSA roles, ECR image tag values, API Gateway integration, and production sizing prevent deployment readiness.

## Initial repository and integration state

- `git status --short --branch` showed `feature/phase-3-kubernetes...origin/feature/phase-3-kubernetes [ahead 6]`, with the Phase 3 working changes uncommitted.
- HEAD is `58353ff`, identical to the locally recorded `origin/dev`. The CI repair commit `9509b3a` is an ancestor of HEAD. The previous report's statement that it was not integrated is stale and corrected here.
- No fetch was performed, so the local remote-tracking refs may be stale. `gh` is unavailable; live PR status, required checks/reviews, and current remote ancestry were not verified. The six-commit ahead count is relative to the local tracking ref only.

## Existing Kubernetes architecture

The base directory has a Namespace, shared ConfigMap, four ServiceAccounts, four Deployments, and four ClusterIP Services. The workloads are the GraphQL gateway and the station-reservation, billing-wallet, and energy-dispatch services. The three FastAPI services expose `/health`; the gateway has no HTTP health endpoint and retains TCP startup/liveness/readiness probes. Existing resource requests/limits, non-root/read-only container security settings, rolling update strategy, and SAGA/service boundaries are preserved.

The base has no public Service or Ingress in its root Kustomize graph. The existing `canary-service.yaml` is discovered by the root CI YAML scanner but is not referenced by root Kustomize. The environment overlays do not add or route traffic through that Ingress.

## Kustomize graph and loader decision

The root `k8s/kustomization.yaml` references eight root YAML resource files: `namespace.yaml`, `configmap.yaml`, `serviceaccounts.yaml`, `gateway-deployment.yaml`, `gateway-service.yaml`, `station-reservation.yaml`, `billing-wallet.yaml`, and `energy-dispatch.yaml`. None of these references an overlay. The dependency direction is therefore overlays to root resources, with no root-to-overlay edge.

The previous `resources: - ../../` attempt loaded the parent `k8s/` directory as a Kustomize root. Because that directory contains the overlay currently being built, Kustomize's directory-root cycle detection rejected it even though there is no manifest dependency cycle. I reproduced the same cycle using a temporary isolated overlay and `kubectl kustomize --load-restrictor LoadRestrictionsNone ...`; the probe exited 1 and was removed. The overlays instead list the eight root resource files individually using paths such as `../../namespace.yaml`; the relaxed loader permits these trusted repository-relative paths without recursively loading the parent directory.

The CI change applies `--load-restrictor LoadRestrictionsNone` only to the three checked-in environment overlay builds. It does not change the default root build or the existing `Path("k8s").glob("*.yaml")` scan. Root validation still runs before the overlay step. CI assertions now check unique rendered objects, environment labels, namespace, environment and table values, images, replica counts, resource requests/limits, health probes, and ClusterIP-only Services. The default root build and existing manifest discovery scan are unchanged. Do not use the relaxed loader on arbitrary user-supplied directories or external manifest trees.

## Overlay configuration

Each overlay sets `ENVIRONMENT`, the SAGA table and the three service `TABLE_NAME` values to the corresponding `dev`, `test`, or `prod` DynamoDB names. The names match the application environment guard and Terraform table naming: `aegisvolt-<environment>-{stations,wallets,dispatch,sagas}`. Existing internal URLs, all three feature-flag keys and their false defaults, ports, probes, and resource settings are preserved.

Replica counts are one for dev and two for test/prod. The test/prod counts retain the existing base value; the prod value is explicitly not approved production sizing because there is no load-test evidence. No resource sizing was introduced by these overlays.

Image transformation targets the existing ECR naming scheme `aegisvolt/<environment>/<workload>`. Account, region, and tag are visibly marked `CHANGE_ME_*`; `CHANGE_ME_SHA` must be replaced with the full immutable source commit SHA produced/approved by the image pipeline before deployment. No registry account, AWS region, credential, or real image digest was invented. Terraform declares ECR immutable tags, but that AWS-side setting is not verified live here.

The IRSA annotations use the role names generated by the Terraform module for each workspace and service account, with account IDs left as placeholders. No Kubernetes Secret or credential was added: workloads use their service accounts/IRSA and AWS SDK credential chain. Role existence, OIDC association, DynamoDB access, and the target account remain unverified until approved infrastructure is deployed.

## Terraform, networking, and observability dependencies

Terraform declares a private EKS API endpoint, private subnet node group, four workload IRSA roles, environment-specific DynamoDB tables, immutable ECR repositories, and CloudWatch log groups. The overlays' table names, role names, and repository paths align with those declared naming patterns.

Terraform's EKS administrator access entries are optional and `eks_admin_principal_arns` defaults to an empty list; no EKS access principal is configured in the checked-in environment tfvars. Cluster operator access therefore remains unresolved. AWS account and region values, ECR account, IRSA account IDs, and image SHA also remain placeholders.

The API Gateway Terraform module is still only a regional HTTP API shell: it has no route, integration, VPC Link, or private API/execute-api VPC endpoint integration. The required private API Gateway architecture remains incomplete. Kubernetes Services are `ClusterIP` and do not substitute for that private API integration.

Application containers write to container stdout/stderr, which the platform can collect when a log agent is installed. Terraform declares CloudWatch log groups and IAM log write permissions, but no EKS pod log collector/CloudWatch agent is declared in the inspected Kubernetes or Terraform files. Correlation IDs remain part of the application/SAGA request data; this change adds no logging implementation or monitoring stack.

## Files changed

- Added `k8s/overlays/dev/kustomization.yaml` and `patches.yaml`.
- Added `k8s/overlays/test/kustomization.yaml` and `patches.yaml`.
- Added `k8s/overlays/prod/kustomization.yaml` and `patches.yaml`.
- Updated `.github/workflows/ci.yml` with an overlay-render step using the explicit relaxed loader.
- Updated `docs/REQUIREMENTS_TRACEABILITY.md`, `project-management/CURRENT_TASK.md`, and `project-management/IMPLEMENTATION_STATUS.md`.
- Added this report.

No base manifests were moved, duplicated, or changed. No application, test, Terraform, or Dockerfile was changed.

## Validation results

| Validation | Result |
|---|---|
| `kubectl version --client=true` | Passed; kubectl v1.34.1, embedded Kustomize v5.7.1. The requested loader flag was also exercised successfully by all overlay builds. |
| `kubectl kustomize k8s` | Passed, exit 0. |
| `kubectl kustomize --load-restrictor LoadRestrictionsNone k8s/overlays/dev` | Passed, exit 0; 14 Kubernetes objects rendered. |
| `kubectl kustomize --load-restrictor LoadRestrictionsNone k8s/overlays/test` | Passed, exit 0; 14 Kubernetes objects rendered. |
| `kubectl kustomize --load-restrictor LoadRestrictionsNone k8s/overlays/prod` | Passed, exit 0; 14 Kubernetes objects rendered. |
| Existing embedded CI root manifest validator | Passed when its Python validation block was extracted from `.github/workflows/ci.yml` and executed locally. It still scans only `k8s/*.yaml`; 16 YAML documents were read, including the Kustomization document, and expected workload/service/account/config references and selectors passed. |
| Overlay configuration assertions | Passed locally for all three renders: 14 unique resources per overlay, expected environment labels, table names, ECR environment paths and `CHANGE_ME_SHA`, workload counts, replicas, probes, resource bounds, and ClusterIP services. |
| Kubernetes schema validation | Kustomize parsing and YAML parsing passed. No `kubeconform`/`kubeval` binary or cluster schema validation was available, so this audit does not claim API-server schema validation. No invalid fields were found in the static review of the manifests and rendered objects. |
| CI workflow YAML parse and embedded root validator | Passed with installed PyYAML. The CI overlay shell step itself could not execute because Windows denied `bash.exe` access; equivalent render/assertions ran directly in Python. GitHub Actions was not dispatched. |
| CI job graph review | Existing backend, frontend, Terraform, and Kubernetes jobs remain present. The four Docker image builds still depend on all four validation jobs; no required job condition or dependency was removed. |
| `python -m pytest -q -o faulthandler_timeout=10` | **Blocked/interrupted** at `tests/test_compensation.py::test_retry_compensation_rejects_non_failed_saga`. Faulthandler reproduced AnyIO/asyncio Windows Proactor `_make_self_pipe` waiting in `socket.socket._fallback_socketpair` / `socket.accept`; the run was interrupted and no suite summary was produced. No application code or tests were changed. |
| `python -m pytest -q tests/test_services.py` | Passed on this audit: 5 tests, 54 warnings, 1.26 s. |

The GitHub workflow's shell render step was not executed on this Windows host because `bash.exe` access was denied. Its embedded Python root validator was executed locally; the equivalent overlay render/assertions and root/overlay Kustomize commands were run directly. No GitHub workflow run is claimed.

## Limitations and next steps

1. Configure the approved AWS account, region, EKS admin principal, IRSA role account IDs, and immutable image SHA using Terraform outputs and image publication records before a deployment review.
2. Obtain production replica/resource sizing from load testing and owner approval; current prod replicas are inherited values, not a readiness claim.
3. Complete the required private API Gateway/VPC endpoint backend integration in its authorized infrastructure scope.
4. Configure and validate pod log collection into the declared CloudWatch log groups.
5. Run Kubernetes API schema validation in CI or an approved Kubernetes validation environment.
6. Re-run the full backend suite in a runner where Windows Proactor TestClient startup does not hang (or an approved Linux/CI environment); inspect actual GitHub checks and reviews.
7. Refresh Git refs and inspect live GitHub checks/reviews before claiming current `dev` is healthy; local ancestry confirms CI repair `9509b3a` is already included at `58353ff`.
8. Review this uncommitted diff, then open `feature/phase-3-kubernetes` -> `dev` only after current remote ancestry and required checks are verified. Do not merge until checks and approvals pass.

No Terraform plan/apply, AWS API, cluster connection, `kubectl apply`, deployment, commit, push, or branch modification was performed.
