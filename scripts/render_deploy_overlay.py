"""Write a throwaway Kustomize overlay that binds k8s/overlays/<env> to real
values from Terraform outputs (account, ECR images, IRSA roles, private API).

Used by .github/workflows/deploy.yml and for manual demos. Output goes to a
directory outside the repository (never commit account-specific overlays).

  python scripts/render_deploy_overlay.py --env dev --account 123456789012 \
      --region us-east-1 --tag <git-sha> --api-id abc123 --out /tmp/deploy-dev
  kubectl kustomize --load-restrictor LoadRestrictionsNone /tmp/deploy-dev
"""

import argparse
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ["gateway", "station-reservation", "billing-wallet", "energy-dispatch", "frontend"]
IRSA_SERVICE_ACCOUNTS = ["gateway", "station-reservation", "billing-wallet", "energy-dispatch"]


def render(env: str, account: str, region: str, tag: str, api_id: str, stable_gateway_tag: str | None) -> str:
    if not re.fullmatch(r"\d{12}", account):
        raise ValueError("account must be a 12-digit AWS account ID")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", tag):
        raise ValueError("tag must be an immutable image tag (e.g. a git SHA)")
    if not re.fullmatch(r"[a-z0-9]{10}", api_id):
        raise ValueError("api-id must be the private REST API ID from Terraform")
    registry = f"{account}.dkr.ecr.{region}.amazonaws.com/aegisvolt/{env}"
    placeholder = f"CHANGE_ME_ECR_ACCOUNT.dkr.ecr.CHANGE_ME_AWS_REGION.amazonaws.com/aegisvolt/{env}"
    lines = [
        "apiVersion: kustomize.config.k8s.io/v1beta1",
        "kind: Kustomization",
        "resources:",
        f"  - {{OVERLAY}}",
        "images:",
    ]
    for image in IMAGES:
        image_tag = stable_gateway_tag if image == "gateway" and stable_gateway_tag else tag
        lines += [f"  - name: {placeholder}/{image}", f"    newName: {registry}/{image}", f"    newTag: {image_tag}"]
    lines.append("patches:")
    for sa in IRSA_SERVICE_ACCOUNTS:
        lines += [
            f"  - target: {{kind: ServiceAccount, name: {sa}}}",
            "    patch: |-",
            "      - op: replace",
            "        path: /metadata/annotations/eks.amazonaws.com~1role-arn",
            f"        value: arn:aws:iam::{account}:role/{env}-aegisvolt-{sa}-irsa",
        ]
    lines += [
        "  - target: {kind: ConfigMap, name: frontend-config}",
        "    patch: |-",
        "      - op: replace",
        "        path: /data/GRAPHQL_UPSTREAM_HOST",
        f"        value: {api_id}.execute-api.{region}.amazonaws.com",
        "  - target: {kind: ConfigMap, name: aegisvolt-config}",
        "    patch: |-",
        "      - op: replace",
        "        path: /data/AWS_DEFAULT_REGION",
        f"        value: {region}",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True, choices=["dev", "test", "prod"])
    parser.add_argument("--account", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--api-id", required=True)
    parser.add_argument("--stable-gateway-tag", help="keep the stable gateway on this tag (canary rollout)")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out = Path(args.out).resolve()
    if ROOT in out.parents or out == ROOT:
        parser.error("--out must be outside the repository")
    out.mkdir(parents=True, exist_ok=True)
    overlay = os.path.relpath(ROOT / "k8s" / "overlays" / args.env, out).replace("\\", "/")
    content = render(args.env, args.account, args.region, args.tag, args.api_id, args.stable_gateway_tag)
    (out / "kustomization.yaml").write_text(content.replace("{OVERLAY}", overlay))
    print(out / "kustomization.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
