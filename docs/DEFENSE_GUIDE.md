# Guía de sustentación — AegisVolt

Respuestas y demostraciones para el banco de preguntas (sección 6 del
enunciado). Cada respuesta cita el archivo exacto. Las demos locales usan
`docker compose`; las de AWS usan el perfil `aegisvolt` (región `us-east-1`).

## Preparación de la demo local (≈3 min)

```powershell
docker compose up -d --build                      # Floci, 3 servicios, gateway, frontend
docker compose --profile observability up -d prefect   # Prefect UI en http://localhost:4201
# Frontend: http://localhost:8088   GraphQL: http://localhost:8010/graphql
$env:AWS_ENDPOINT_URL="http://localhost:4566"; $env:AWS_ACCESS_KEY_ID="test"; $env:AWS_SECRET_ACCESS_KEY="test"
python scripts/set_feature_flag.py --env dev --list
```

---

## 6.1 IaC, S3 y redes (30 %)

**¿Cómo evita que un apply en `test` sobrescriba tablas o estado de `prod`?**
- Cada ambiente es un workspace distinto. El backend S3 guarda el estado en
  `env:/<workspace>/aegisvolt/terraform.tfstate` (`infra/backend/*.hcl`), así
  que `test` y `prod` tienen archivos de estado separados.
- `terraform_data.workspace_guard` (`infra/main.tf`) aborta si el workspace no
  es `dev|test|prod`.
- Todos los nombres usan `terraform.workspace`: `local.prefix =
  "${terraform.workspace}-aegisvolt"`, tablas `aegisvolt-${terraform.workspace}-*`.
  Un apply en `test` solo puede tocar recursos `test-*`/`aegisvolt-test-*`.
- En CI, `deploy.yml` toma el workspace de la rama que recibió el merge
  (`github.ref_name`) y el rol OIDC solo lo puede asumir el GitHub Environment
  de ese ambiente.

**Mostrar versiones anteriores del tfstate de dev y restaurar una.**
```powershell
aws s3api list-object-versions --bucket aegisvolt-tfstate-065656773005-us-east-1 --prefix "env:/dev/" --query "Versions[].[VersionId,LastModified,Size,IsLatest]" --output table --profile aegisvolt
# Restaurar: copiar la versión buena encima de la actual (crea una nueva versión, no borra historia)
aws s3api copy-object --bucket aegisvolt-tfstate-065656773005-us-east-1 --key "env:/dev/aegisvolt/terraform.tfstate" --copy-source "aegisvolt-tfstate-065656773005-us-east-1/env:/dev/aegisvolt/terraform.tfstate?versionId=<VERSION>" --profile aegisvolt
terraform -chdir=infra workspace select dev; terraform -chdir=infra plan -var-file=envs/dev.tfvars   # verificar
```
- El bucket tiene versionado, cifrado SSE-S3 y bloqueo de acceso público.
  Hay 38 versiones reales del estado de dev, del despliegue del 2026-11-23.
- El bloqueo de concurrencia usa `use_lockfile = true` (archivo `.tflock` en S3).

**Recorrido de un paquete API Gateway → pod.**
1. El navegador (dentro de la VPC: VPN o túnel de Session Manager) entra al ALB
   interno del frontend (`k8s/frontend.yaml`, `inbound-cidrs 10.0.0.0/16`).
2. nginx reenvía `/graphql` a `https://<api-id>.execute-api.us-east-1.amazonaws.com/<env>/graphql`.
   El DNS privado del **VPC Endpoint `execute-api`** resuelve ese nombre a IPs
   privadas de la VPC (`infra/modules/network`, `private_dns_enabled`). El
   security group del endpoint solo admite 443 desde el CIDR de la VPC.
3. La API REST es **PRIVATE**. Su resource policy (`aws_api_gateway_rest_api_policy`)
   solo permite `execute-api:Invoke` si `aws:SourceVpce` es ese endpoint.
4. La integración `HTTP_PROXY` con `connection_type = VPC_LINK` usa el **VPC Link v2**
   (ENIs en las subredes privadas, SG `apigw-vpclink`) hacia el **ALB interno**
   de GraphQL que crea el AWS Load Balancer Controller.
5. El ALB usa target-type `ip`: envía directo a la IP del pod del gateway (VPC CNI).
   La regla de forward pondera los target groups stable/canary.
6. El gateway llama por DNS de Kubernetes (ClusterIP) a los tres servicios. Estos
   llegan a DynamoDB por el **Gateway Endpoint de DynamoDB**, que aparece en las
   **tablas de ruteo privadas** (`aws_vpc_endpoint.dynamodb`, `route_table_ids`).
   No hay NAT ni salida a internet. ECR, STS, logs y monitoring usan endpoints
   de interfaz.

---

## 6.2 CI/CD, promoción y canary (25 %)

**`git push --force` o push directo a `test`.**
```powershell
git checkout test; git commit --allow-empty -m "intento directo"; git push origin test
git push --force origin test
```
GitHub rechaza ambos con `GH006: Protected branch update failed`. Las reglas
de protección de `test` exigen PR con checks verdes y bloquean el force push.
Además, en un PR, el job `promotion-guard` rechaza cualquier origen distinto
de `dev` hacia `test`.

**¿Cómo decide el YAML sobre qué ambiente correr `terraform apply`?**
`.github/workflows/deploy.yml`: se dispara con `on.push.branches [dev,test,prod]`
(es decir, después del merge). Usa `TARGET_ENVIRONMENT: ${{ github.ref_name }}`
y `environment.name: ${{ github.ref_name }}`. Después ejecuta
`terraform workspace select "${TARGET_ENVIRONMENT}"` y `terraform apply
-auto-approve -var-file="envs/${TARGET_ENVIRONMENT}.tfvars"`. En el PR,
`terraform-plan` usa `github.base_ref` (la rama destino).

**¿Qué métrica evalúa el canary antes de pasar de 20 % a 100 %?**
`scripts/canary_deploy.py` hace lo siguiente:
1. Despliega `gateway-canary` y espera a que esté ready.
2. Pondera el ALB 80/20 con la anotación `actions.graphql-weighted`.
3. Observa durante 5 minutos.
4. Lee de CloudWatch (namespace `AegisVolt/<env>`) `Requests-gateway-canary` y
   `Http5xx-gateway-canary`. Los generan filtros de métricas sobre
   `/aegisvolt/<env>/gateway-canary`, que cuentan `status_code >= 500`.
5. Promueve solo si hubo **≥ 20 requests**, la **tasa de 5xx es ≤ 1 %**, hubo
   **0 reinicios** y el pod está **ready**. Si no, hace **rollback automático**:
   peso 0, canary a 0 réplicas y el job falla.

La función `evaluate()` tiene tests unitarios en `tests/test_canary_gate.py`.

---

## 6.3 SAGA y feature flags (25 %)

**Activar la flag de fallo en `test`, disparar la mutación y mostrar la compensación en DynamoDB.**
```powershell
python scripts/set_feature_flag.py --env test --flag SIMULATE_CHARGER_HARDWARE_FAULT --enabled true
# en GraphQL de test (o la UI): reserveAndActivateCharge(...) -> state COMPENSATED
aws dynamodb get-item --table-name aegisvolt-test-sagas --key '{"id":{"S":"<sagaId>"}}'      # events: reservation ok, charge ok, activation failed, compensation refund ok, release ok
aws dynamodb get-item --table-name aegisvolt-test-wallets --key '{"id":{"S":"refund-charge-<key>"}}'   # evento de reversión
aws dynamodb get-item --table-name aegisvolt-test-stations --key '{"id":{"S":"reservation-<key>"}}'    # status cancelled; conector AVAILABLE
```
En local, lo mismo con `--env dev` y `AWS_ENDPOINT_URL=http://localhost:4566`.
El test E2E `test_runtime_fault_flag_triggers_refund_then_release_without_redeploy`
lo automatiza.

Orden de la compensación (`gateway/app.py`, orquestación):
1. Si falla la activación, primero el **reembolso** en billing, que es atómico:
   `TransactWriteItems` suma el saldo, marca el cobro `refunded` y crea el
   registro `refund-*`.
2. Luego la **liberación** de la reserva en station.
3. Si falla el paso 2 (fondos insuficientes, HTTP 402), solo se libera la reserva.

**¿Cómo evita problemas si una compensación se procesa dos veces?**
- **Claves de idempotencia deterministas:**
  - `charge-<key>`, `refund-charge-<key>` y `reservation-<key>`.
  - El registro de reembolso se crea con `attribute_not_exists(id)` dentro de la
    misma transacción que suma el saldo y exige `status = charged`. Un segundo
    reembolso no puede volver a sumar dinero.
  - Un replay devuelve el resultado ya guardado (estado leído de nuevo, nunca
    una copia vieja).
- **SAGA condicional:**
  - El SAGA se crea con una huella (fingerprint) del payload.
  - La misma clave con otro payload da error GraphQL.
  - Un lease de 120 s serializa los workers.
- **Compensaciones protegidas por estado:**
  - `pending_compensations` guarda las compensaciones pendientes y
    `retryCompensation` solo re-ejecuta las que faltan.
  - `cancel` de una reserva ya cancelada es un no-op.
- Tests:
  - `tests/test_services.py::test_charge_replay_and_refund_replay_are_atomic`
    (2 reembolsos concurrentes = 1 solo abono).
  - `tests/test_saga.py::test_duplicate_idempotency_request_does_not_repeat_effects`.

**Aislamiento de flags por ambiente.**
- Cada ambiente tiene su tabla `aegisvolt-<env>-flags` (Terraform,
  `infra/modules/dynamodb`). El gateway lee la suya (`FLAGS_TABLE`).
- `common/feature_flags.py` rechaza una tabla de otro ambiente.
- Valores iniciales según el ejemplo del enunciado: surge `true` en dev/test y
  `false` en prod. Terraform ignora los cambios en caliente (`ignore_changes`).

---

## 6.4 Observabilidad y frontend (20 %)

**Prefect + rastrear en CloudWatch el `correlation_id` de una SAGA fallida.**
- Prefect: `observability/prefect/audit_flow.py`.
  1. Health de dev/test/prod.
  2. Auditoría de SAGAs: compensadas, fallidas, estancadas, inconsistentes y
     huérfanas. Una SAGA compensada que no devolvió el dinero o no liberó el
     conector se marca inconsistente.
  3. Artefactos en el dashboard de Prefect: `aegisvolt-environment-health`,
     `aegisvolt-saga-audit` y `aegisvolt-audit-summary`.
  4. Métricas `AegisVolt/SAGA` en CloudWatch.
  ```powershell
  $env:PREFECT_API_URL="http://localhost:4201/api"; $env:AEGISVOLT_AUDIT_ENVIRONMENTS_JSON=(Get-Content audit.json -Raw)
  python -c "import sys; sys.path.insert(0,'observability/prefect'); from audit_flow import audit; audit()"
  ```
- CloudWatch:
  - Logs JSON (`common/observability.py`) con `environment`, `service` y
    `correlation_id` (propagado por el gateway en `X-Correlation-ID`).
  - Fluent Bit los envía a `/aegisvolt/<env>/<servicio>`.
  - Consulta en Logs Insights (también está en el dashboard `<env>-aegisvolt-overview`):
  ```
  SOURCE '/aegisvolt/dev/gateway' '/aegisvolt/dev/billing-wallet' '/aegisvolt/dev/station-reservation' '/aegisvolt/dev/energy-dispatch'
  | filter log_processed.correlation_id = '<correlationId de la SAGA>'
  | fields @timestamp, @log, log_processed.service, log_processed.path, log_processed.status_code
  ```
  - Evidencia real del 2026-11-23: el correlation id `f8b0ed47-…` se encontró en
    los logs de los servicios en CloudWatch (`docs/PHASE_4_DEV_DEPLOYMENT_EVIDENCE.md`).

**Cambiar una flag en dev sin redesplegar; prod intacto.**
```powershell
python scripts/set_feature_flag.py --env dev --flag SIMULATE_CHARGER_HARDWARE_FAULT --enabled true
python scripts/set_feature_flag.py --env prod --list      # sigue en false
```
- El gateway relee la tabla cada `FLAG_CACHE_SECONDS` (5 s) y el frontend
  consulta cada 4 s.
- En la página **Feature flags** cambia el estado. En **Stations** aparece el
  aviso de fallo y una nueva carga termina en `COMPENSATED`. prod no cambia
  porque lee `aegisvolt-prod-flags`.

---

## Límites conocidos (decirlos con honestidad si preguntan)

- **Despliegue AWS:**
  - Se desplegó y probó **dev** en AWS real y luego se destruyó, por costo.
  - test y prod están declarados (workspaces, tfvars, overlays) pero no aprovisionados.
  - Los pipelines de plan/deploy en GitHub requieren el bootstrap OIDC
    (`docs/CICD_PIPELINE.md`).
- **Acceso:** no hay VPN. El acceso privado es por túnel de Session Manager:
  sin IP pública ni puertos de entrada.
- **Flags sin comportamiento:** surge pricing y fast-charge boost se muestran
  por ambiente, pero sus reglas de negocio no están implementadas.
- **Tiempo real:** es polling cada 4 s, no WebSocket.
