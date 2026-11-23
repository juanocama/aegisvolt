"""Deployment pipeline and canary wiring (spec 3.3, rubric 6.2)."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _workflow(name: str) -> dict:
    return yaml.safe_load((ROOT / ".github/workflows" / name).read_text())


def test_pr_pipeline_has_required_gates():
    ci = _workflow("ci.yml")
    triggers = ci.get("on") or ci.get(True)
    assert triggers["pull_request"]["branches"] == ["dev", "test", "prod"]
    for job in ("promotion-guard", "lint-build", "unit-tests", "integration-tests", "e2e-tests", "terraform-plan", "kubernetes"):
        assert job in ci["jobs"], job
    plan = ci["jobs"]["terraform-plan"]
    script = "\n".join(step.get("run", "") for step in plan["steps"])
    assert plan["env"]["TARGET_ENVIRONMENT"] == "${{ github.base_ref }}"
    assert 'terraform workspace select "${TARGET_ENVIRONMENT}"' in script
    assert "terraform plan" in script and "-lock=false" in script


def test_promotion_guard_enforces_linear_flow():
    guard = _workflow("ci.yml")["jobs"]["promotion-guard"]["steps"][0]["run"]
    assert 'test) [[ "$HEAD" == "dev" ]]' in guard
    assert 'prod) [[ "$HEAD" == "test" ]]' in guard
    assert "^(feature|fix|hotfix|chore|docs)/" in guard


def test_post_merge_deploy_targets_only_the_merged_branch_workspace():
    deploy = _workflow("deploy.yml")
    triggers = deploy.get("on") or deploy.get(True)
    assert triggers["push"]["branches"] == ["dev", "test", "prod"]
    job = deploy["jobs"]["deploy"]
    assert job["env"]["TARGET_ENVIRONMENT"] == "${{ github.ref_name }}"
    assert job["environment"]["name"] == "${{ github.ref_name }}"
    script = "\n".join(step.get("run", "") for step in job["steps"])
    assert 'terraform workspace select "${TARGET_ENVIRONMENT}"' in script
    assert "terraform apply -input=false -auto-approve" in script
    assert "scripts/canary_deploy.py" in script and "--weight 20" in script


def test_canary_pair_and_weighted_router_are_part_of_every_overlay():
    for kustomization in ("k8s/kustomization.yaml", *(f"k8s/overlays/{e}/kustomization.yaml" for e in ("dev", "test", "prod"))):
        text = (ROOT / kustomization).read_text()
        assert "gateway-canary.yaml" in text and "gateway-ingress.yaml" in text, kustomization
    assert not (ROOT / "k8s/canary-service.yaml").exists()


def test_services_and_gateway_expose_health_used_by_internal_alb():
    for relative_path in (
        "services/station-reservation/app.py",
        "services/billing-wallet/app.py",
        "services/energy-dispatch/app.py",
        "gateway/app.py",
    ):
        assert '@app.get("/health")' in (ROOT / relative_path).read_text()
    ingress = (ROOT / "k8s/gateway-ingress.yaml").read_text()
    assert "alb.ingress.kubernetes.io/healthcheck-path: /health" in ingress
    assert "alb.ingress.kubernetes.io/scheme: internal" in ingress
