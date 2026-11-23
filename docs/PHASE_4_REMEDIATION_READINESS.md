# AegisVolt Phase 4 — remediación dirigida y readiness

Fecha: 2026-11-23. Esta nota complementa `PHASE_4_INFRASTRUCTURE_OBSERVABILITY_REPORT.md`.

## Logging y correlación

- `X-Correlation-ID` acepta de 1 a 128 caracteres ASCII que cumplan `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`. Si falta o no cumple, el middleware genera un UUID nuevo; el valor saneado sigue en el contexto, la respuesta y la propagación servicio a servicio.
- El log registra la plantilla de ruta FastAPI, nunca la ruta URL cruda; si la ruta no está resuelta usa `<unmatched>`. No incluye cuerpos, query strings, tokens ni valores de negocio.
- Se añadieron pruebas para IDs válidos, malformados, sobredimensionados y ocultación de identificadores dinámicos; la de privacidad también comprueba que query strings, Authorization y cuerpo no llegan al log.

## Prefect: semántica SAGA, escala y coste

Los estados terminales se derivan de `gateway/app.py`: `COMPLETED`, `COMPENSATED`, `FAILED` y `STOPPED`. `FAILED` y `COMPENSATION_FAILED` se marcan inmediatamente como fallos; `pending_compensations` también se conserva como señal accionable. Los estados activos recientes ya no se clasifican automáticamente como inconsistentes. Un estado no terminal es stale si `updated_at` supera `SAGA_STALE_AFTER_SECONDS` (por defecto 300 segundos) y no hay lease vigente. Timestamp ausente/malformado se informa explícitamente. Umbral inválido o <= 0 falla cerrado.

`compensation_attempts` cuenta solo eventos `compensation/started`; `compensation_retries` cuenta `compensation_retry/started`. Eventos de refund y liberación no inflan intentos.

La ejecución habitual pagina la tabla SAGA y usa `BatchGetItem` por referencias existentes para validar filas en las tablas de servicio; no escanea tres tablas de servicio en cada corrida. El scan exhaustivo de huérfanos es opcional mediante `SAGA_FULL_ORPHAN_SCAN_ENABLED=true` y queda deshabilitado por defecto. Su estado aparece como `orphan_audit_complete=false`/`OrphanAuditComplete=0`, nunca como cero huérfanos; `OrphanServiceRecords` y `records_without_correlation_id` quedan sin publicar si el scan no se ejecutó. El scan sigue paginado cuando se habilita.

El esquema solo tiene clave hash `id`: no existe un índice por estado/fecha ni por `correlation_id`. Por eso, el inventario de SAGA aún lee todos los items de una tabla por ambiente (tres tablas por ejecución de dev/test/prod), aunque ya no recorra en cada corrida todas las tablas de servicios. RCU depende del tamaño de los items/consistencia; paginar acota memoria, pero no el RCU total. Para stale SAGA incremental se requiere diseñar un GSI/cursor durable; detectar huérfanos exige estrategia incremental adicional. Ningún índice ni tabla de cursores fue inventado o añadido.

## Matriz de endpoints y egress

Valores para la región aportada `us-east-1`. Un endpoint Interface requiere DNS privado y permitir TCP/443 desde workloads hacia su SG. El SG actual acepta TCP/443 desde todo el CIDR VPC; la salida es amplia. DNS de VPC está habilitado.

| Servicio y nombre | Tipo / DNS | Consumidor | Presente | NAT/egress si falta | Coste/nota |
|---|---|---|---|---|---|
| EC2 — `com.amazonaws.us-east-1.ec2` | Interface / sí | AMI EKS, descubrimiento de región/VPC y operaciones EC2 del LBC | Sí | Endpoint o salida | Cargo por AZ-hora y datos. |
| ELB — `com.amazonaws.us-east-1.elasticloadbalancing` | Interface / sí | Crear y reconciliar ALB/target groups del LBC | **No** | Endpoint o egress requerido | Falta crítica para ALB sin NAT. [AWS PrivateLink ELB](https://docs.aws.amazon.com/elasticloadbalancing/latest/userguide/load-balancer-vpc-endpoints.html). |
| STS — `com.amazonaws.us-east-1.sts` | Interface / sí | IRSA y llamadas de workload | Sí | Endpoint o salida | Cargo por AZ-hora/datos. |
| ECR API — `com.amazonaws.us-east-1.ecr.api` | Interface / sí | Token/metadata de imagen | Sí | Endpoint o salida | Cargo por AZ-hora/datos. |
| ECR Docker — `com.amazonaws.us-east-1.ecr.dkr` | Interface / sí | Registry OCI y pulls | Sí | Endpoint o salida | Cargo por AZ-hora/datos. |
| S3 — `com.amazonaws.us-east-1.s3` | Gateway / no aplica | Capas de imagen ECR y objetos S3 usados por workloads | Sí | No requiere NAT para S3 | Sin cargo horario de endpoint; tarifas normales de S3. |
| CloudWatch Logs — `com.amazonaws.us-east-1.logs` | Interface / sí | Fluent Bit y CloudWatch Observability | Sí | Endpoint o salida | Cargo por AZ-hora/datos. |
| CloudWatch Monitoring — `com.amazonaws.us-east-1.monitoring` | Interface / sí | `PutMetricData` de Prefect y métricas CloudWatch | **No** | Endpoint o salida | Falta si Prefect está en subnets aisladas. |
| EKS Auth — `com.amazonaws.us-east-1.eks-auth` | Interface / sí | Pod Identity Agent | Sí | Endpoint o salida | Cargo por AZ-hora/datos. |
| EKS Management — `com.amazonaws.us-east-1.eks` | Interface / sí | Runner privado que ejecuta APIs AWS EKS | **No** | Solo si ese cliente está en red aislada | No sustituye el endpoint Kubernetes privado. Cargo por AZ-hora/datos. |
| EKS Kubernetes API | Endpoint privado administrado por EKS | `kubectl`/Helm y nodos | Clúster declarado privado | Requiere runner en VPC/VPN/peering/Direct Connect | No es VPC Interface Endpoint. |
| API Gateway execute-api — `com.amazonaws.us-east-1.execute-api` | Interface / sí | Clientes GraphQL privados | Sí | Parte requerida del diseño | Independiente del VPC Link. |
| OIDC EKS — `com.amazonaws.us-east-1.oidc-eks` | Interface si se consulta desde VPC | Bootstrap IRSA desde runner dentro de VPC | No | Solo bootstrap si necesita endpoint issuer | No es endpoint runtime para credenciales IRSA. |
| DynamoDB — `com.amazonaws.us-east-1.dynamodb` | Gateway / no aplica | Servicios y Prefect | Sí | No requiere NAT para DynamoDB | Sin cargo horario de endpoint; tarifas de DynamoDB aplican. |

No se añadieron endpoints. La arquitectura de endpoints privados evita egress general y permite aislar el runtime, pero suma cargos horarios por endpoint/AZ y cargos por transferencia. NAT simplifica acceso a APIs públicas/AWS faltantes y descarga de artefactos externos, pero agrega precio horario, procesamiento de datos y una ruta egress más amplia; NAT único reduce costo fijo pero introduce dependencia cross-AZ y punto de falla. Se mantienen execute-api y Gateway endpoints privados aun en alternativa NAT. No se calculó importe exacto: depende de número de AZ/endpoint y volumen, y requiere revisar precios vigentes de us-east-1.

Recomendación provisional: endpoints privados para el runtime, agregando ELB y Monitoring tras aprobación de costo, más `eks`/OIDC solo si la ubicación y tareas del runner lo requieren. Para Helm/imágenes externas, usar mirror privado o egress de runner aprobado. Alternativamente, evaluar NAT por AZ con costo revisado. **No se eligió ni implementó NAT o endpoint nuevo.** [AWS: requisitos de clúster privado](https://docs.aws.amazon.com/eks/latest/userguide/private-clusters.html).

## AWS Load Balancer Controller

- Versión upstream objetivo del plan: `v3.6.3`; compatible con Kubernetes 1.22+ según referencia del controlador. No se instaló. Política oficial exacta: [iam_policy.json v3.6.3](https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v3.6.3/docs/install/iam_policy.json).
- La política exige recursos `*` para varias acciones Describe y reglas/listeners; acciones de creación incluyen condiciones por tag `elbv2.k8s.aws/cluster`, y recursos modificables se acotan por el tag cuando soportado. Debe revisarse cada statement para la ruta Ingress-only y conservar las condiciones upstream requeridas.
- Usar un rol dedicado al controlador y Pod Identity con el agente ya declarado, namespace `kube-system`, ServiceAccount `aws-load-balancer-controller`; no reutilizar el rol administrador ni los roles IRSA de aplicaciones. Helm reproducible: repositorio `https://aws.github.io/eks-charts`, chart `aws-load-balancer-controller --version 3.6.3`, con imagen/tag de controlador v3.6.3; fijar chart y valores en IaC/lock antes de instalar. Pasar `clusterName`, `region=us-east-1` y `vpcId` explícitos para no depender de IMDS. En clúster aislado desactivar flags Shield/WAF/WAFv2 conforme a la guía LBC.
- Runner de instalación debe resolver y alcanzar la API Kubernetes privada. La Ingress ya pide ALB interno, targets IP, HTTP 80, `/graphql`, health `/health`; los tags de subred privada están declarados.
- Antes de crear: conectar la SG de VPC Link como origen permitido en la SG frontend del ALB. La SG del VPC Link no se publica como output y la Ingress no fija la SG, así que esa unión permanece pendiente. Verificar Service/health path en el cluster.
- Después de reconciliar: leer `status.loadBalancer.ingress[].hostname`, describir ALB para confirmar ARN real, `Scheme=internal`, subnets y targets sanos; verificar DNS/ruta desde VPC/VPN. Solo entonces habilitar REST API GraphQL con los valores reales.

## EKS administrator ARN y add-ons

La salida compartida de STS indica cuenta `065656773005` y sesión `AWSReservedSSO_AdministratorAccess_a0fe7335cef42aa4`. Contradice la descripción de permiso `AegisVolt-Terraform-Admin`: no se debe afirmar que esa permission set haya sido la usada. Con Identity Center en `us-east-1`, la forma IAM esperada derivada de la sesión es `arn:aws:iam::065656773005:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_AdministratorAccess_a0fe7335cef42aa4`; confirmar el ARN real antes de tfvars. El ARN STS `assumed-role/.../aegisvolt-admin` no es válido como principal de access entry. [AWS: formato y estabilidad de roles Identity Center](https://docs.aws.amazon.com/singlesignon/latest/userguide/referencingpermissionsets.html).

No se consultó IAM. Para revisión read-only posterior, obtener el rol real mediante IAM Console/`GetRole` o `list-roles` filtrado por el nombre exacto. Una sola identidad facilita la operación cross-environment pero aumenta radio de impacto; separar permiso/rol de prod (idealmente cuenta aparte) mejora aislamiento. En ambos casos, el controlador usa su rol técnico separado.

No se ejecutó `DescribeAddonVersions`. Para `coredns`, `kube-proxy`, `vpc-cni`, `eks-pod-identity-agent` y `amazon-cloudwatch-observability`, consultar en la cuenta/región con `aws eks describe-addon-versions --kubernetes-version 1.37 --region us-east-1`, elegir una versión compatible aprobada, y fijarla explícitamente en `addon_version` para cada `aws_eks_addon`. No se inventaron versiones.

## Kubeconform y frontend privado

El workflow conserva `kubectl kustomize k8s`, los overlays dev/test/prod, Kubernetes 1.37.0 y modo estricto; añade la ubicación de esquema `yannh/kubernetes-json-schema` fijada a `v1.37.0-standalone-strict`, y la imagen Kubeconform sigue fijada por digest. Esta referencia versionada quita `master` mutable. Falta ejecutar CI: Docker Desktop local no está disponible.

La SPA puede ser accedida por navegadores si se aloja en una ubicación privada y el usuario llega por VPN o conectividad equivalente; DNS privado debe resolver `execute-api` en ese camino. No hay hosting privado frontend ni DNS de navegador declarados. El frontend actual solo tiene proxy Vite local. No existe configuración CORS en FastAPI/API Gateway; si app y API usan orígenes distintos, definir CORS/preflight antes de despliegue. No se implementó alternativa pública.

## Validación y límites de esta remediación

- `python -m compileall -q common gateway services tests observability/prefect`: pasó.
- Pytest focalizado Windows: bloqueado antes/durante las pruebas async por creación de loop Proactor/socket pair (`socket.accept` en `_fallback_socketpair`); no se alteraron pruebas existentes. Falta intento Linux/WSL.
- No se ejecutó AWS CLI, plan/apply, despliegue, Helm, kubectl apply ni cambios de infraestructura.
- El cierre de validación y del PR queda sujeto a terminar las pruebas, parseo CI, Kustomize, Terraform local y `git diff --check`.

## Actualización 2026-11-23 — ejecución Stage A/B y discovery AWS

**Correcciones de código (validadas localmente):**
- `_load_referenced_service_records` enviaba claves tipadas (`{"id": {"S": ...}}`) y re-deserializaba ítems a través del cliente del *resource* boto3, que ya (de)serializa. Contra DynamoDB real fallaba con `TypeError: unhashable type: 'dict'`; el mock de la prueba lo ocultaba. Ahora usa valores planos. Nueva prueba Moto con 150 referencias (>100 claves por BatchGetItem) y registro faltante.
- `ACTIVATION_UNCERTAIN` (estado real de `gateway/app.py`) faltaba en `ACTIVE_STATES`; un SAGA reciente en ese estado se marcaba como inconsistente. Prueba añadida.
- Prueba Moto de paginación real de `Scan` (>1 MB, varias páginas).
- `test_phase4_canary_readiness` afirmaba que el gateway no tenía `/health`; Phase 4 lo requiere para el health check del ALB interno. La prueba ahora verifica `/health` en gateway y servicios, `healthcheck-path: /health` y `scheme: internal` en la Ingress.
- `python -m pytest -q`: **36 passed** en Windows (el bloqueo Proactor no se reprodujo).

**Discovery AWS read-only (cuenta 065656773005, us-east-1):** sin VPC, EKS, DynamoDB, ECR, endpoints, NAT ni log groups de AegisVolt; tampoco bucket de estado. Rol admin real verificado: `arn:aws:iam::065656773005:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_AdministratorAccess_a0fe7335cef42aa4` (fijado en `envs/dev.tfvars`). Kubernetes 1.37 en `STANDARD_SUPPORT`.

**Add-ons fijados** (versión *default* reportada por `aws eks describe-addon-versions --kubernetes-version 1.37`): coredns `v1.14.7-eksbuild.35`, kube-proxy `v1.37.0-eksbuild.39`, vpc-cni `v1.22.4-eksbuild.14`, eks-pod-identity-agent `v1.4.1-eksbuild.3`, amazon-cloudwatch-observability `v8.0.1-eksbuild.1`.

**Terraform:** endpoints `elasticloadbalancing` y `monitoring` añadidos. Backends dev/test/prod usan bucket `aegisvolt-tfstate-065656773005-us-east-1` y una única key, de modo que el workspace produce `env:/<env>/aegisvolt/terraform.tfstate`. `fmt`/`validate` pasan. `terraform plan` dev (copia con backend local, solo lecturas AWS): solo creaciones (VPC, 4 subnets, 11 VPC endpoints, EKS + 1 nodo t3.medium, 5 add-ons, 4 tablas DynamoDB, 5 ECR, 4 log groups, REST API privada, IAM); sin reemplazos/borrados, sin NAT.

**Pendiente de aprobación del propietario:** creación del bucket de estado (bloqueada por el control de permisos de la sesión) y `apply` de dev por su costo recurrente estimado (~USD 235/mes; detalle en el reporte de sesión). No se creó ningún recurso AWS.
