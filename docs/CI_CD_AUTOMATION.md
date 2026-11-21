# AegisVolt CI/CD Automation

## Workflow map

| Workflow | Trigger | AWS access | Result |
|---|---|---|---|
| Continuous integration | Pull requests and pushes to dev/test/prod | None | Python tests/syntax, frontend lint/tests/build, Terraform backend-disabled validation, Kustomize render, four independent Docker builds without push |
| Publish AegisVolt images | Manual dispatch from matching dev/test/prod branch | GitHub OIDC, protected ecr-publish-* environment | Pushes the four app images to that environment's ECR repositories with the full commit SHA tag |
| Promote image digests | Manual dispatch from the source branch | GitHub OIDC, protected ecr-promote-test/prod environment | Copies source ECR manifest to the next environment without rebuilding and verifies the digest is unchanged |
| Protected Terraform remote plan | Manual dispatch | GitHub OIDC, protected terraform-plan-* environment and remote state | Explicit-backend terraform plan only; no apply or destroy |
| Canary deployment readiness | Manual dispatch | No AWS credentials; `contents: read` only | Fails closed while private runner, traffic router, request metrics, and deployment identity are unconfigured; it does not deploy |

CI builds images only after the validation jobs pass. The build job uses root context and the existing Dockerfiles. Image names are gateway, station-reservation, billing-wallet, and energy-dispatch. The frontend is not included in the ECR pipeline. Pull request and branch builds do not publish.

## Commands reflected by CI

Backend dependency file: root requirements.txt, installed with Python 3.12. CI runs:

    python -m compileall -q common gateway services tests
    python -m pytest -q

No Python linter is configured in the repository. Frontend uses Node 24.15.0 and the unchanged package-lock.json:

    npm ci
    npm run lint
    npm test
    npm run build

Terraform static validation uses the declared minimum-compatible Terraform 1.10 line and never initializes the backend in CI:

    terraform fmt -check -recursive
    terraform init -backend=false -input=false
    terraform validate

Kubernetes validation uses kubectl kustomize k8s to render the checked-in base and PyYAML to parse every manifest, including the unbundled canary ingress. It checks expected workloads, ServiceAccounts, ConfigMap references, selectors, and Service/Ingress targets. It does not contact a cluster. Placeholder account, region, role, image URL, and image tag values remain intentionally unresolved.

The default Docker job builds each existing Dockerfile using the repository root as build context, tags with github.sha, and uses per-image BuildKit GitHub Actions cache. It does not push. The root .dockerignore excludes Git metadata, credentials/config, Terraform state/cache, Python caches, and frontend dependencies/build output.

## Branch and GitHub Environment policy

Intended promotion is feature branch -> PR to dev -> PR from dev to test -> PR from test to prod. Do not push directly to dev/test/prod. This checkout has only local main and no Git remote, so the hosting repository and branch policies cannot be confirmed or changed here.

In repository settings, configure branch rulesets for dev, test, and prod:

- Require pull requests and these Continuous integration checks: Backend tests and syntax; Frontend lint, tests, and build; Terraform static validation; Render Kubernetes base; and each of the four Build <image> (no push) matrix checks.
- Require branches to be up to date before merge; block force pushes and deletion.
- Restrict direct updates to those branches to the approved PR merge process.
- Set prod to require at least one reviewer and prevent bypass where course/team policy allows.

Create GitHub Environments before enabling protected operations:

- ecr-publish-dev, ecr-publish-test, ecr-publish-prod
- ecr-promote-test, ecr-promote-prod
- terraform-plan-dev, terraform-plan-test, terraform-plan-prod

Require reviewers for all ecr-publish environments, ecr-promote-test, ecr-promote-prod, and all terraform-plan environments. Test promotion should be reviewed; production publishing/promotion must be explicitly approved. GitHub Environment protection is configured in the hosting UI, not by these workflow files. A manual workflow trigger alone does not create reviewer protection.

Restrict each GitHub Environment’s deployment branch rule to its matching
environment branch. The publish, promote, and remote-plan workflows also check
the selected source/target branch in the job before requesting AWS credentials.

The GitHub-hosted runner source branch must match the target environment for image publication. Promotion accepts only dev -> test and test -> prod, requires the SHA to exist on the source branch, and verifies each target image digest. It does not change Kubernetes manifests or deploy workloads. Rollback means selecting the previously approved commit SHA/digest and manually promoting it under the same review gates; no automatic rollback is implemented.

## Repository and environment variables

Set these as GitHub Actions repository variables (not secrets):

| Variable | Used by | Value source |
|---|---|---|
| AWS_REGION | ECR login/publish/promotion and remote plan | Must match the selected Terraform environment; current Terraform configs contain CHANGE_ME_AWS_REGION. |
| AWS_ACCOUNT_ID | ECR registry URI | Account identifier for the approved AWS account. Do not infer it from a sample. |

Set the following variables separately in each named GitHub Environment:

| Variable | Environments | Value source |
|---|---|---|
| ECR_PUBLISH_ROLE_ARN | ecr-publish-dev/test/prod | publisher role ARN output from the matching Terraform workspace |
| ECR_PROMOTION_ROLE_ARN | ecr-promote-test/prod | promoter role ARN output from the target Terraform workspace |
| TERRAFORM_PLAN_ROLE_ARN | terraform-plan-dev/test/prod | separately provisioned read/remote-state-lock-only role ARN |

The repository slug is currently unknown because there is no Git remote. When an approved Terraform run configures GitHub roles, set the root Terraform input github_repository to the exact owner/repository slug. The optional role module stays absent while this input is empty.

The manual remote plan intentionally fails before AWS authentication while the selected backend HCL or tfvars contains CHANGE_ME or while required variables are unset. Do not add bucket names, account IDs, or regions to source control merely to make the workflow pass.

## GitHub OIDC and IAM design

The new optional Terraform module looks up the account-level provider at https://token.actions.githubusercontent.com; it does not create one. The EKS IRSA provider in the EKS module has a cluster-specific issuer URL and is not the GitHub provider.

Before enabling roles, an AWS administrator must inspect IAM OpenID Connect providers in the correct account. If the GitHub provider already exists, verify its issuer and sts.amazonaws.com audience and use that provider. If it is absent, create it once through the approved account bootstrap process, then rerun Terraform. Never create a duplicate blindly. If Terraform is to manage an existing provider, import/reconcile its exact ARN into the chosen state first; do not let two states own the same account-level provider.

The optional module creates environment-specific publisher roles and (test/prod only) promoter roles. Trust conditions require both audience sts.amazonaws.com and the exact subject:

    repo:<owner>/<repository>:environment:ecr-publish-<dev|test|prod>
    repo:<owner>/<repository>:environment:ecr-promote-<test|prod>

Configure the corresponding GitHub Environment name exactly. Do not replace these subjects with a wildcard branch/repository subject. Publisher permissions include ECR login plus upload/push operations scoped to the four matching environment repositories. Promoter permissions read only the preceding environment's four images and write only the target environment's four repositories. Neither role has Terraform provisioning permissions, EKS workload permissions, AdministratorAccess, or IAM role-management rights. The module consumes the pre-existing GitHub OIDC provider through a data lookup and leaves the EKS IRSA roles separate.

The ECR repositories are configured for immutable tags. Publication uses the full Git commit SHA. Promotion uses Skopeo for registry-to-registry copying with digest preservation, verifies the target digest, and refuses an existing conflicting tag. It does not rebuild. Terraform source changes still require a reviewed Terraform plan/apply in a separately approved infrastructure phase before repository immutability and IAM roles exist in AWS.

## Terraform remote plan prerequisites

PR CI is backend-disabled and cannot read remote state. The remote plan is a separate manual workflow protected by a GitHub Environment. It uses only the selected infra/backend/<environment>.hcl and infra/envs/<environment>.tfvars, selects an already-existing workspace, and has no apply/destroy step or plan artifact upload.

Before enabling it:

1. Replace the exact backend bucket and region placeholders through approved environment configuration; align them with the bucket/bootstrap and native S3 lockfile design.
2. Confirm the state bucket, versioning, encryption, public-access controls, key, and use_lockfile configuration. No backend values are fabricated here.
3. Create a dedicated GitHub OIDC plan role, distinct from publisher, promoter, and EKS roles. Its permissions must include state read/list and S3 lockfile coordination in the selected bucket/prefix, plus provider read/describe actions scoped to this stack. Lock coordination requires narrowly scoped state lock writes; the plan role must have no infrastructure create/update/delete, IAM, ECR push, or EKS workload permissions.
4. Store its ARN as TERRAFORM_PLAN_ROLE_ARN in the matching protected GitHub Environment and require reviewers.
5. Verify state/workspace existence and review the exact plan output in the protected run. This task did not initialize or access remote state.

The remote plan is read-oriented but not a zero-write operation: Terraform acquires/releases a state lock. Its IAM role therefore needs lock coordination permissions. No remote plan was executed.

## Validation and limits

Action versions use stable major tags. The current machine does not have actionlint, standalone kustomize, or kubeconform. Local validation on 2026-11-21: Terraform fmt check passed; backend-disabled init succeeded using the already-cached provider mirror; Terraform validate could not load the AWS/TLS provider schemas (plugins did not respond). Frontend lint passed, 2 test files/3 tests passed, production build passed; kubectl kustomize rendered successfully. Python pytest did not complete: the run remained on its first compensation test with no result and was interrupted. YAML parsing of all workflow files and the Kustomize file passed with local PyYAML; workflow expressions were not run through actionlint. GitHub Actions themselves were not executed.

No GitHub repository settings, environments, variables, or secrets were created. No AWS command, remote plan, image publication, cluster connection, branch operation, or deployment was performed.

## Phase 4 canary deployment status

No deployment workflow, EKS deployment role, or automatic rollback is implemented. `.github/workflows/canary-readiness.yml` is a non-deploying guard that makes missing prerequisites visible; even if its readiness variables are set, it fails with an explicit message that no rollout implementation exists. It has no OIDC permission and does not contact AWS or Kubernetes.

Terraform declares private-only EKS API access. A GitHub-hosted runner is not a private network path. Deployment requires an approved private runner and a separately scoped OIDC role, plus Kubernetes authorization. The existing ECR publisher and promoter roles must not be reused.

The unused NGINX canary Ingress is not included by `k8s/kustomization.yaml`; no Ingress controller or stable/canary Deployment pair is declared. Therefore the configured annotation is not evidence of weighted traffic. No app request error-rate or latency metrics exist for rollout analysis. See [the Phase 4 audit](PHASE4_CANARY_READINESS_AUDIT.md) and [deployment guide](PHASE4_CANARY_DEPLOYMENT_GUIDE.md).

## Phase 3.1 remediation

**Remediation date:** 2026-11-21

### Frontend runtime

- Frontend CI uses Node 24.15.0 for `npm ci`, lint, tests, and production build.
- Vitest 5.1.1 requires Node `^22.12.0 || ^24.0.0 || >=26.0.0`; the lockfile
  also requires Node 24.15.0 or newer for jsdom 31.0.1.
- `package.json` has no incompatible `engines` declaration.
- `frontend/package-lock.json` remains unchanged.

### ECR retry and digest behavior

The publish workflow preflights all four repositories before the first push.
It:

1. detects existing full-SHA tags;
2. builds existing tags locally and calculates the intended OCI digest;
3. skips matching digests;
4. fails without overwrite if a tag has an unexpected digest;
5. publishes only absent tags; and
6. verifies each pushed digest against ECR.

This makes reruns of a partial or complete publication safe while preserving
immutable ECR tags. No `latest` tag is used. The publisher IAM policy includes
`ecr:DescribeImages` scoped to the four target repositories.

### Supply-chain pinning

Third-party workflow actions are pinned to verified full commit SHAs with
readable version comments. Pin decisions cover checkout, setup Python/Node,
Terraform, kubectl, Docker Buildx/build-push, AWS credential configuration,
and ECR login actions.

`id-token: write` is job-scoped to publish, promote, and remote-plan jobs.
CI jobs remain `contents: read` only.

Skopeo promotion currently uses Ubuntu apt installation. That package is not
an exact reproducible version; replace it with a pinned official Skopeo
container digest or verified binary/package release before production promotion.

### Terraform plan fail-closed behavior

Remote-plan dispatch now fails before AWS credentials or backend initialization
when the branch/environment mismatch, placeholders, AWS region, or plan role
ARN is incomplete.

### Manual configuration still required

Repository variables:

- `AWS_REGION`
- `AWS_ACCOUNT_ID`

Protected environment variables:

- `ECR_PUBLISH_ROLE_ARN`
- `ECR_PROMOTION_ROLE_ARN`
- `TERRAFORM_PLAN_ROLE_ARN`

AWS Terraform and GitHub Environment configuration must also provide the real
S3 backend bucket and region, exact GitHub owner/repository slug, OIDC provider
state, ECR role ARNs, and existing Terraform workspace names.

### Phase 3.1 validation

- `python -m pytest -q`: passed, 16 tests.
- Compensation test alone: passed.
- Frontend lint: passed under Node 24.
- Frontend tests: 2 files and 3 tests passed.
- Frontend build: passed under Node 24.
- Terraform fmt check: passed.
- Terraform validate: passed.
- `kubectl kustomize k8s`: passed.
- Four workflow files parsed successfully with PyYAML.
- All four Dockerfiles built successfully with Docker Desktop.
- `actionlint`: unavailable locally.
- Docker engine: accessible, and no Docker context changes were made.

The four Dockerfiles, compensation test, and Terraform validation are
implemented and passed locally. GitHub-hosted execution, AWS publication,
remote Terraform plan, and Kubernetes deployment remain unverified.

## Phase 3.2 final CI/CD corrections

**Remediation date:** 2026-11-21

### Final publication model

Initial publication is restricted to the `dev` environment. The publish
workflow has no test/prod input and runs only under `ecr-publish-dev` on the
`dev` branch. Test and production artifacts must arrive through promotion.

The workflow preflights the four dev repository SHA tags before it builds or
pushes anything. It distinguishes:

- `ImageNotFoundException`: the immutable tag is genuinely absent.
- `RepositoryNotFoundException`: fail closed.
- `AccessDeniedException`: fail closed.
- throttling or request-limit errors: fail closed.
- any other AWS describe-images error: fail closed.

For an existing immutable tag, the workflow skips rebuild and overwrite. It
uses the ECR digest as the canonical existing artifact. For a missing tag, it
builds once with the exact Dockerfile/context and pushes that artifact. The
Buildx metadata digest is compared with the digest returned by ECR after push.

This approach is safe for partial-publish retries: existing tags are skipped,
missing tags are published once, and immutable tags prevent overwrites. It
does not rebuild an existing tag and does not claim to prove that an existing
tag is cryptographically linked to the current source commit unless its
provenance or attestation is independently recorded. The immutable-tag
convention plus the same full-SHA tag therefore prevents silent replacement,
but cannot retrospectively prove source provenance for a tag created outside
this workflow.

Every published image digest is read back from ECR. Existing image digests are
also read back during preflight and recorded in the workflow summary.

### Promotion model and IAM

Promotion remains `dev -> test -> prod` and never rebuilds an image.

The promotion workflow validates:

- exact dev-to-test or test-to-prod sequence;
- source branch equals the source environment;
- a full 40-character commit SHA;
- commit ancestry;
- source-tag existence;
- absent or matching target tag;
- target conflict refusal;
- source and target digest equality after copy.

Production promotion remains protected by `ecr-promote-prod`.

The publisher IAM role is now created only for the dev workspace. Test and
prod workspaces have no publisher role and cannot perform initial publication.
Publisher permissions remain limited to the four dev repositories.

Promoter IAM remains environment-specific and is still created only for test
and prod. It reads only the immediately preceding environment and writes only
the target environment repositories.

### Skopeo pinning

The promotion workflow uses the official Quay Skopeo stable image:

`quay.io/skopeo/stable@sha256:075359e92740bec687ed6ec8d12141bdb3666e6547dcd917657e24a7758926ed`

Verification:

- Official Skopeo release v1.25.1:
  https://github.com/podman-container-tools/skopeo/releases/tag/v1.25.1
- Quay immutable manifest for v1.25.1:
  `sha256:075359e92740bec687ed6ec8d12141bdb3666e6547dcd917657e24a7758926ed`

The image is pinned by manifest digest and executed through Docker. Registry
authentication is supplied through the GitHub runner Docker configuration.
The workflow preserves multi-platform manifests and digests with
`skopeo copy --all --preserve-digests`.

### Remaining configuration

GitHub must still configure:

- repository variables `AWS_REGION` and `AWS_ACCOUNT_ID`;
- `ecr-publish-dev`;
- `ecr-promote-test` and `ecr-promote-prod`;
- matching publisher and promoter role ARN environment variables;
- branch rules and required reviewers.

AWS must still provision and approve the OIDC provider, ECR repositories,
dev publisher role, test/promote roles, and prod promoter role. No AWS values
are inferred locally.
