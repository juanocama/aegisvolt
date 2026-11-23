"""Canary promotion gate and traffic split (spec 3.3b, rubric 6.2)."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("canary_deploy", ROOT / "scripts" / "canary_deploy.py")
canary = importlib.util.module_from_spec(spec)
sys.modules["canary_deploy"] = canary
spec.loader.exec_module(canary)
Obs = canary.CanaryObservation


def test_promotes_healthy_canary_with_enough_traffic():
    ok, reason = canary.evaluate(Obs(requests=100, errors=0, restarts=0, ready=True), 20, 0.01)
    assert ok, reason


@pytest.mark.parametrize(
    "observation, fragment",
    [
        (Obs(requests=100, errors=5, restarts=0, ready=True), "5xx rate"),
        (Obs(requests=5, errors=0, restarts=0, ready=True), "not enough evidence"),
        (Obs(requests=100, errors=0, restarts=1, ready=True), "restarted"),
        (Obs(requests=100, errors=0, restarts=0, ready=False), "not ready"),
    ],
)
def test_rolls_back_on_errors_missing_traffic_restarts_or_unready(observation, fragment):
    ok, reason = canary.evaluate(observation, 20, 0.01)
    assert not ok and fragment in reason


def test_weighted_action_splits_stable_and_canary():
    action = json.loads(canary.weighted_action(20))
    groups = {g["serviceName"]: g["weight"] for g in action["forwardConfig"]["targetGroups"]}
    assert groups == {"gateway": 80, "gateway-canary": 20}
    with pytest.raises(ValueError):
        canary.weighted_action(101)


def test_ingress_routes_graphql_through_weighted_action():
    ingress = (ROOT / "k8s/gateway-ingress.yaml").read_text()
    assert "alb.ingress.kubernetes.io/actions.graphql-weighted" in ingress
    assert "name: use-annotation" in ingress
    canary_manifest = (ROOT / "k8s/gateway-canary.yaml").read_text()
    assert "replicas: 0" in canary_manifest and "track: canary" in canary_manifest
