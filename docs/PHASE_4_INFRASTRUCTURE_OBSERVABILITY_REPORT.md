# Auditoría y avance de Phase 4: infraestructura y observabilidad

**Fecha:** 2026-11-23  
**Rama:** `feature/phase-4-infrastructure-observability`, creada desde el `origin/dev` actualizado.  
**Alcance:** cambios locales y validaciones. No se ejecutaron `terraform plan/apply`, llamadas AWS, operaciones `kubectl`, despliegues, commits, pushes ni PR.

## Estado ejecutivo

La auditoría encontró que el API Gateway era solo un HTTP API regional sin ruta, integración ni endpoint privado; EKS tenía access entries sin modo de autenticación explícito y sin un principal administrador configurado; las cuatro políticas IRSA repetían acciones DynamoDB sin distinguir servicios; los grupos CloudWatch no tenían colector de pods; Prefect solo inspeccionaba un gateway y una tabla; y CI renderizaba Kubernetes sin validar contra esquemas de la versión objetivo.

Se eligió, según las respuestas del propietario, que los clientes GraphQL estén solo en una red privada y que el backend sea un ALB interno reconciliado por AWS Load Balancer Controller. Los campos y pasos que dependen de recursos de AWS aún no existentes permanecen como entradas explícitas.

## Matriz de brechas priorizada

| Requisito | Estado anterior y evidencia | Cambio de esta fase | Prioridad / estado actual |
|---|---|---|---|
| API Gateway privado | `infra/modules/api_gateway` declaraba un HTTP API público/regional sin ruta ni backend. | REST API `PRIVATE`, política limitada a `aws:SourceVpce`, VPC endpoint `execute-api`, ruta POST `/graphql` y VPC Link v2 a ALB. El modo de integración queda desactivado hasta registrar ARN/DNS reales. | P0 — Implementado en Terraform; AWS y destino real pendientes. |
| Ingress GraphQL privado | Gateway solo tenía Service ClusterIP; no había Ingress para AWS LBC. | Ingress `alb` con esquema `internal`, target IP y health check `/health`; gateway expone esa ruta y responde con ID de correlación. | P0 — Manifiestos renderizan; instalación/rol de LBC y ALB real pendientes. |
| Acceso administrativo EKS | Sin `authentication_mode`; `admin_principal_arns` aceptaba lista vacía. | `API_AND_CONFIG_MAP`, versión Kubernetes fijada a `1.37` y variable raíz de ARNs requerida, no vacía y validada como ARN IAM. | P0 — Validado estáticamente; requiere ARN real y validación AWS. |
| IAM de aplicaciones | Cada IRSA permitía un conjunto común que incluía `DeleteItem`, `Scan` y `TransactWriteItems`; apps no enviaban logs directos a CloudWatch. | Las acciones DynamoDB se reducen por servicio según las llamadas observadas. Se eliminan permisos de logs de las aplicaciones. Se mantienen trust conditions OIDC con namespace y service account exactos. | P1 — Implementado; IAM no evaluado por Access Analyzer ni desplegado. |
| Reenvío de logs EKS | Había grupos por servicio pero ningún collector. | Add-ons EKS Pod Identity y CloudWatch Observability declarados; Fluent Bit habilitado para logs de contenedores; grupos `application`, `dataplane`, `host` y control plane con retención Terraform. | P1 — Implementado en IaC; instalación, permisos efectivos, parsing y coste requieren AWS. Rol del add-on usa política administrada `CloudWatchAgentServerPolicy`. |
| Logs y correlación | Los servicios no emitían logs JSON; correlación inicial no se persistía en reserva. | Middleware FastAPI emite JSON de metadatos de petición sin cuerpos ni parámetros; propaga `X-Correlation-ID`; la mutación GraphQL comparte ese ID con SAGA y servicios, y reserva lo persiste. Deshabilitado access log duplicado de Uvicorn en imágenes. | P1 — Código y prueba unitaria local; formato final en CloudWatch pendiente. |
| Auditoría SAGA Prefect | Un endpoint `localhost`, excepción genérica convertida en `False`, una tabla y `scan` sin páginas. | Requiere configuración privada explícita dev/test/prod; comprueba gateway y tres servicios; pagina scans, informa estado, pasos, fallas, compensaciones pendientes, referencias ausentes y registros de servicio huérfanos por correlación; publica métricas por ambiente. | P1 — Lógica y pruebas unitarias; red/IAM Prefect, ejecución y dashboard no configurados. |
| Esquemas Kubernetes CI | Render y aserciones propias, sin validación OpenAPI. | CI valida base y overlays dev/test/prod con Kubeconform v0.8.0 fijado por digest, modo estricto y Kubernetes 1.37.0. | P1 — Paso agregado; imagen/schema remoto no ejecutado en este equipo. |
| Configuración de entornos | Región, state bucket, cuenta, imágenes y roles eran placeholders. | Administrador y ALB ahora son entradas validadas; integración GraphQL solo se habilita al suministrar destino real. | P2 — Valores de cuenta, región, estado, imágenes y runner permanecen requeridos. |
| Rúbrica oficial | El DOCX oficial no está disponible en el repositorio ni en los artefactos inspeccionados. La trazabilidad previa decía 20% observabilidad. | Se documentó por separado la distribución suministrada en Phase 4: 30/25/25/12/8. | P2 — La distribución y el DOCX oficial siguen sin verificarse. |

## Diseño y dependencias

1. API Gateway privado usa REST API porque los private endpoints del cliente se soportan para REST API; la HTTP API v2 existente no satisface ese requisito. El endpoint `execute-api` es independiente del VPC Link: el primero da entrada privada a los clientes y el segundo conecta API Gateway con el ALB privado. Referencias: [private REST APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-private-apis.html), [private integration](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-private-integration.html).
2. La integración ALB usa `aws_api_gateway_integration.integration_target`, disponible desde AWS provider 6.25. El lockfile local quedó actualizado a AWS provider 6.73.0. Se mantiene `enable_graphql_integration = false` inicialmente para permitir crear primero VPC/EKS/API privada sin fingir un ALB. Tras instalar LBC y desplegar Ingress desde un runner conectado a la red privada, se agregan ARN y DNS reales y se habilita la integración en el siguiente cambio Terraform.
3. La API privada todavía no tiene authorizer de usuario; la decisión confirmada limita clientes por red privada/VPC endpoint. No se registraron requisitos de Cognito/JWT en el contrato actual.
4. EKS usa `API_AND_CONFIG_MAP` para activar access entries y conservar el camino de compatibilidad con `aws-auth`. El modo `API` sería una transición de acceso y no se eligió sin evidencia del estado real del clúster. Referencia: [EKS access entries y modo de autenticación](https://docs.aws.amazon.com/eks/latest/userguide/setting-up-access-entries.html).
5. El colector es el add-on administrado por AWS `amazon-cloudwatch-observability`, con CloudWatch Agent + Fluent Bit. Se fijan grupos compatibles con sus defaults y la metadata de Kubernetes/streams distingue workload y pod. Las aplicaciones no reciben permisos CloudWatch. Referencia: [CloudWatch Observability add-on](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/install-CloudWatch-Observability-EKS-addon.html).
6. No se incluye todavía el paquete/rol de AWS Load Balancer Controller ni su instalación Helm: la instalación debe realizarla un runner con conectividad al API privado de EKS y requiere la política upstream correspondiente al release elegido. Sin esos datos no hay ALB que entregar a Terraform. Referencia: [instalación del AWS Load Balancer Controller en EKS](https://docs.aws.amazon.com/eks/latest/userguide/lbc-manifest.html).

## Archivos modificados

- `.github/workflows/ci.yml`
- `common/observability.py`
- `docs/REQUIREMENTS_TRACEABILITY.md`
- `gateway/app.py`, `gateway/Dockerfile`
- `infra/.terraform.lock.hcl`, `infra/main.tf`, `infra/outputs.tf`, `infra/variables.tf`, `infra/versions.tf`
- `infra/modules/api_gateway/main.tf`
- `infra/modules/eks_ecr/main.tf`
- `infra/modules/network/main.tf`
- `infra/modules/observability/main.tf`
- `k8s/gateway-ingress.yaml`, `k8s/kustomization.yaml`
- `observability/prefect/audit_flow.py`
- Dockerfiles de `services/station-reservation`, `services/billing-wallet`, `services/energy-dispatch` y sus apps FastAPI
- `tests/test_phase4_observability.py`
- `project-management/CURRENT_TASK.md`, `project-management/IMPLEMENTATION_STATUS.md`

## Valores que siguen siendo necesarios

- Región y cuenta AWS reales; bucket S3 backend configurado y acceso a su estado existente.
- Un ARN IAM real para administración EKS por ambiente, entregado en tfvars seguro local/CI; nunca en el repositorio.
- Repositorios ECR y referencias de imagen SHA válidas para los manifiestos, sin `CHANGE_ME`.
- Instalación del AWS Load Balancer Controller en el clúster, despliegue de Ingress y sus salidas reales `gateway_alb_arn` / `gateway_alb_dns_name`; solo entonces `enable_graphql_integration=true`.
- Conectividad privada del runner que aplica Terraform a la API privada de EKS para operar Helm/kubectl cuando se instale LBC.
- `AEGISVOLT_AUDIT_ENVIRONMENTS_JSON` con URLs privadas reales del gateway y servicios, y acceso IAM del Prefect runner de solo lectura a las cuatro tablas por ambiente más `cloudwatch:PutMetricData` para `AegisVolt/SAGA`.
- Confirmar rúbrica oficial y sus ponderaciones.

## Uso operativo previsto

Después de habilitar el add-on y crear logs en AWS, CloudWatch Logs Insights puede correlacionar la petición de la respuesta GraphQL con los cuatro servicios. El nombre del grupo incorpora el clúster/ambiente y Fluent Bit añade metadata de pod/contenedor al stream:

```text
fields @timestamp, service, correlation_id, method, path, status_code, duration_ms
| filter correlation_id = "<correlation_id de la respuesta GraphQL>"
| sort @timestamp asc
```

Prefect devuelve para cada SAGA el `saga_id`, `correlation_id`, estado, pasos completados/fallidos, intentos y resultados de compensación e inconsistencias candidatas. La retención declarada es configurable con `cloudwatch_log_retention_days` (14 días por defecto); la tabla DynamoDB conserva la fuente de verdad de eventos SAGA.

## Validación

| Comando / comprobación | Resultado exacto |
|---|---|
| `terraform fmt -check -recursive` (`infra/`) | Pasó, exit 0. |
| `terraform init -backend=false -input=false -reconfigure` (`infra/`) | Pasó, exit 0; proveedores locales AWS 6.73.0 y TLS 4.4.2. No se inicializó S3. |
| `terraform validate -no-color` (`infra/`) | Pasó: `Success! The configuration is valid.`, exit 0. No plan. |
| `python -m compileall -q common gateway services tests observability/prefect` | Pasó, exit 0. |
| `python -m pytest -q tests/test_services.py tests/test_phase4_observability.py` | **9 passed, 68 warnings**, exit 0. Incluye persistencia del correlation ID de reserva. Las advertencias son deprecaciones/configuración existentes de pytest-asyncio, Botocore y FastAPI. |
| `python -m pytest -q -o faulthandler_timeout=10` | No terminó; se interrumpió al detectar el bloqueo Windows Proactor/socket-pair en `tests/test_compensation.py::test_retry_compensation_rejects_non_failed_saga`. La traza fue capturada a los 10 s; no se modificó ni debilitó esa prueba. |
| `kubectl kustomize k8s` y overlays dev/test/prod con `LoadRestrictionsNone` | Pasaron, exit 0. YAML parseado: raíz 15 recursos; cada overlay 14. |
| Parseo local de `.github/workflows/ci.yml` con PyYAML | Pasó; también se confirmó Ingress interno y backend `gateway` en el render raíz. |
| Kubeconform | Paso agregado a CI, pero no se ejecutó localmente: `kubeconform` no está instalado y Docker Engine devuelve acceso denegado al pipe de Docker Desktop. |
| `git diff --check` | Pasó, exit 0; Git mostró solo advertencias de conversión CRLF para algunos archivos LF. |

No se afirmó despliegue, AWS plan ni validación contra un API Server. 

## AWS y Git

No se inicializó backend S3, no se ejecutó plan/apply, no se consultó ni modificó AWS, no se desplegó Kubernetes, no se crearon recursos facturables y no se accedió a credenciales. La rama de trabajo está basada en el `origin/dev` actualizado; no hay commit, push o PR.
