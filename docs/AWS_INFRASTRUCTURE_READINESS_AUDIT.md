# AegisVolt AWS Infrastructure Readiness Audit

**Audit date:** 2026-11-21

## Executive summary

Terraform is not ready: fmt check fails on invalid HCL in infra/variables.tf and infra/bootstrap/bootstrap.tf. Network defines only public subnets; EKS lacks worker capacity; API Gateway has no integration; workload IAM is absent. State buckets are placeholders and native S3 locking is absent.

The current task record reports 16 backend tests and frontend build/lint/tests passed locally. This does not prove Docker, Floci, AWS or EKS behavior. Compose config check passed. Git shows clean main and no remote. No official DOCX was found. AWS profile identity check failed; no resources were queried.

## Findings

| Severity | Finding | Evidence |
|---|---|---|
| CRITICAL | Terraform parser failure | infra/variables.tf, infra/bootstrap/bootstrap.tf |
| CRITICAL | State configuration placeholder/mismatch | infra/backend/*.hcl, infra/bootstrap/bootstrap.tf |
| HIGH | Missing private subnets, worker nodes, endpoints | infra/modules/network/main.tf, infra/modules/eks_ecr/main.tf |
| HIGH | Deploy workflow conditions conflict with dependencies | .github/workflows/deploy.yml |
| HIGH | Runtime table creation lacks least-privilege boundary | common/dynamodb.py |

## Architecture and repository

The local stack is React/Vite to GraphQL gateway to three FastAPI services and separate DynamoDB tables; Prefect checks one gateway and counts SAGA states. Compose provides Floci and dev only. AWS resources are declared but none were verified deployed.

Repository areas: services, gateway, frontend, common, infra, k8s, .github/workflows, observability/prefect, tests, docs, project-management.

Frontend spec, roadmap and traceability contain stale pre-frontend claims. Current task/status and actual source are newer.

## Backend and frontend

Backend/SAGA is PARTIALLY IMPLEMENTED. Conditional connector locks, atomic wallet debit/refund, activation/telemetry persistence, SAGA lease/retry and compensation are in services and gateway. Activation failure refunds then releases; insufficient funds releases reservation. Current task reports 16 Moto/in-process tests. No Docker/Floci/AWS proof. Recovery is retry-driven, events share one 400 KB-limited item and are not exposed in GraphQL.

Flags ENABLE_DYNAMIC_SURGE_PRICING, ENABLE_FAST_CHARGE_BOOST, SIMULATE_CHARGER_HARDWARE_FAULT are read-only process values. Only hardware fault is gated; pricing/boost behavior is absent. ensure_table creates missing tables, so AWS runtime may need create-table rights. Demo wallets seed USD balance.

Frontend has Overview, Stations, SAGA history, Flags. Reported build/lint/tests and local proxy mutation passed; not rerun. Limits: polling rather than streaming, dev only, demo data, no SAGA event details/paging or flag edits. Dashboard health checks only station service.

## Terraform and networking

Terraform readiness is MISSING. infra/versions.tf requires Terraform >=1.5 and AWS provider ~>5.0. fmt check failed: infra/variables.tf has invalid type/default block; bootstrap has same issue and invalid nested encryption block. Backend HCL uses CHANGE_ME buckets; bootstrap accepts one bucket; DynamoDB lock configured, native use_lockfile absent. Versioning/AES256 are declarations only. tfvars are identical; no workspace guard. Seven PAY_PER_REQUEST/PITR tables are declared, but source uses four; unused feature-flags/reservations/billing tables and no GSIs.

Network module declares a VPC and two public subnets only: no IGW/routes/NAT/private subnets/security groups/endpoints. API Gateway has no route/integration/auth/VPC link. HIGH deployment blocker.

## DynamoDB, EKS, security

DynamoDB is partial locally; environment token in names does not prove account/data isolation. No AWS metadata inspected. Generic id keys fit simple current operations; access-pattern/GSI/retention design absent; some scans used.

EKS/Kubernetes samples are partial and undeployed. EKS has no node group/Fargate, worker role, workload OIDC, add-ons/logging. K8s only has gateway stable/canary, no service workloads/config. Service selector matches both tracks, no base ingress/controller. Canary annotation says 10%; script checks rollout/restarts, not traffic/errors/rollback.

Only EKS control-plane IAM role exists. No service DynamoDB roles, workload identity, API auth, secrets design, or explicit KMS. Compose keys are Floci-only. .gitignore does not establish history safety; no remote or hosting protection evidence.

## CI/CD and observability

PR workflow runs pytest, frontend install/build, Terraform fmt/init-backend=false/validate and Compose config. Omits lint/frontend tests, container build, E2E, plan. Deploy workflow dependencies/conditions can skip test/prod jobs; manual dispatch also runs dev; dev auto-applies without plan. No K8s deployment or rollback. Branch-protection script only prints a command. Git has only main locally.

Terraform creates one 14-day log group and SNS topic. No structured app logs, per-service groups, alarms/dashboard. Prefect checks one gateway, scans one SAGA table, counts states and publishes CloudWatch metrics; no multi-env/service/cross-table audit. Broad catch maps health errors to false; metric task writes AWS and was not run.

## Cost risks

No regional estimate. EKS standard control plane is currently $0.10/hour before workers etc.; 730 hours is about $73. [EKS pricing](https://aws.amazon.com/eks/pricing/) NAT is charged per hour and GB ([NAT pricing](https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-pricing.html)); public IPv4 is $0.005/hour ([VPC pricing](https://aws.amazon.com/vpc/pricing/)); DynamoDB charges reads/writes/storage and PITR ([DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/)). S3 versions, CloudWatch ingestion/retention, load balancers, image pulls, egress, cross-AZ and NAT data also cost money.

For demos prefer Compose/Floci. If AWS is required, evaluate short-lived single dev, budget alerts/teardown, whether EKS is mandatory, endpoints vs NAT, and minimum tables/backups.

## Requirement status

| Requirement | Status | Evidence/gap |
|---|---|---|
| Reserve/pay/activate/telemetry | PARTIALLY IMPLEMENTED | Services exist; telemetry simulated. |
| Real-time status | PARTIALLY IMPLEMENTED | Polling; one station; no stream. |
| Reserve/activate UI | IMPLEMENTED locally | Current GraphQL operation; local mutation reported. |
| Feature flags | PARTIALLY IMPLEMENTED | Read-only process values; pricing absent. |
| SAGA history/compensation | PARTIALLY IMPLEMENTED | Summary/retry; no details/paging. |
| GraphQL contract | PARTIALLY IMPLEMENTED | Existing operations; missing management/detail. |
| Three services on Kubernetes | PARTIALLY IMPLEMENTED | Dockerfiles; gateway manifest only. |
| SAGA compensation paths | IMPLEMENTED locally | Source/tests reported; runtime unverified. |
| Terraform modules | MISSING | Invalid HCL/incomplete resources. |
| S3 state/versioning/native lock | MISSING | Placeholders/mismatch/no use_lockfile. |
| Workspaces dev/test/prod | PARTIALLY IMPLEMENTED | Prefix exists; identical vars/no guard. |
| VPC/private/endpoints | MISSING | Public subnets only. |
| DynamoDB/environment isolation | PARTIALLY IMPLEMENTED | Local tables/name guard only. |
| CloudWatch structured logs | MISSING | One log group. |
| Prefect audit | PARTIALLY IMPLEMENTED | One gateway/state counts. |
| Branch protection | NEEDS VERIFICATION | No remote. |
| Promotion workflow | MISSING | Conditions conflict. |
| PR tests/plan | PARTIALLY IMPLEMENTED | Some checks; plan/E2E/lint absent. |
| Canary | PARTIALLY IMPLEMENTED | 10% annotation; no traffic/error/rollback evidence. |
| Zero downtime | NEEDS VERIFICATION | Never exercised. |
| Full layered testing | PARTIALLY IMPLEMENTED | No Docker/browser/AWS E2E. |

## Blockers and recommended order

1. CRITICAL: Fix HCL and validate locally with backend disabled.
2. CRITICAL: Reconcile backend bucket/bootstrap, versioning, native lock, public access and recovery.
3. HIGH: Complete network, EKS compute, API integration and least-privilege IAM.
4. HIGH: Repair CI targeting, plan/apply approval, promotion, canary and rollback.
5. MEDIUM: Add structured correlated logs, health checks and Prefect consistency audit.
6. MEDIUM: Complete Docker/Floci/browser E2E and update stale docs.
7. Approve feature/pricing/currency rules and spending cap before implementation/deployment.
8. Only after separate AWS approval provision disposable dev from reviewed plan, verify SAGA, then decide test/prod.

## Console preparation and future commands

No Console inspection possible. Before approved phase inspect account/region, budget, state bucket and locks, VPC/routes/endpoints, EKS/load balancers, IAM roles, table schemas/backups/encryption, CloudWatch retention, GitHub secrets/rules. Do not create resources or share identifiers. Profile failed authentication; existing resources are unknown.

After HCL repair, local commands:

    terraform -chdir=infra fmt -check -recursive
    terraform -chdir=infra init -backend=false
    terraform -chdir=infra validate

Only after approved backend setup:

    terraform -chdir=infra init -backend-config=backend/dev.hcl
    terraform -chdir=infra workspace select dev
    terraform -chdir=infra plan -var-file=envs/dev.tfvars -out=dev.tfplan
    terraform -chdir=infra show dev.tfplan
    terraform -chdir=infra apply dev.tfplan

Do not run init against current placeholder backend; apply or Kubernetes deployment requires separate approval.

## Assumptions and safety

- Official DOCX absent; findings use source, repo docs, pasted request.
- No AWS session/metadata, Git remote, cluster, or Docker runtime evidence.
- Python/frontend outcomes come from CURRENT_TASK.md, not rerun to avoid artifacts.
- Public AWS prices at audit date are not region-specific estimates.
- No AWS resources modified, Terraform init/plan/apply/destroy/state access, or Kubernetes deployment. No source/config file changed. This report is the only new file.

## Phase 1 Terraform repair status

**Verification date:** 2026-11-21

### Resolved

- `infra/variables.tf` was rewritten with valid Terraform variable/type/validation syntax.
- `infra/bootstrap/bootstrap.tf` was rewritten with valid HCL and a valid nested S3 encryption configuration.
- Terraform now requires at least 1.10.0, compatible with the native S3 backend lockfile.
- AWS provider constraints remain `~> 5.0`; local initialization selected AWS provider 5.100.0.
- The bootstrap no longer declares a DynamoDB lock table.
- The bootstrap now declares S3 public-access blocking.
- The dev, test, and prod backend HCL files now use `use_lockfile = true`.
- DynamoDB locking (`dynamodb_table`) was removed from the backend files.
- Environment-specific state keys remain `aegisvolt/dev.tfstate`, `aegisvolt/test.tfstate`, and `aegisvolt/prod.tfstate`.
- Region and state-bucket values use explicit `CHANGE_ME` placeholders in environment configuration.
- The root configuration now guards Terraform workspace names to `dev`, `test`, or `prod`.

### Remaining in Phase 1

- The actual AWS region and three state bucket names require user-provided values.
- The bootstrap S3 bucket and public-access configuration describe resources but were not created or initialized.
- Remote state was not accessed.
- Native lockfile behavior is configured but not runtime-tested against a real S3 backend.
- The provider lock file `infra/.terraform.lock.hcl` was created by backend-disabled initialization and is not a deployed-resource change.

### Verified local commands

- `terraform -chdir=infra fmt -recursive` — passed.
- `terraform -chdir=infra fmt -check -recursive` — passed.
- `terraform -chdir=infra init -backend=false` — passed; provider 5.100.0 downloaded and initialized.
- `terraform -chdir=infra validate` — passed.

No apply, destroy, plan against a remote backend, workspace creation, AWS request, S3 bucket creation, DynamoDB table creation, VPC/EKS creation, or remote-state modification was performed.

## Phase 2 AWS architecture status

**Verification date:** 2026-11-21

### Phase 2 implementation

- `infra/modules/network/main.tf` now declares a configurable VPC, two or three
  public/private subnet pairs, an Internet Gateway, public routing, private
  routing, optional NAT gateways, and least-privilege HTTPS VPC-endpoint access.
- Gateway endpoints are declared for S3 and DynamoDB. Interface endpoints are
  declared for ECR API, ECR DKR, CloudWatch Logs, and STS. These endpoints
  support private workloads without making application ports public.
- NAT gateway creation defaults to disabled. One NAT gateway or one per AZ can
  be enabled explicitly because it incurs hourly and data-processing charges.
- `infra/modules/eks_ecr/main.tf` now declares:
  - EKS control-plane and EC2 worker IAM roles.
  - A private-subnet managed node group with configurable capacity and instance
    type defaults.
  - CoreDNS, kube-proxy, and VPC CNI add-ons.
  - Private EKS API access and disabled public EKS API access.
  - Cluster control-plane logging.
  - An EKS OIDC provider and workload-identity IAM roles.
  - Separate station, wallet, dispatch, and gateway IRSA roles.
- DynamoDB declarations now contain only `stations`, `wallets`, `dispatch`, and
  `sagas`. These match the four inspected application table contracts. The
  unused `feature-flags`, `reservations`, and `billing` declarations were
  removed.
- DynamoDB tables remain on-demand, use partition key `id`, use AWS-managed
  server-side encryption, and enable point-in-time recovery. Runtime table
  creation is not granted by the workload policies.
- Per-service CloudWatch log groups now cover gateway and all three FastAPI
  services. Cluster logging is declared separately.
- The API Gateway HTTP API has a default stage, but no route or integration.
  This is intentional: the current K8s source provides no verified private
  load balancer, VPC-link, backend URI, or public ingress target contract.

### DynamoDB/application consistency

The source contracts verified as of 2026-11-21 use:

| Workload | Environment table name | Terraform key | Partition key |
|---|---|---|---|
| station-reservation | `aegisvolt-{env}-stations` | `stations` | `id` |
| billing-wallet | `aegisvolt-{env}-wallets` | `wallets` | `id` |
| energy-dispatch | `aegisvolt-{env}-dispatch` | `dispatch` | `id` |
| GraphQL gateway SAGA | `aegisvolt-{env}-sagas` | `sagas` | `id` |

No GSIs or sort keys are used in the inspected application access paths. Wallet
and dispatch workflows use DynamoDB transactions with the same partition key.
The application startup helpers call `ensure_table`, but Terraform precreates
the declared tables and the IRSA policies intentionally omit CreateTable.

### IAM and security decisions

- EKS control-plane and worker roles are separate.
- Application workloads receive one IRSA role per service.
- DynamoDB actions are scoped to only that workload's table ARN.
- Workload policies omit create-table, account-wide DynamoDB, VPC, EC2,
  AdministratorAccess, and wildcard AWS actions.
- CloudWatch writes are scoped to the matching application log-group ARN.
- Application secrets are not modeled because the inspected source uses
  environment variables and AWS SDK credential discovery rather than a secret
  value contract.
- The EKS API endpoint is private-only in Terraform. Human approval and a
  management/network path are required for cluster administration.

### Cost implications

The following remain costs or cost risks:

- EKS control plane: approximately $73/month for 730 hours at the audit's
  stated $0.10/hour reference, before worker nodes.
- Managed worker nodes: default `t3.medium` count is 1, with capacity 1-3.
- NAT gateway: disabled by default. Enabling it adds an hourly charge and
  data-processing charges; per-AZ NAT adds one cost per AZ.
- Public IPv4/EIP charges apply to NAT and load balancers.
- DynamoDB PAY_PER_REQUEST charges reads, writes, storage, and PITR.
- CloudWatch log ingestion and 14-day default retention vary by volume.
- ECR, VPC interface endpoints, load balancers, and cross-AZ traffic may add
  charges.

Cheaper alternatives include retaining Compose/Floci for development,
disabling NAT when endpoints cover required AWS access, using 1 worker, and
deferring private-only cluster management until a VPN or equivalent path exists.

### Human decisions and blockers

- Provide the real AWS region and state bucket names.
- Decide whether private-only EKS API access is acceptable and provide the
  management network path.
- Decide whether NAT gateway egress is required for runtime dependencies.
- Decide public versus private GraphQL ingress.
- Provide a valid Kubernetes load-balancer/ingress backend contract and DNS
  target before adding API Gateway routes or a VPC link.
- Decide environment-specific node size and deletion-protection values.
- Decide KMS key ownership if AWS-owned DynamoDB/EBS encryption is insufficient.
- Approve the architecture and spending level before AWS provisioning.

### Phase 2 validation

- `terraform -chdir=infra fmt -recursive` — passed.
- `terraform -chdir=infra fmt -check -recursive` — passed.
- `terraform -chdir=infra init -backend=false` — passed. AWS provider 5.100.0
  and TLS provider 4.4.2 were initialized locally.
- `terraform -chdir=infra validate` — passed.

No AWS authentication, AWS API query, remote-state command, Terraform plan,
workspace operation, apply, destroy, or infrastructure creation was performed.
