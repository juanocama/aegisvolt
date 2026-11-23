"""Per-environment feature flags.

Source of truth in deployed environments is the environment's own DynamoDB
flags table (``FLAGS_TABLE``, e.g. ``aegisvolt-dev-flags``), one item per flag:
``{"id": <FLAG_NAME>, "enabled": <bool>}``. Changing an item takes effect
within ``FLAG_CACHE_SECONDS`` without redeploying, and each environment's
table is isolated from the others.

When ``FLAGS_TABLE`` is not configured (unit tests, local Compose) the values
come from process environment variables of the same name.

Errors stay visible: invalid values, a flags table that cannot be read, or a
flag missing from a configured table raise instead of silently defaulting.
"""

import os
import threading
import time

from common.environment import current_environment

FEATURE_FLAG_NAMES = (
    "ENABLE_DYNAMIC_SURGE_PRICING",
    "ENABLE_FAST_CHARGE_BOOST",
    "SIMULATE_CHARGER_HARDWARE_FAULT",
)

_cache_lock = threading.Lock()
_cache: dict = {"table": None, "expires": 0.0, "flags": None}


def _parse(name: str, value) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1"}:
        return True
    if text in {"false", "0"}:
        return False
    raise ValueError(f"{name} must be set to true or false")


def flags_table_name() -> str | None:
    table = os.getenv("FLAGS_TABLE", "").strip()
    if not table:
        return None
    environment = current_environment()
    if environment not in table.split("-"):
        raise ValueError(f"FLAGS_TABLE must include the active environment '{environment}'")
    return table


def flag_source() -> str:
    table = flags_table_name()
    return f"dynamodb:{table}" if table else "environment"


def _load_from_environment() -> dict[str, bool]:
    flags = {}
    for name in FEATURE_FLAG_NAMES:
        value = os.getenv(name)
        flags[name] = False if value is None else _parse(name, value)
    return flags


def _load_from_dynamodb(table_name: str) -> dict[str, bool]:
    from common.dynamodb import dynamodb_client

    response = dynamodb_client().batch_get_item(
        RequestItems={
            table_name: {
                "Keys": [{"id": {"S": name}} for name in FEATURE_FLAG_NAMES],
                "ConsistentRead": True,
            }
        }
    )
    if response.get("UnprocessedKeys"):
        raise RuntimeError("Feature flag read was throttled; retry")
    items = {item["id"]["S"]: item for item in response["Responses"].get(table_name, [])}
    missing = [name for name in FEATURE_FLAG_NAMES if name not in items]
    if missing:
        raise RuntimeError(f"Feature flags not provisioned in {table_name}: {', '.join(missing)}")
    flags = {}
    for name in FEATURE_FLAG_NAMES:
        attribute = items[name].get("enabled")
        if not attribute or "BOOL" not in attribute:
            raise ValueError(f"{name} in {table_name} must have a boolean 'enabled' attribute")
        flags[name] = attribute["BOOL"]
    return flags


def load_feature_flags() -> dict[str, bool]:
    table_name = flags_table_name()
    if table_name is None:
        return _load_from_environment()

    ttl = float(os.getenv("FLAG_CACHE_SECONDS", "5"))
    now = time.monotonic()
    with _cache_lock:
        if _cache["table"] == table_name and _cache["flags"] is not None and now < _cache["expires"]:
            return dict(_cache["flags"])
    flags = _load_from_dynamodb(table_name)
    with _cache_lock:
        _cache.update(table=table_name, flags=flags, expires=now + ttl)
    return dict(flags)


def clear_flag_cache() -> None:
    with _cache_lock:
        _cache.update(table=None, flags=None, expires=0.0)
