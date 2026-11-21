from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canary_readiness_workflow_fails_closed_without_aws_access():
    workflow = (ROOT / ".github/workflows/canary-readiness.yml").read_text()

    assert "permissions:\n  contents: read" in workflow
    assert "id-token: write" not in workflow
    assert "EKS_PRIVATE_RUNNER_READY" in workflow
    assert "CANARY_TRAFFIC_ROUTER_READY" in workflow
    assert "CANARY_REQUEST_METRICS_READY" in workflow
    assert "This workflow does not request AWS credentials or contact EKS." in workflow
    assert "exit 1" in workflow


def test_unverified_ingress_is_not_part_of_the_deployable_kustomize_base():
    kustomization = (ROOT / "k8s/kustomization.yaml").read_text()
    canary_ingress = (ROOT / "k8s/canary-service.yaml").read_text()

    assert "canary-service.yaml" not in kustomization
    assert 'nginx.ingress.kubernetes.io/canary-weight: "10"' in canary_ingress
    assert "Selected mechanism: none." in (
        ROOT / "docs/PHASE4_CANARY_DEPLOYMENT_GUIDE.md"
    ).read_text()


def test_only_microservices_have_http_health_routes():
    service_apps = (
        "services/station-reservation/app.py",
        "services/billing-wallet/app.py",
        "services/energy-dispatch/app.py",
    )
    for relative_path in service_apps:
        source = (ROOT / relative_path).read_text()
        assert '@app.get("/health")' in source

    gateway = (ROOT / "gateway/app.py").read_text()
    assert '@app.get("/health")' not in gateway


def test_kubernetes_traffic_path_has_no_canary_pair_or_router_resource():
    kustomization = (ROOT / "k8s/kustomization.yaml").read_text()
    resources = [line.strip()[2:] for line in kustomization.splitlines() if line.strip().startswith("- ")]
    assert "canary-service.yaml" not in resources

    for relative_path in (
        "k8s/gateway-deployment.yaml",
        "k8s/gateway-service.yaml",
    ):
        assert "track:" not in (ROOT / relative_path).read_text()

