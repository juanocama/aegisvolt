# Deployment

## Local development (Windows PowerShell)

### Verified status

`docker compose config --quiet` passed on 2026-11-20. The Docker CLI is
installed, but the Docker Desktop Linux engine was unavailable: Docker
commands could not connect to `//./pipe/dockerDesktopLinuxEngine`. Therefore
the Compose stack was **not started** and container readiness is unverified.

The local Compose configuration defines Floci (`4566`), station reservation
(`8001`), billing wallet (`8002`), energy dispatch (`8003`), and the only
GraphQL gateway (`8000`). The frontend is a separate Vite process (`5173`).
Compose has no health checks; `depends_on` does not wait for service
readiness. The gateway's `ENVIRONMENT` defaults to `dev`, and Compose names
its data tables with `dev`.

### Install dependencies

From the project root:

```powershell
Set-Location 'C:\Users\iamju\Desktop\patrones\aegisvolt'
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Set-Location .\frontend
npm ci
Set-Location ..
```

### Configure the local frontend process

The current `.env.example` is stale and the frontend helper ignores
`VITE_GRAPHQL_URL`. For this PowerShell session, configure the local dev
endpoint to use the existing Vite same-origin proxy:

```powershell
$env:VITE_ENVIRONMENT = 'dev'
$env:VITE_GRAPHQL_DEV_URL = '/graphql'
```

Only the dev GraphQL endpoint exists locally. Do not select `test` or `prod`:
Compose has no separate GraphQL gateways for those environments, and the
current frontend's built-in test/prod defaults point to REST service ports.
Those environments are unavailable, not local aliases for dev.

### Start services and check readiness

Ensure Docker Desktop is running with its Linux engine, then from the project
root:

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

The configuration's exact service readiness endpoints are:

```powershell
$healthUrls = @(
  'http://localhost:8001/health',
  'http://localhost:8002/health',
  'http://localhost:8003/health',
  'http://localhost:8000/health'
)
foreach ($url in $healthUrls) {
  $ready = $false
  $lastError = $null
  for ($attempt = 1; $attempt -le 30; $attempt++) {
    try {
      $health = Invoke-RestMethod -Uri $url -TimeoutSec 3 -ErrorAction Stop
      if ($health.status -eq 'ok') {
        Write-Host "Ready: $url"
        $ready = $true
        break
      }
      $lastError = "Unexpected health response: $($health | ConvertTo-Json -Compress)"
    } catch {
      $lastError = $_.Exception.Message
    }
    Start-Sleep -Seconds 2
  }
  if (-not $ready) {
    throw "Not ready after 60 seconds: $url. Last result: $lastError"
  }
}
$flociReady = $false
for ($attempt = 1; $attempt -le 30; $attempt++) {
  if (Test-NetConnection -ComputerName localhost -Port 4566 `
      -InformationLevel Quiet -WarningAction SilentlyContinue) {
    $flociReady = $true
    break
  }
  Start-Sleep -Seconds 2
}
if (-not $flociReady) { throw 'Floci port 4566 was not reachable after 60 seconds.' }
```

Each service health response should report `status: ok`; Floci is checked for
TCP reachability because no Floci health path is established by this
repository's Compose configuration. Verify the GraphQL route without
triggering a business mutation:

```powershell
$body = @{ query = '{ flags { name enabled } }' } | ConvertTo-Json -Compress
Invoke-RestMethod -Uri 'http://localhost:8000/graphql' `
  -Method Post -ContentType 'application/json' -Body $body
```

Start the frontend in a separate PowerShell terminal:

```powershell
Set-Location 'C:\Users\iamju\Desktop\patrones\aegisvolt\frontend'
$env:VITE_ENVIRONMENT = 'dev'
$env:VITE_GRAPHQL_DEV_URL = '/graphql'
npm run dev
```

Open `http://localhost:5173`. The Vite proxy forwards relative `/graphql`
requests to `http://localhost:8000`.

### Run backend tests

From the project root with the virtual environment active:

```powershell
python -m pytest -q
```

### Stop without deleting local service data

Stop containers while retaining them and their writable layers:

```powershell
Set-Location 'C:\Users\iamju\Desktop\patrones\aegisvolt'
docker compose stop
```

Do not use `docker compose down -v` for routine shutdown. The current Compose
file declares no named volume, so emulator data in a container is not a
durable backup.

## Terraform (not validated; do not apply from this baseline)

No Terraform command or apply was run in Phase 0. Backend files contain
`CHANGE_ME` bucket names, while bootstrap creates one supplied bucket; the
configurations need reconciliation and validation before use. The instructions
below are retained from the prior setup note and are **not verified**:

Bootstrap first:

```powershell
cd infra/bootstrap
terraform init
terraform apply -var="state_bucket=your-globally-unique-bucket"
```

The bucket and lock table names must be real and unique. No AWS credentials or resources are fabricated.

```powershell
cd ..
terraform init -backend-config=backend/dev.hcl
terraform workspace new dev
terraform fmt -recursive
terraform validate
terraform plan -var-file=envs/dev.tfvars
terraform apply -var-file=envs/dev.tfvars
```

Do not run `terraform apply` until the backend bucket/lock configuration is
corrected, `fmt`/`validate`/plans have passed, and AWS use is explicitly
approved. The `dev`, `test`, and `prod` tfvars currently contain identical
values and do not by themselves establish environment isolation.

## Kubernetes (not deployed or validated in Phase 0)

`kubectl apply -f k8s/namespace.yaml -f k8s/gateway-deployment.yaml -f k8s/canary-service.yaml`

Run `.\scripts\canary_check.ps1 -Deployment gateway-canary`.
