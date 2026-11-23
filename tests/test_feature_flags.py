"""Per-environment feature flags backed by DynamoDB (spec 2.2, rubric 6.3/6.4)."""

import boto3
import pytest

from common import feature_flags
from common.feature_flags import FEATURE_FLAG_NAMES, clear_flag_cache, load_feature_flags


def _flags_table(name: str, values: dict[str, bool]):
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    try:
        table = dynamodb.create_table(
            TableName=name,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
    except dynamodb.meta.client.exceptions.ResourceInUseException:
        table = dynamodb.Table(name)
    for flag, enabled in values.items():
        table.put_item(Item={"id": flag, "enabled": enabled})
    return table


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    clear_flag_cache()
    monkeypatch.setenv("FLAG_CACHE_SECONDS", "0")
    yield
    clear_flag_cache()


def test_flags_are_read_from_the_environment_table(monkeypatch):
    _flags_table("aegisvolt-dev-flags", {name: False for name in FEATURE_FLAG_NAMES} | {"ENABLE_DYNAMIC_SURGE_PRICING": True})
    monkeypatch.setenv("FLAGS_TABLE", "aegisvolt-dev-flags")
    assert load_feature_flags() == {
        "ENABLE_DYNAMIC_SURGE_PRICING": True,
        "ENABLE_FAST_CHARGE_BOOST": False,
        "SIMULATE_CHARGER_HARDWARE_FAULT": False,
    }
    assert feature_flags.flag_source() == "dynamodb:aegisvolt-dev-flags"


def test_runtime_toggle_is_visible_without_restart(monkeypatch):
    table = _flags_table("aegisvolt-dev-flags", {name: False for name in FEATURE_FLAG_NAMES})
    monkeypatch.setenv("FLAGS_TABLE", "aegisvolt-dev-flags")
    assert load_feature_flags()["SIMULATE_CHARGER_HARDWARE_FAULT"] is False
    table.put_item(Item={"id": "SIMULATE_CHARGER_HARDWARE_FAULT", "enabled": True})
    assert load_feature_flags()["SIMULATE_CHARGER_HARDWARE_FAULT"] is True


def test_environment_tables_are_isolated(monkeypatch):
    _flags_table("aegisvolt-dev-flags", {name: True for name in FEATURE_FLAG_NAMES})
    _flags_table("aegisvolt-prod-flags", {name: False for name in FEATURE_FLAG_NAMES})
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("FLAGS_TABLE", "aegisvolt-prod-flags")
    assert not any(load_feature_flags().values())
    monkeypatch.setenv("ENVIRONMENT", "dev")


def test_table_must_belong_to_the_active_environment(monkeypatch):
    monkeypatch.setenv("FLAGS_TABLE", "aegisvolt-prod-flags")
    with pytest.raises(ValueError, match="active environment"):
        load_feature_flags()


def test_missing_flag_item_is_an_error_not_a_default(monkeypatch):
    table = _flags_table("aegisvolt-dev-flags", {name: False for name in FEATURE_FLAG_NAMES})
    table.delete_item(Key={"id": "ENABLE_FAST_CHARGE_BOOST"})
    monkeypatch.setenv("FLAGS_TABLE", "aegisvolt-dev-flags")
    with pytest.raises(RuntimeError, match="ENABLE_FAST_CHARGE_BOOST"):
        load_feature_flags()


def test_environment_variables_are_used_when_no_table_is_configured(monkeypatch):
    monkeypatch.delenv("FLAGS_TABLE", raising=False)
    monkeypatch.setenv("SIMULATE_CHARGER_HARDWARE_FAULT", "true")
    assert load_feature_flags()["SIMULATE_CHARGER_HARDWARE_FAULT"] is True
    monkeypatch.setenv("SIMULATE_CHARGER_HARDWARE_FAULT", "maybe")
    with pytest.raises(ValueError):
        load_feature_flags()
    monkeypatch.setenv("SIMULATE_CHARGER_HARDWARE_FAULT", "false")
