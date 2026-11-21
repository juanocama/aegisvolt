# AegisVolt Canary Deployment Guide

## Status

Canary deployment is **blocked and not implemented**. This guide describes the verified repository state and the prerequisites for a safe implementation. No 10%, 25%, 50%, or 100% production traffic stages currently exist. The NGINX annotation in `k8s/canary-service.yaml` is not included in Kustomize and does not route requests.

See [PHASE4_CANARY_READINESS_AUDIT.md](PHASE4_CANARY_READINESS_AUDIT.md) for the evidence and environment-by-environment status.

## Architecture overview

The declared app has a GraphQL gateway and three FastAPI services. Kubernetes Services are ClusterIP and select the single Deployment for each app. The gateway calls the shared service DNS names. There is no configured ingress controller, Argo Rollouts installation, service mesh, ALB Ingress, weighted target group, or other traffic-splitting path in the repository.

Terraform declares a private-only EKS API, private worker subnets, a managed node group, and EKS core add-ons. These are Terraform declarations, not proof of provisioned resources. The GitHub-hosted runner cannot be presumed to reach that private API.

## Canary mechanism and traffic distribution

**Selected mechanism: none.** The existing NGINX canary Ingress is unbundled and has no matching stable ingress/controller contract. It points to the ordinary `gateway` Service, which does not select a separate canary Deployment. Do not apply it or describe it as a canary.

Before implementing a router, the project owner must select and provision an approved controller/data plane and validate it in dev. A future design must route the gateway and compatible microservice version as one release unit. Shared service DNS currently makes a gateway-only canary unsafe to assume compatible.

## Stages and analysis

No rollout stages, observation periods, sample counts, error-rate thresholds, or latency thresholds are configured. The repository has no reliable HTTP request counters/status metrics or latency histograms. Do not infer error-rate or latency safety from pod readiness or SAGA state counts.

Available process checks:

- Station Reservation: real `GET /health` returns service status.
- Billing Wallet: real `GET /health` returns service status.
- Energy Dispatch: real `GET /health` returns service status.
- Gateway: no HTTP `/health`; current Kubernetes probes check only TCP port 8000.

These checks have not been exercised in EKS and do not by themselves establish successful customer requests or gateway-to-service behavior.

## Automated rollback

There is no automated rollout or rollback controller/script. The current known-good image is not captured by a deployment record because no deploy is performed. ECR SHA tags and digest-preserving promotion provide immutable release inputs, but they do not implement rollback. Until a rollout mechanism is approved, recovery is a separately reviewed promotion of a previous approved SHA/digest; do not claim automated rollback or delete images.

A future rollback must retain prior stable image digests, stop advancing traffic, restore the whole compatible application unit, wait for workload health plus representative successful requests, and record the failed/previous SHA, reason, and verified result. It must report failure if restoration is not healthy.

## GitHub Actions, AWS prerequisites, and protection

Existing `ci.yml`, `publish-images.yml`, `promote-images.yml`, and `terraform-plan.yml` remain separate. The publisher/promoter roles are ECR-only and must not be reused for EKS access. No deployment workflow or deployment IAM role exists.

Required before enabling deployment:

1. An approved private-network deployment runner that can reach the private EKS API. Do not expose the API publicly or provision a persistent runner without approval.
2. A separately designed OIDC role trusted only by the exact repository and `eks-deploy-<environment>` subject, with no static AWS keys. Restrict AWS actions and EKS Kubernetes authorization to the intended cluster/namespace and operations.
3. A real router installed and healthy, a version-compatible path for all four workloads, and request-level metrics.
4. Existing ECR promotion completed for the exact full Git SHA; use the promoted immutable images/digests and do not rebuild during promotion/deployment.
5. GitHub Environments `eks-deploy-dev`, `eks-deploy-test`, and `eks-deploy-prod`, with branch constraints and required reviewers. Production approval must be verified in GitHub settings.
6. Approved cluster name, AWS region, role ARN, account/repository values, and environment config. Current manifests/backend contain placeholders; none are supplied here.

No GitHub settings or AWS resources were inspected or modified for this audit.

## Local validation

Render the checked-in base without applying it:

```powershell
kubectl kustomize k8s
```

The rendered image references are placeholders and are not deployable. Do not use `kubectl apply` as a validation command. No rollout/rollback test can pass until a traffic router and local or disposable test cluster are available.

## Troubleshooting and manual recovery

- `k8s/canary-service.yaml` is not in the base; its annotation alone has no effect.
- Gateway TCP probe passing means a socket accepted a connection; it is not an HTTP readiness check.
- A private EKS endpoint requires a private network path; AWS credentials alone do not provide connectivity.
- If a future canary fails, stop traffic promotion, restore the previous verified SHA/digests using the protected promotion/release process, and confirm all workloads and representative requests recover before reporting success.
- Never overwrite immutable tags or delete ECR images during rollback.

## Cost and operations

No new AWS resources or recurring costs were introduced. A future canary typically needs temporary capacity for parallel workloads, plus the cost of its router, metrics/log ingestion, and a private runner/network path. Estimate these against the actual environment and obtain approval before provisioning. Terraform EKS declarations do not prove a running cluster or cost.

