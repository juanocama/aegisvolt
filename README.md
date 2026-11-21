# AegisVolt

Small, independent university demonstration of an EV charging reservation platform with React, GraphQL, three FastAPI microservices, DynamoDB, orchestrated SAGA, Docker/Floci, Terraform, Kubernetes, and Prefect.

## Local demo (Windows PowerShell)

```powershell
Set-Location 'C:\Users\iamju\Desktop\patrones\aegisvolt'
docker compose config --quiet
docker compose up --build -d
```

The full PowerShell dependency setup, environment configuration, readiness
checks, backend test command, and non-destructive stop procedure are in
[`docs/deployment.md`](docs/deployment.md). Start the frontend separately with
Vite. The local Compose configuration provides only the `dev` GraphQL gateway;
`test` and `prod` are not available locally.

Floci is an emulator fallback. DynamoDB also requires AWS credentials in
production. If Floci or moto is unavailable, `boto3.resource` reports the
connection error; no fake AWS resource IDs are generated.

Run tests:

```powershell
py -m pip install -r requirements.txt
py -m pytest -q
cd frontend
npm install
npm run build
```

## GraphQL
Open `http://localhost:8010/graphql`. Example mutation:

```graphql
mutation {
  reserveAndActivateCharge(
    walletId: "wallet-1"
    stationId: "st-1"
    connectorId: "c-1"
    amount: 25
    idempotencyKey: "demo-001"
  ) { success sagaId correlationId state message }
}
```

The gateway reports the read-only official flags
`ENABLE_DYNAMIC_SURGE_PRICING`, `ENABLE_FAST_CHARGE_BOOST`, and
`SIMULATE_CHARGER_HARDWARE_FAULT` from its process environment; all default to
`false`. Only the hardware-fault flag currently gates the existing
per-request fault-injection input. Local Compose provides only `dev`; the
pricing and boost flags have no business effect until their rules are approved.

## CI/CD

GitHub Actions validation, non-publishing image builds, protected ECR
publishing/promotion, OIDC role prerequisites, and the manual Terraform plan
boundary are documented in
[`docs/CI_CD_AUTOMATION.md`](docs/CI_CD_AUTOMATION.md). No workflow deploys to
EKS or runs Terraform apply.

Phase 4 canary deployment is currently blocked: no operational traffic router,
private-network deployment runner, deployment OIDC role, or request-level
canary metrics are configured. The manual canary readiness workflow fails
closed and does not contact AWS or EKS. See
[`docs/PHASE4_CANARY_READINESS_AUDIT.md`](docs/PHASE4_CANARY_READINESS_AUDIT.md)
and [`docs/PHASE4_CANARY_DEPLOYMENT_GUIDE.md`](docs/PHASE4_CANARY_DEPLOYMENT_GUIDE.md).
