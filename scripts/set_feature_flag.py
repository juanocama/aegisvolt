"""Read or change a per-environment feature flag at runtime (no redeploy).

Examples:
  python scripts/set_feature_flag.py --env dev --list
  python scripts/set_feature_flag.py --env test --flag SIMULATE_CHARGER_HARDWARE_FAULT --enabled true
  # Local Compose/Floci only: create and seed the emulated table
  AWS_ENDPOINT_URL=http://localhost:4566 python scripts/set_feature_flag.py --env dev --seed-local

Against AWS the table must already exist (Terraform owns it); this script
never creates tables outside an emulator endpoint.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import boto3  # noqa: E402

from common.feature_flags import FEATURE_FLAG_NAMES  # noqa: E402

LOCAL_DEFAULTS = {
    "ENABLE_DYNAMIC_SURGE_PRICING": True,
    "ENABLE_FAST_CHARGE_BOOST": False,
    "SIMULATE_CHARGER_HARDWARE_FAULT": False,
}


def _table(env: str):
    kwargs = {"region_name": os.getenv("AWS_DEFAULT_REGION", "us-east-1")}
    if os.getenv("AWS_ENDPOINT_URL"):
        kwargs["endpoint_url"] = os.environ["AWS_ENDPOINT_URL"]
    return boto3.resource("dynamodb", **kwargs).Table(f"aegisvolt-{env}-flags")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True, choices=["dev", "test", "prod"])
    parser.add_argument("--flag", choices=FEATURE_FLAG_NAMES)
    parser.add_argument("--enabled", choices=["true", "false"])
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--seed-local", action="store_true")
    args = parser.parse_args()
    table = _table(args.env)

    if args.seed_local:
        if not os.getenv("AWS_ENDPOINT_URL"):
            parser.error("--seed-local is only allowed against an emulator (AWS_ENDPOINT_URL)")
        from common.dynamodb import ensure_table

        os.environ.setdefault("ENVIRONMENT", args.env)
        table = ensure_table(table.name)
        for name, value in LOCAL_DEFAULTS.items():
            try:
                table.put_item(Item={"id": name, "enabled": value}, ConditionExpression="attribute_not_exists(id)")
            except table.meta.client.exceptions.ConditionalCheckFailedException:
                pass

    if args.flag:
        if args.enabled is None:
            parser.error("--enabled is required with --flag")
        table.update_item(
            Key={"id": args.flag},
            UpdateExpression="SET enabled = :v",
            ConditionExpression="attribute_exists(id)",
            ExpressionAttributeValues={":v": args.enabled == "true"},
        )

    items = {item["id"]: item["enabled"] for item in table.scan(ConsistentRead=True)["Items"]}
    for name in FEATURE_FLAG_NAMES:
        print(f"{args.env:5} {name:34} {items.get(name, 'MISSING')}")
    return 0 if all(name in items for name in FEATURE_FLAG_NAMES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
