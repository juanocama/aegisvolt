# CI/CD pipeline, branch governance and canary

Spec sections 3.1–3.3. Workflows: `.github/workflows/ci.yml` (pre-merge) and
`.github/workflows/deploy.yml` (post-merge).

## Branch model and protection

- Permanent branches: `dev`, `test`, `prod`. Work happens on `feature/*`.
- Promotion is linear: `feature/* → dev → test → prod`. The `promotion-guard`
  job fails any PR whose source/target pair breaks this chain (for example
  `feature/x → test` or `dev → prod`).
- Branch protection (configured in GitHub for `dev`, `test`, `prod`): pull
  request required, force push blocked, deletion blocked, and these required
  status checks: `promotion-guard`, `lint-build`, `unit-tests`,
  `integration-tests`, `e2e-tests`, `terraform-static`, `terraform-plan`,
  `kubernetes`.

## Pre-merge (pull request into dev/test/prod) — `ci.yml`

| Job | What it proves |
|---|---|
| `promotion-guard` | Source branch is allowed for the target branch. |
| `lint-build` | Python compiles; live GraphQL schema equals `docs/graphql/schema.graphql`; frontend ESLint + Vitest + Vite build; all five Docker images build; frontend image refuses to start without a GraphQL upstream. |
| `unit-tests` | Feature flags (DynamoDB source, isolation, runtime toggle), canary promotion gate, observability/correlation, Prefect audit rules, pipeline wiring. |
| `integration-tests` | GraphQL gateway + the three FastAPI services in-process against DynamoDB (Moto): SAGA success, insufficient funds, hardware-fault compensation, failed compensation + retry, idempotent replays, concurrency. |
| `e2e-tests` | `docker compose up` (Floci DynamoDB, 3 services, gateway, nginx frontend) then `e2e/`: dashboard, flags, happy path + replay + idempotency conflict + stop/release, insufficient funds, **runtime fault flag → refund → release**, frontend SPA and `/graphql` proxy. |
| `terraform-static` | `fmt -check`, `init -backend=false`, `validate`. |
| `terraform-plan` | Assumes the read-only OIDC plan role, `terraform workspace select ${{ github.base_ref }}` (the PR **target** branch) and runs `terraform plan -lock=false`; plan text uploaded as an artifact and summarized on the run. |
| `kubernetes` | Kustomize renders root + dev/test/prod overlays; selectors, service accounts, weighted canary routing, per-env tables/flags/ALB names; kubeconform strict schemas (Kubernetes 1.37). |

## Post-merge (push to dev/test/prod) — `deploy.yml`

1. **Target detection:** `TARGET_ENVIRONMENT = github.ref_name` (the branch that
   received the merge). The job runs in the GitHub Environment of the same name,
   whose `AWS_DEPLOY_ROLE_ARN` only that environment can assume (OIDC subject
   `repo:<owner>/<repo>:environment:<env>`).
2. `terraform init -backend-config=backend/<env>.hcl`,
   `terraform workspace select <env>`, `terraform apply -auto-approve
   -var-file=envs/<env>.tfvars` — only that workspace/state
   (`s3://…/env:/<env>/aegisvolt/terraform.tfstate`) changes.
3. Build and push images tagged with the commit SHA (ECR repositories are
   `IMMUTABLE`); mirror the Load Balancer Controller image (no NAT).
4. Session Manager tunnel to the private EKS API (no public endpoint), install
   the AWS Load Balancer Controller (Pod Identity role), render the overlay with
   `scripts/render_deploy_overlay.py` keeping the **stable gateway on its
   current image**, apply, wait for rollouts.
5. Wire the private API Gateway → VPC Link → internal GraphQL ALB (second apply
   with the real ALB ARN/DNS).
6. **Canary** (`scripts/canary_deploy.py`): new gateway image to
   `gateway-canary`, ALB weighted forward **80% stable / 20% canary**,
   synthetic traffic for 5 minutes, then the gate reads CloudWatch metrics
   `AegisVolt/<env>` `Requests-gateway-canary` and `Http5xx-gateway-canary`
   (log metric filters on `/aegisvolt/<env>/gateway-canary`) plus pod
   restarts/readiness. Promote to 100% only if ≥20 requests, 5xx rate ≤1%, no
   restarts and ready; otherwise automatic rollback (weight 0, canary scaled to 0,
   job fails).
7. Post-deploy E2E through the internal frontend ALB → private API Gateway → EKS.

The other services roll with `maxUnavailable: 0` and readiness probes (no
downtime); the canary applies to the GraphQL gateway, the only service that
receives external traffic.

## One-time bootstrap (manual, documented, not done by CI)

1. Account-level GitHub OIDC provider:
   `aws iam create-open-id-connect-provider --url https://token.actions.githubusercontent.com --client-id-list sts.amazonaws.com`
2. First `terraform apply` per workspace by an administrator (creates the
   `…-github-terraform-plan` and `…-github-deploy` roles).
3. GitHub: repository variables `AWS_REGION=us-east-1` and
   `TERRAFORM_PLAN_ROLE_ARN=<terraform output github_plan_role_arn>`;
   Environments `dev`, `test`, `prod` (deployment branch = same name) with
   variable `AWS_DEPLOY_ROLE_ARN=<terraform output github_deploy_role_arn>`.

Until these exist, `terraform-plan` and `deploy` fail closed with an explicit
message; they never fall back to another environment.
