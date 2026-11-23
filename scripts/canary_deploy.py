"""Canary rollout of the GraphQL gateway with automatic promote/rollback.

Flow (spec 3.3 post-merge, rubric 6.2):
  1. Deploy the new image to `gateway-canary` (1 replica) and wait for readiness.
  2. Shift WEIGHT% of ALB traffic to the canary target group (default 20%).
  3. Observe for WINDOW seconds: CloudWatch metrics from the per-environment
     log metric filters (`Requests-gateway-canary`, `Http5xx-gateway-canary`
     in namespace AegisVolt/<env>) plus canary pod restarts/readiness.
  4. Promote when requests >= MIN_REQUESTS, error rate <= MAX_ERROR_RATE and
     no restarts: roll the stable `gateway` Deployment to the same image,
     return 100% traffic to stable, scale the canary to 0.
     Otherwise roll back: 100% to stable, canary to 0, exit 1.

Requires kubectl access to the private cluster (CI opens a Session Manager
tunnel first) and AWS credentials allowed to read CloudWatch metrics.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

NAMESPACE = "aegisvolt"
INGRESS = "gateway-private"
ACTION_ANNOTATION = "alb.ingress.kubernetes.io/actions.graphql-weighted"


@dataclass(frozen=True)
class CanaryObservation:
    requests: float
    errors: float
    restarts: int
    ready: bool


def evaluate(observation: CanaryObservation, min_requests: int, max_error_rate: float) -> tuple[bool, str]:
    """Pure promotion gate, unit-tested in tests/test_canary_gate.py."""
    if not observation.ready:
        return False, "canary pod is not ready"
    if observation.restarts > 0:
        return False, f"canary restarted {observation.restarts} time(s)"
    if observation.requests < min_requests:
        return False, f"only {observation.requests:.0f} canary requests observed (< {min_requests}); not enough evidence"
    rate = observation.errors / observation.requests
    if rate > max_error_rate:
        return False, f"canary 5xx rate {rate:.2%} exceeds {max_error_rate:.2%}"
    return True, f"{observation.requests:.0f} requests, 5xx rate {rate:.2%}"


def weighted_action(canary_weight: int) -> str:
    if not 0 <= canary_weight <= 100:
        raise ValueError("canary weight must be between 0 and 100")
    return json.dumps(
        {
            "type": "forward",
            "forwardConfig": {
                "targetGroups": [
                    {"serviceName": "gateway", "servicePort": "80", "weight": 100 - canary_weight},
                    {"serviceName": "gateway-canary", "servicePort": "80", "weight": canary_weight},
                ]
            },
        },
        separators=(",", ":"),
    )


def kubectl(*args: str, capture: bool = False) -> str:
    result = subprocess.run(["kubectl", "-n", NAMESPACE, *args], check=True, text=True, capture_output=capture)
    return result.stdout if capture else ""


def set_weight(canary_weight: int) -> None:
    kubectl("annotate", "ingress", INGRESS, "--overwrite", f"{ACTION_ANNOTATION}={weighted_action(canary_weight)}")
    print(f"traffic: stable {100 - canary_weight}% / canary {canary_weight}%", flush=True)


def observe(environment: str, region: str, start: datetime, end: datetime) -> CanaryObservation:
    import boto3

    cloudwatch = boto3.client("cloudwatch", region_name=region)

    def total(metric: str) -> float:
        response = cloudwatch.get_metric_statistics(
            Namespace=f"AegisVolt/{environment}",
            MetricName=metric,
            StartTime=start,
            EndTime=end,
            Period=60,
            Statistics=["Sum"],
        )
        return sum(point["Sum"] for point in response["Datapoints"])

    pods = json.loads(kubectl("get", "pods", "-l", "app=gateway-canary", "-o", "json", capture=True))["items"]
    statuses = [status for pod in pods for status in pod.get("status", {}).get("containerStatuses", [])]
    return CanaryObservation(
        requests=total("Requests-gateway-canary"),
        errors=total("Http5xx-gateway-canary"),
        restarts=sum(status.get("restartCount", 0) for status in statuses),
        ready=bool(statuses) and all(status.get("ready") for status in statuses),
    )


def rollback(reason: str) -> int:
    print(f"ROLLBACK: {reason}", file=sys.stderr, flush=True)
    set_weight(0)
    kubectl("scale", "deployment/gateway-canary", "--replicas=0")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--environment", required=True, choices=["dev", "test", "prod"])
    parser.add_argument("--image", required=True, help="new gateway image (immutable tag)")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--weight", type=int, default=20, help="canary traffic percentage (10-20)")
    parser.add_argument("--window", type=int, default=300, help="observation window in seconds")
    parser.add_argument("--min-requests", type=int, default=20)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--metric-delay", type=int, default=90, help="seconds to wait for log metric filters")
    args = parser.parse_args()
    if not 10 <= args.weight <= 20:
        parser.error("--weight must be between 10 and 20 percent")

    kubectl("set", "image", "deployment/gateway-canary", f"gateway={args.image}")
    kubectl("scale", "deployment/gateway-canary", "--replicas=1")
    try:
        kubectl("rollout", "status", "deployment/gateway-canary", "--timeout=180s")
    except subprocess.CalledProcessError:
        return rollback("canary did not become ready")

    start = datetime.now(timezone.utc)
    set_weight(args.weight)
    time.sleep(args.window)
    end = datetime.now(timezone.utc)
    time.sleep(args.metric_delay)

    observation = observe(args.environment, args.region, start - timedelta(seconds=60), end + timedelta(seconds=60))
    ok, reason = evaluate(observation, args.min_requests, args.max_error_rate)
    print(f"canary observation: {observation} -> {reason}", flush=True)
    if not ok:
        return rollback(reason)

    kubectl("set", "image", "deployment/gateway", f"gateway={args.image}")
    try:
        kubectl("rollout", "status", "deployment/gateway", "--timeout=300s")
    except subprocess.CalledProcessError:
        return rollback("stable rollout of the promoted image failed")
    set_weight(0)
    kubectl("scale", "deployment/gateway-canary", "--replicas=0")
    print(f"PROMOTED {args.image} to 100%: {reason}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
