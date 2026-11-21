# Phase 4 Canary Readiness Audit

**Audit date:** 2026-11-21  
**Scope:** Repository and local configuration only. No AWS identity check, AWS API call, cluster connection, or GitHub settings inspection was performed.

## Executive summary

**Deployment readiness: NOT READY.** The repository does not currently provide a working canary traffic path or a safe remote deployment path. A manifest named `k8s/canary-service.yaml` declares a 10% NGINX canary Ingress, but Kustomize does not include it, there is no stable Ingress, the target service selects the ordinary gateway Deployment, and no NGINX controller is declared. It does not route 10% of real traffic.

Terraform declares a private-only EKS endpoint, a managed node group, and core add-ons. These are desired infrastructure definitions only; no AWS resources or add-ons were checked live. The GitHub-hosted runners used by current workflows cannot be assumed to reach that private API. No private-network runner is configured in the repository.

The safe implementation strategy is to retain the current workloads and image promotion controls, document the exact prerequisites, and keep deployment fail-closed. No controller, load balancer, IAM role, cluster access policy, or application telemetry has been fabricated or provisioned.

## Current state and evidence

| Area | Repository evidence | Readiness |
|---|---|---|
| Workloads | Kustomize includes one Deployment and ClusterIP Service for the gateway and each of the three FastAPI services. | Declared only; not verified in a cluster. |
| Stable/canary workloads | Workloads have no `track` labels or separate stable/canary Deployments. | Missing. |
| Traffic split | `k8s/canary-service.yaml` contains an NGINX canary annotation set to `10`, but is not in `k8s/kustomization.yaml`; no base Ingress or controller is present. Its backend names `gateway`, whose selector accepts the single ordinary gateway workload. | No functioning traffic split. |
| EKS endpoint | `infra/modules/eks_ecr/main.tf` sets private access true and public access false. | Private-only is declared; actual endpoint reachability is unknown. |
| Compute and add-ons | Terraform declares a managed node group plus CoreDNS, kube-proxy, and VPC CNI add-ons. | Desired definitions exist; deployed capacity/add-on health is unverified. |
| Images | Kustomize uses dev ECR paths with `CHANGE_ME` account, region, and tag placeholders. ECR names are environment-qualified and Terraform declares immutable tags. | Not deployable from these manifests as checked in. No real image digest was verified. |
| Health checks | Station Reservation, Billing Wallet, and Energy Dispatch expose real `GET /health` handlers used by HTTP probes. The GraphQL gateway has no `/health` route; its probes are TCP socket checks on port 8000. | Microservice process checks exist; gateway has only a socket check. None were run in Kubernetes. |
| Application metrics | Prefect checks one gateway URL and publishes SAGA state counts. The app exposes no request counter, HTTP 5xx rate, latency histogram, or Prometheus endpoint. | Not suitable for traffic-based canary analysis. |
| CloudWatch | Terraform declares log groups, cluster logs, and an SNS topic. Prefect's metric task publishes SAGA counts. There are no app request error/latency alarms or dashboards in the inspected configuration. | No canary signal. Declarations are not deployed evidence. |
| OIDC deployment permissions | Existing GitHub OIDC module creates only ECR publisher/promoter roles when enabled. It has no EKS deployment role. | Deployment identity and Kubernetes authorization are missing. |
| GitHub runner path | Current workflows use GitHub-hosted Ubuntu runners. No private self-hosted runner or deployment workflow is configured. | Cannot reach the private EKS API by assumption. |
| Terraform readiness | Backend and tfvars include `CHANGE_ME` values. Remote state was not initialized. | Remote operation is not ready. |
| GitHub Environments | Docs specify protected environment names and reviewers. Hosting settings were not inspected. | Reviewer/branch rules require verification in GitHub. |

## Components reusable as-is

- The four service images use full commit SHA tags in the image publishing flow and ECR immutability is declared in Terraform.
- Digest-preserving dev-to-test and test-to-prod promotion is separate from deployment and should remain unchanged.
- Kubernetes Deployments already specify resource requests/limits, non-root security contexts, and rolling-update settings.
- The three microservices have real HTTP health routes. Keep the gateway's TCP probe until an application-level readiness endpoint is designed and tested.
- Terraform already declares private EKS endpoint access, private subnets, worker capacity, and standard EKS add-ons. These remain unverified infrastructure declarations.
- GitHub OIDC ECR roles remain separate from any future deployment role.

## Missing dependencies and blockers

1. **Traffic router:** Choose and provision an approved ingress/data-plane controller. NGINX Ingress is the only hint in the repository, but it is not installed or configured. Argo Rollouts is not present. Do not treat the unused annotation as traffic management.
2. **Consistent whole-application routing:** A gateway-only split could pair a new gateway with old microservices. A future design must route compatible gateway and service versions together or establish and test backward-compatible contracts. Current service discovery points each gateway at the shared stable service names.
3. **Request metrics:** Add trustworthy request counts, status classes, and latency measurements before defining error-rate/latency thresholds. SAGA counts and TCP probes do not measure the routed request population.
4. **Private deployment runner:** Provide an approved runner inside a network path to the private EKS endpoint, or another approved secure deployment mechanism. Do not make the EKS endpoint public as a workaround.
5. **Deployment identity and Kubernetes authorization:** Define a separate GitHub OIDC role with exact repository/environment trust, scoped `eks:DescribeCluster`, and a deliberately narrow EKS access entry/Kubernetes RBAC mapping. No such role/access mapping is implemented or live-verified.
6. **Image and environment inputs:** Resolve account, region, cluster, role, environment, and actual promoted SHA/digests through approved configuration. Do not replace placeholders with guesses.
7. **GitHub protection:** Configure and verify per-environment reviewer requirements and branch restrictions in GitHub. No remote or hosting settings were available to inspect.
8. **Capacity and persistence compatibility:** Confirm the node group can schedule temporary parallel canary workloads and that the old/new app versions remain compatible with shared DynamoDB tables. No capacity/runtime evidence exists.
9. **Terraform:** Repair and validate current Terraform/backend configuration in its separately approved scope before remote plans or provisioning.

## Deployment readiness by environment

| Environment | Image path | Deployment readiness | Reason |
|---|---|---|---|
| dev | Manual dev publication exists | **Blocked** | No router, private runner, deploy role, live cluster verification, or resolved manifest placeholders. |
| test | Digest promotion exists | **Blocked** | Same deployment blockers; protected GitHub environment configuration is unverified. |
| prod | Digest promotion exists | **Blocked** | Same blockers plus production approval rules must be verified in GitHub. |

## Strategy decision

No operational traffic-splitting controller exists in repository configuration, and live cluster inspection was intentionally not performed. Therefore this phase does **not** declare 10%, 25%, 50%, or 100% stages as implemented. The unused NGINX annotation is not activated or expanded. Adding a controller, new ingress infrastructure, or an Argo Rollouts dependency without cluster/network approval would not be safe.

The minimum next design is to select one traffic router and confirm it exists in each cluster; then model all four services as a versioned application unit, add a same-version canary backend path, and use measured request metrics. A private deployment runner and separately authorized deployment role are prerequisites. Until then, release and rollback remain manual image promotion procedures, not automatic canary behavior.

## Intentionally left unmodified

- `k8s/canary-service.yaml` and application deployment manifests: no verified router/traffic semantics exist to safely wire them.
- All Terraform resources, AWS credentials, cluster settings, IAM roles, and EKS access policies.
- Application API behavior, health endpoints, CloudWatch/Prefect instrumentation, and persistent data schema.
- Existing CI, image publish, digest promotion, and Terraform plan workflows.
- GitHub environments, branch protections, secrets, and variables.

