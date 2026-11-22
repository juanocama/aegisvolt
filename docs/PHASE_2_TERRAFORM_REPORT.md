# AegisVolt Phase 2 Terraform Readiness Report

**Audit date:** 2026-11-22

## 1. Initial findings

The Terraform root, bootstrap, environment configuration, and six infrastructure
modules existed before this phase. The configuration already had:

- Terraform workspaces guarded to `dev`, `test`, or `prod`
- DynamoDB tables for stations, wallets, dispatch, and Sagas
- Public and private subnets
- Optional NAT gateways
- S3/DynamoDB gateway endpoints
- EC2, ECR, CloudWatch Logs, and STS interface endpoints
- A private-only EKS API endpoint
- Managed node groups and core EKS add-ons
- Workload IRSA roles
- Environment-qualified ECR repositories
- CloudWatch application and cluster log groups
- A GitHub Actions OIDC image-publish/promote module

Known issues verified in the existing source included placeholder backend
buckets and regions, separate placeholder bucket names that did not match the
single-bucket bootstrap design, duplicate cluster-name composition, one
inconsistent application log-group convention, and an API Gateway module without
a route or backend integration.

No AWS resource was created or modified.

## 2. Files inspected

- `infra/versions.tf`
- `infra/variables.tf`
- `infra/providers.tf`
- `infra/main.tf`
- `infra/outputs.tf`
- `infra/bootstrap/bootstrap.tf`
- `infra/backend/dev.hcl`
- `infra/backend/test.hcl`
- `infra/backend/prod.hcl`
- `infra/envs/dev.tfvars`
- `infra/envs/test.tfvars`
- `infra/envs/prod.tfvars`
- `infra/modules/network/main.tf`
- `infra/modules/dynamodb/main.tf`
- `infra/modules/eks_ecr/main.tf`
- `infra/modules/api_gateway/main.tf`
- `infra/bootstrap/.terraform.lock.hcl`
- `infra/modules/observability/main.tf`
- `infra/modules/github_actions_ecr/main.tf`
- `.github/workflows/terraform-plan.yml`

## 3. Files modified

- `infra/main.tf`
- `infra/variables.tf`
- `infra/outputs.tf`
- `infra/bootstrap/bootstrap.tf`
- `infra/backend/dev.hcl`
- `infra/backend/test.hcl`
- `infra/backend/prod.hcl`
- `infra/modules/observability/main.tf`
- `infra/modules/eks_ecr/main.tf`
- `infra/modules/api_gateway/main.tf`
- `project-management/CURRENT_TASK.md`
- `project-management/IMPLEMENTATION_STATUS.md`
- `docs/PHASE_2_TERRAFORM_REPORT.md`

## 4. Issues fixed

### Cluster naming

The cluster name is now derived as:

```text
<workspace>-<cluster_name>
```

For example, the `dev` environment with the existing `aegisvolt` cluster base
produces `dev-aegisvolt`, instead of the previous
`dev-aegisvolt-aegisvolt`.

### Remote-state design

All three backend files now refer to the same explicit shared-bucket pattern:

```text
CHANGE_ME-aegisvolt-terraform-state
```

Their keys remain isolated:

- `aegisvolt/dev.tfstate`
- `aegisvolt/test.tfstate`
- `aegisvolt/prod.tfstate`

This reconciles the root backend design with the bootstrap module, which creates
one supplied bucket. Native S3 lockfile support remains `use_lockfile = true`
and requires Terraform 1.10 or newer.

The bootstrap module now exports `state_bucket_name` and `state_bucket_arn`.
It creates the supplied bucket with:

- S3 versioning enabled
- AES256 server-side encryption
- Public ACL, policy, and bucket access disabled
- No access policy or cost controls inferred beyond the repository

### CloudWatch names

Application log groups now use a consistent environment/service convention:

```text
/aegisvolt/<environment>/<service>
```

The cluster log group remains:

```text
/aws/eks/<environment>-<cluster-base>/cluster
```

The Terraform names do not prove application JSON logging, metrics, alarms,
dashboards, or log delivery.

### EKS administrative access

The EKS module now accepts an optional list of IAM role or user principal ARNs.
Each supplied principal receives a STANDARD EKS access entry and the
`AmazonEKSClusterAdminPolicy` cluster policy.

No principal ARN is supplied by default. This avoids fabricating an AWS account
role or granting access without an approved operator identity.

### API Gateway outputs

The API Gateway module now exports its API ID and regional endpoint. It remains
a shell: no route, integration, authorizer, VPC link, load balancer, DNS name,
or private API configuration was invented.

### Input validation

The root `region` variable now rejects values containing `CHANGE_ME`.

The optional EKS administrator ARN list is validated as an IAM role or user
ARN. Node sizing already has a root workspace precondition requiring
`node_min_size <= node_desired_size <= node_max_size`.

## 5. Issues intentionally not fixed

- Real AWS account IDs, regions, bucket names, operator role ARNs, and domain
  names were not added.
- The environment tfvars remain fail-closed placeholders.
- Backend HCL values remain placeholders until a real shared bucket exists.
- The API Gateway routes and backend architecture remain undecided.
- Private API Gateway, ALB/NLB, VPC Link, and DNS integration were not added.
- NAT gateway behavior remains opt-in and does not infer a production cost
  policy.
- Terraform was not applied.
- AWS credentials and APIs were not used.
- Kubernetes, GitHub workflows, application code, and frontend code were not
  changed.

## 6. Environment configuration design

The workspaces define environment isolation:

- `dev`: `aegisvolt-dev-*` DynamoDB tables and `dev-aegisvolt` cluster naming
- `test`: `aegisvolt-test-*` DynamoDB tables and `test-aegisvolt` cluster naming
- `prod`: `aegisvolt-prod-*` DynamoDB tables and `prod-aegisvolt` cluster naming

The ECR repositories remain environment-qualified:

```text
aegisvolt/<environment>/<image>
```

The tfvars files currently share common scaffold values. This is intentional
until approved test/prod sizing, CIDRs, node types, retention, and deletion
policies are documented.

## 7. Remote-state bootstrap and initialization

1. Supply the actual AWS region and globally unique shared state bucket name.
2. Initialize the bootstrap module.
3. Apply the bootstrap module only with explicit AWS approval.
4. Record the `state_bucket_name` output.
5. Replace `CHANGE_ME-aegisvolt-terraform-state` in all backend HCL files with
   that exact bucket name.
6. Replace `CHANGE_ME_AWS_REGION` with the selected region.
7. Initialize the root module with the matching environment backend.
8. Select or create the matching Terraform workspace.
9. Run a read-only plan.
10. Review and separately approve any apply.

Example local commands, without a real backend or remote operation:

```powershell
Set-Location C:\Users\iamju\Desktop\patrones\aegisvolt\infra
terraform fmt -check -recursive
terraform init -backend=false -input=false
terraform validate -no-color
terraform validate -no-color -var-file='envs/dev.tfvars'
```

Do not run a remote backend init or plan until the placeholders are replaced
with reviewed real values and AWS access is explicitly authorized.

## 8. EKS access strategy

The private EKS API endpoint requires network reachability as well as AWS
identity authorization. An approved operator needs a VPC route or an existing
private administrative path. The cluster is not made public.

Set `eks_admin_principal_arns` only to reviewed IAM role or user ARNs. GitHub
Actions has no Terraform apply role or EKS deployment role in this design.
Those roles require separate implementation decisions and host configuration.

## 9. Networking assumptions

The network module uses public and private subnets across two or three selected
availability zones. Private subnets do not receive general internet egress
unless an operator enables NAT gateways.

The module already declares S3, DynamoDB, EC2, ECR API, ECR Docker, CloudWatch
Logs, and STS connectivity. Private nodes can pull ECR images and write logs
through these endpoints if routing and IAM permit it.

NAT is intentionally optional because NAT hourly and data-processing costs
must be approved. An external package repository or third-party dependency not
covered by these endpoints may require NAT or additional private endpoints.

No `execute-api` endpoint is declared because the API Gateway integration
architecture is not established.

## 10. DynamoDB consistency findings

The module declares exactly four application tables:

| Application | Environment table |
|---|---|
| Station reservation | `aegisvolt-<environment>-stations` |
| Billing wallet | `aegisvolt-<environment>-wallets` |
| Energy dispatch | `aegisvolt-<environment>-dispatch` |
| GraphQL SAGA | `aegisvolt-<environment>-sagas` |

Each uses:

- Partition key `id`
- On-demand billing
- AWS-owned encryption
- Point-in-time recovery
- Optional deletion protection
- No secondary indexes

These names match the application environment contract. No persistent
feature-flags table was added.

The application and Terraform both need deployed tables before service startup.
No runtime DynamoDB table deployment was verified.

## 11. API Gateway status

The API Gateway module creates a regional HTTP API shell and `$default` stage.
It does not expose `/graphql` because no route or integration exists.

Missing human decisions are:

1. Public or private API exposure
2. GraphQL backend component and stable network address
3. Whether an ALB/NLB load balancer is provisioned
4. Whether API Gateway VPC Link is required
5. Whether the backend is reached directly or through a load balancer
6. Custom DNS, authorizer, CORS, and route policy

Implementation must stop until these values are supported by the Kubernetes
deployment architecture.

## 12. CloudWatch naming convention

Application:

```text
/aegisvolt/<environment>/<service>
```

Cluster:

```text
/aws/eks/<environment>-<cluster-base>/cluster
```

Services are:

- `gateway`
- `station-reservation`
- `billing-wallet`
- `energy-dispatch`

## 13. IAM findings

### Workload IAM

Each workload IRSA role has table access limited to its intended DynamoDB table
and write access to its matching application log group.

### GitHub Actions ECR

The optional module:

- Looks up the account GitHub OIDC provider
- Restricts publishers/promoters to the reviewed GitHub repository
- Restricts subjects to named GitHub environments
- Scopes image actions to the environment-qualified ECR repositories

The publisher only exists for `dev`; test/prod use promoter roles with source
and target repository scopes.

### Missing roles

No Terraform-plan role, Terraform-apply role, or EKS deployment role is
implemented. This is intentional: no account or repository role ARN was
available and the GitHub workflows do not currently authorize deployment.

## 14. Exact validation commands and results

| Command | Result |
|---|---|
| `terraform fmt -check -recursive` | Passed |
| `terraform init -backend=false -input=false` | Passed; AWS 5.100.0 and TLS 4.4.2 providers reused |
| `terraform validate -no-color` | Passed |
| `terraform validate -no-color -var-file='envs/dev.tfvars'` | Passed local syntax/reference validation |
| Bootstrap `terraform init -backend=false -input=false` | Passed |
| Bootstrap `terraform validate -no-color` | Passed |
| AWS API calls | Not performed |
| Remote backend initialization | Not performed |
| Terraform plan/apply/destroy | Not performed |

Environment tfvars still contain real-account placeholders. A plan must fail
closed until the placeholders are replaced and an approved AWS environment,
credentials, and backend are available.

## 15. Remaining blockers

- Shared state bucket name
- AWS region
- AWS account identity
- EKS operator IAM principal ARN
- Private/public API Gateway decision
- GraphQL backend address/load balancer architecture
- Approved test/prod sizing and CIDRs
- Terraform remote-plan role
- Optional EKS deployment role
- Live provider-plan/provider-credential verification

## 16. Human operator procedure

1. Review the architecture and approve a region, shared state bucket, and
   environment sizing.
2. Bootstrap the shared bucket in the approved account.
3. Update all three backend HCL files and matching tfvars.
4. Supply optional approved EKS administrator ARNs.
5. Resolve API Gateway routing and backend integration.
6. Create or authorize the Terraform plan role.
7. Initialize the remote backend.
8. Select or create the environment workspace.
9. Run and review `terraform plan`.
10. Apply only after a separate deployment approval.
