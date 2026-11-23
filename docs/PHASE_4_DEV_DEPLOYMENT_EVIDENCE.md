# Phase 4 — Temporary `dev` deployment evidence (2026-11-23)

Account `065656773005`, `us-east-1`, workspace `dev` only. Authorized by the
user for a same-day demonstration with a USD 4 operational ceiling, no
promotional credits (Free plan account with card attached).

## Timeline (UTC)

| Step | Time / result |
|---|---|
| Pre-flight discovery | No pre-existing EKS/EC2/NAT/ELB/VPCE/EIP/EBS/DynamoDB/ECR. Pre-existing and untouched: default VPC, REST API `strangler-gateway`, `/aws/lambda/legacy-monolith`, `/aws/lambda/modern-orders`. |
| State bucket | `aegisvolt-tfstate-065656773005-us-east-1` created (versioned, SSE-S3, public access blocked). **Kept** (≈2 KB, ≈USD 0). |
| `terraform apply` (reviewed plan) | 17:46:53 — 87 resources, 0 NAT, 0 EIP. |
| Fix applies | CloudWatch agent config, API policy drift, GraphQL integration (VPC Link + stage), billing IAM. |
| Teardown complete | 18:43 — Terraform state empty, independent discovery clean. |

Billable runtime ≈ 57 min. Estimated cost ≈ USD 0.45–0.50 (EKS 0.10/h, node +
access host 0.052/h, 12 endpoints × 1 AZ 0.12/h, 2 internal ALBs ≈ 0.06/h,
CloudWatch). Cost Explorer lags ~24 h; month-to-date at teardown still showed
the pre-session USD 0.128.

## Architecture actually deployed

- Private EKS 1.37 (public endpoint `False`), 1× t3.medium, no NAT; interface
  endpoints in one AZ (`interface_endpoint_az_count = 1`).
- Operator access: Session Manager host (no public IP, no inbound rule) with
  port forwarding to the private EKS API; no VPN was created (cost/time).
- AWS Load Balancer Controller v3.6.3 via Helm, image mirrored into private ECR,
  dedicated Pod Identity role with the unmodified upstream IAM policy,
  WAF/WAFv2/Shield disabled (no endpoints).
- Two internal ALBs created by the controller: `aegisvolt-graphql`,
  `aegisvolt-frontend`; both `inbound-cidrs: 10.0.0.0/16`.
- Private REST API → execute-api VPC endpoint → VPC Link v2 → internal GraphQL
  ALB. React SPA served by unprivileged nginx, which proxies same-origin
  `/graphql` to the private API.

## E2E results (run from inside the VPC via SSM `AWS-RunShellScript`)

| Check | Result |
|---|---|
| `dashboard`, `flags`, `stations` via private API GW | 200, `environment=dev`, `servicesOk=true`, 3 official flags `false` |
| Same queries via frontend ALB → nginx → API GW | 200, identical data |
| SPA `/` via frontend ALB | 200, React root present |
| `reserveAndActivateCharge` (first run) | `CHARGE_UNCERTAIN` — **AccessDenied: billing role lacked `dynamodb:UpdateItem` required by `TransactWriteItems` Update items**. Fixed in Terraform and applied. |
| Same-key retry after fix | `COMPLETED`, wallet 100 → 87.5 (charged once) |
| Replay | same SAGA, `COMPLETED`, no extra debit |
| Same key, different amount | GraphQL error "Idempotency key was already used for a different request" |
| Second wallet on busy connector | `FAILED` (409 from reservation), no charge |
| Telemetry after activation | `active`, 0.0 kW (simulated baseline) |
| Correlation ID in CloudWatch | `f8b0ed47-…` found in `/aws/containerinsights/dev-aegisvolt/application` |
| API from the internet | connection fails (private API, no public DNS route) |
| ALB schemes | both `internal` |

## Defects found by the live run and fixed in the repository

1. Billing workload IAM missing `dynamodb:UpdateItem` (transaction items need the per-item action).
2. CloudWatch Observability add-on crash-looped with all metric pipelines disabled; now basic (non-enhanced) Container Insights with explicit agent config.
3. REST API inline policy drifted on every plan (`execute-api:/*` rewritten by AWS); moved to `aws_api_gateway_rest_api_policy` with the execution ARN.
4. nginx upstream TLS failed with default `proxy_ssl_verify_depth 1`; set to 3.
5. Dev overlay omitted `gateway-ingress.yaml` and left `AWS_DEFAULT_REGION=CHANGE_ME_AWS_REGION`.

## Teardown verification (independent AWS discovery after destroy)

EKS, EC2, VPC (non-default), VPC endpoints, ENIs, EBS volumes, snapshots, EIPs,
NAT, ALBs, target groups, VPC Links, ECR, DynamoDB, `dev-aegisvolt*` IAM
roles/policies, OIDC providers, SNS: **none remaining**. The controller-created
`/aws/containerinsights/dev-aegisvolt/performance` log group (not managed by
Terraform) was deleted manually; the stale SSM session was terminated.

Remaining by design: the Terraform state bucket (≈USD 0/month).

## Redeploy procedure (≈25 min)

1. `terraform -chdir=infra workspace select dev`; `plan -var-file=envs/dev.tfvars`; review; apply.
2. Build images, push to `aegisvolt/dev/*` with an immutable SHA tag; mirror
   `public.ecr.aws/eks/aws-load-balancer-controller:v3.6.3` into
   `aegisvolt/dev/mirror/aws-load-balancer-controller`.
3. `aws ssm start-session --document-name AWS-StartPortForwardingSessionToRemoteHost`
   to the EKS endpoint (local 8443); kubeconfig `server=https://127.0.0.1:8443`
   with `tls-server-name=<eks endpoint host>`.
4. Helm install the controller (`clusterName`, `region`, `vpcId`, mirrored image, WAF/Shield off).
5. Deploy a local, uncommitted overlay over `k8s/overlays/dev` that sets image
   tags, IRSA role ARNs and `GRAPHQL_UPSTREAM_HOST=<api id>.execute-api.us-east-1.amazonaws.com`.
6. Second apply with `enable_graphql_integration=true`, `gateway_alb_arn`, `gateway_alb_dns_name`.
7. Demo: port-forward via SSM to the frontend ALB DNS on port 80 and open `http://localhost:<port>`.
8. Teardown: delete Ingresses (wait for ALBs to disappear), uninstall Helm, `terraform destroy`, verify.

## Open items

- Client VPN is still not implemented; Session Manager port forwarding is the
  documented secure substitute for operators/demo.
- Full pytest still blocked locally by the Windows Proactor hang; focused suites pass (25).
- Kubeconform runs only in CI.
