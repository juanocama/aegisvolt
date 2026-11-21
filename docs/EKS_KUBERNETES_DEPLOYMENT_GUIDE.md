# AegisVolt EKS Kubernetes Deployment Guide

The manifests in `k8s/kustomization.yaml` describe the application base only.
They are locally buildable but are not deployable until the placeholder values
below are replaced.

## Workloads

The base includes:

- Gateway on port `8000`
- Station reservation on port `8001`
- Billing wallet on port `8002`
- Energy dispatch on port `8003`

All inter-workload communication uses Kubernetes DNS and ClusterIP Services:

- `http://gateway:80`
- `http://station-reservation:8001`
- `http://billing-wallet:8002`
- `http://energy-dispatch:8003`

The gateway does not expose a FastAPI `/health` endpoint. Its probes use a TCP
socket on port `8000`. The three FastAPI services use their real `/health`
HTTP endpoints.

## AWS placeholders

Before deployment, replace:

- `CHANGE_ME_AWS_REGION` in `k8s/configmap.yaml`
- `CHANGE_ME_ACCOUNT_ID` in `k8s/serviceaccounts.yaml`
- `CHANGE_ME_ECR_ACCOUNT`
- `CHANGE_ME_TAG`

Use the root Terraform outputs after infrastructure is provisioned:

- `eks_workload_role_arns`
- `ecr_repository_urls`
- `dynamodb_table_names`

For example, each ServiceAccount annotation must contain the exact matching
ARN from `eks_workload_role_arns`, not a reconstructed or AdministratorAccess
role ARN.

## Image strategy

The Kustomize base uses logical image names and explicit `CHANGE_ME_TAG` image
tags. The Terraform ECR repository convention is:

`aegisvolt/{environment}/{workload}`

The workloads use these repository names:

- `gateway`
- `station-reservation`
- `billing-wallet`
- `energy-dispatch`

Before deployment, replace the Kustomize `newName` and `newTag` values using
the repository URLs from Terraform and an immutable image tag such as a Git
commit SHA or release version.

Example build commands, not executed here:

```powershell
docker build -f gateway/Dockerfile -t <gateway-ecr-url>:<tag> .
docker build -f services/station-reservation/Dockerfile -t <station-ecr-url>:<tag> .
docker build -f services/billing-wallet/Dockerfile -t <wallet-ecr-url>:<tag> .
docker build -f services/energy-dispatch/Dockerfile -t <dispatch-ecr-url>:<tag> .
```

Pushing and image authentication require separate AWS deployment approval.

## DynamoDB

The base dev configuration uses:

- `aegisvolt-dev-stations`
- `aegisvolt-dev-wallets`
- `aegisvolt-dev-dispatch`
- `aegisvolt-dev-sagas`

For test or prod, update `ENVIRONMENT`, the three `TABLE_NAME` values, and
`SAGA_TABLE` consistently. No AWS credentials or endpoint variables belong in
the manifests.

## Public exposure

The base exposes only a ClusterIP Service for the gateway. It does not create
public ingress or API Gateway integration.

The existing `k8s/canary-service.yaml` is not included in the Kustomize base
and is not validated as a deployable public GraphQL route.

It is also not an operational weighted canary: no NGINX controller, stable
Ingress, or distinct gateway canary Deployment is configured. See the
[Phase 4 readiness audit](PHASE4_CANARY_READINESS_AUDIT.md). Do not infer
traffic distribution from its `canary-weight` annotation.
