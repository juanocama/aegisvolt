import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from common.observability import current_correlation_id, install_request_logging
from observability.prefect.audit_flow import (
    _load_referenced_service_records,
    _scan_all,
    load_environment_config,
    summarize_sagas,
)


def test_gateway_health_endpoint_is_registered(backend):
    assert any(route.path == "/health" for route in backend["gateway"].app.routes)


def test_station_reservation_persists_saga_correlation_id(backend):
    station = backend["station"]
    correlation_id = "phase4-saga-correlation"
    result = station.reserve(station.Reservation(
        station_id="st-1",
        connector_id="c-1",
        wallet_id="audit-wallet",
        idempotency_key="phase4-correlation-reservation",
        correlation_id=correlation_id,
    ))
    item = station.table.get_item(Key={"id": result["id"]}, ConsistentRead=True)["Item"]
    assert item["correlation_id"] == correlation_id
    station.cancel(result["id"])


def test_audit_configuration_requires_real_private_endpoints_and_environment_tables():
    with pytest.raises(ValueError, match="Set AEGISVOLT_AUDIT_ENVIRONMENTS_JSON"):
        load_environment_config("")

    config = {
        environment: {
            "urls": {service: f"http://{service}.{environment}.internal" for service in ("gateway", "station-reservation", "billing-wallet", "energy-dispatch")},
            "tables": {
                "sagas": f"aegisvolt-{environment}-sagas",
                "station-reservation": f"aegisvolt-{environment}-stations",
                "billing-wallet": f"aegisvolt-{environment}-wallets",
                "energy-dispatch": f"aegisvolt-{environment}-dispatch",
            },
        }
        for environment in ("dev", "test", "prod")
    }
    assert set(load_environment_config(json.dumps(config))) == {"dev", "test", "prod"}
    config["prod"]["tables"]["sagas"] = "aegisvolt-dev-sagas"
    with pytest.raises(ValueError, match="environment-specific"):
        load_environment_config(json.dumps(config))


def test_saga_audit_reports_steps_compensation_and_missing_records():
    saga = {
        "id": "saga-1",
        "correlation_id": "corr-1",
        "state": "COMPENSATION_FAILED",
        "reservation_id": "reservation-1",
        "charge_id": "charge-1",
        "activation_id": "activation-missing",
        "pending_compensations": ["refund"],
        "events": [
            {"step": "reservation", "outcome": "succeeded"},
            {"step": "charge", "outcome": "succeeded"},
            {"step": "activation", "outcome": "failed"},
            {"step": "compensation", "outcome": "started"},
            {"step": "refund", "outcome": "failed"},
        ],
    }
    report = summarize_sagas(
        [saga],
        {
            "station-reservation": [{"id": "reservation-1", "record_type": "reservation", "status": "reserved", "correlation_id": "corr-1"}],
            "billing-wallet": [{"id": "charge-1", "record_type": "charge", "status": "charged", "correlation_id": "corr-1"}],
            "energy-dispatch": [],
        },
    )
    result = report["sagas"][0]
    assert result["completed_steps"] == ["reservation", "charge"]
    assert result["failed_steps"] == ["activation", "refund"]
    assert result["compensation_attempts"] == 1
    assert result["compensation_retries"] == 0
    assert "pending_compensations" in result["issues"]
    assert "missing_activation_id_record" in result["issues"]


@pytest.mark.asyncio
@pytest.mark.parametrize("correlation_id", ["bad id", "x" * 129, "<script>\n"])
async def test_invalid_or_oversized_correlation_id_is_replaced(correlation_id, monkeypatch):
    app = FastAPI()
    install_request_logging(app, "test")
    app.add_api_route("/items/{item_id}", lambda item_id: {"id": item_id}, methods=["GET"])
    logged = []
    monkeypatch.setattr("common.observability.logger.info", logged.append)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/items/private-resource-id", headers={"X-Correlation-ID": correlation_id})

    returned_id = response.headers["X-Correlation-ID"]
    assert str(uuid.UUID(returned_id)) == returned_id
    assert returned_id != correlation_id
    assert json.loads(logged[0])["correlation_id"] == returned_id


@pytest.mark.asyncio
async def test_valid_correlation_id_propagates_and_dynamic_path_is_not_logged(monkeypatch):
    app = FastAPI()
    install_request_logging(app, "test")
    observed = {}

    @app.post("/items/{item_id}")
    async def get_item(item_id: str):
        observed["id"] = current_correlation_id()
        return {"id": item_id}

    logged = []
    monkeypatch.setattr("common.observability.logger.info", logged.append)
    valid_id = "phase4-correlation:request-17"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/items/private-resource-id?token=query-secret",
            headers={"X-Correlation-ID": valid_id, "Authorization": "Bearer auth-secret"},
            json={"wallet_id": "business-secret", "amount": 99},
        )

    log_record = json.loads(logged[0])
    assert response.headers["X-Correlation-ID"] == valid_id
    assert observed["id"] == valid_id
    assert log_record["correlation_id"] == valid_id
    assert log_record["path"] == "/items/{item_id}"
    assert "private-resource-id" not in logged[0]
    for secret in ("query-secret", "auth-secret", "business-secret", "99"):
        assert secret not in logged[0]


def test_audit_distinguishes_active_stale_terminal_and_failed_sagas():
    now = datetime(2026, 11, 23, tzinfo=timezone.utc)
    service_records = {
        "station-reservation": [{"id": "reservation-completed", "status": "reserved"}],
        "billing-wallet": [{"id": "charge-completed", "status": "charged"}],
        "energy-dispatch": [{"id": "activation-completed", "status": "active"}],
    }
    sagas = [
        {"id": "active", "state": "CHARGING", "updated_at": (now - timedelta(seconds=30)).isoformat(), "lease_expires_at": now.timestamp() + 60},
        {"id": "stale", "state": "ACTIVATING", "updated_at": (now - timedelta(seconds=600)).isoformat(), "lease_expires_at": now.timestamp() - 1},
        {"id": "completed", "state": "COMPLETED", "updated_at": now.isoformat(), "reservation_id": "reservation-completed", "charge_id": "charge-completed", "activation_id": "activation-completed", "events": []},
        {"id": "failed-terminal", "state": "FAILED", "updated_at": now.isoformat(), "events": [{"step": "reservation", "outcome": "failed"}]},
        {"id": "failed", "state": "COMPENSATION_FAILED", "updated_at": now.isoformat(), "pending_compensations": ["refund"], "events": [
            {"step": "compensation", "outcome": "started"},
            {"step": "refund", "outcome": "started"},
            {"step": "compensation_retry", "outcome": "started"},
        ]},
    ]

    report = summarize_sagas(sagas, service_records, now=now, stale_after_seconds=300)
    by_id = {entry["saga_id"]: entry for entry in report["sagas"]}
    assert by_id["active"]["issues"] == []
    assert "stale_non_terminal_state" in by_id["stale"]["issues"]
    assert by_id["completed"]["issues"] == []
    assert "failed_state" in by_id["failed-terminal"]["issues"]
    assert "compensation_failed" in by_id["failed"]["issues"]
    assert by_id["failed"]["compensation_attempts"] == 1
    assert by_id["failed"]["compensation_retries"] == 1


def test_stale_threshold_must_be_positive():
    with pytest.raises(ValueError, match="positive integer"):
        summarize_sagas([], {}, stale_after_seconds=0)


def test_regular_audit_batch_gets_only_referenced_service_records():
    requests = []

    def batch_get_item(**kwargs):
        requests.append(kwargs["RequestItems"])
        return {"Responses": {
            "stations": [{"id": "reservation-1", "status": "reserved"}],
            "wallets": [{"id": "charge-1", "status": "charged"}],
            "dispatch": [{"id": "activation-1", "status": "active"}],
        }}

    dynamodb = SimpleNamespace(meta=SimpleNamespace(client=SimpleNamespace(batch_get_item=batch_get_item)))
    records = _load_referenced_service_records(
        dynamodb,
        {"station-reservation": "stations", "billing-wallet": "wallets", "energy-dispatch": "dispatch"},
        [{"reservation_id": "reservation-1", "charge_id": "charge-1", "activation_id": "activation-1"}],
    )
    assert len(requests) == 1
    assert records["station-reservation"] == [{"id": "reservation-1", "status": "reserved"}]
    assert records["billing-wallet"][0]["id"] == "charge-1"
    assert records["energy-dispatch"][0]["status"] == "active"


def test_paged_scan_reads_every_page():
    class Paginator:
        def paginate(self, **kwargs):
            assert kwargs == {"TableName": "sagas"}
            return [{"Items": [{"id": "one"}], "LastEvaluatedKey": {"id": "one"}}, {"Items": [{"id": "two"}]}]

    table = SimpleNamespace(name="sagas", meta=SimpleNamespace(client=SimpleNamespace(get_paginator=lambda operation: Paginator())))
    assert _scan_all(table) == [{"id": "one"}, {"id": "two"}]


def test_skipped_orphan_sweep_is_reported_as_incomplete_not_zero():
    report = summarize_sagas([], {}, orphan_audit_complete=False)
    assert report["orphan_audit_complete"] is False
    assert report["orphan_service_records"] is None
    assert report["records_without_correlation_id"] is None


def test_scan_all_deserializes_real_dynamodb_pages():
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    with moto.mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="phase4-scan-pagination-test",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        padding = "x" * 200_000  # forces multiple 1 MB scan pages
        for index in range(12):
            table.put_item(Item={"id": f"saga-{index}", "state": "COMPLETED", "lease_expires_at": 5, "pad": padding})
        items = _scan_all(table)
    assert len(items) == 12
    assert {item["state"] for item in items} == {"COMPLETED"}
    assert all(isinstance(item["id"], str) for item in items)


def test_fresh_activation_uncertain_saga_is_not_flagged():
    now = datetime(2026, 11, 23, tzinfo=timezone.utc)
    report = summarize_sagas(
        [{"id": "s1", "state": "ACTIVATION_UNCERTAIN", "updated_at": (now - timedelta(seconds=10)).isoformat()}],
        {"station-reservation": [], "billing-wallet": [], "energy-dispatch": []},
        now=now,
    )
    assert report["inconsistent_sagas"] == []


def test_referenced_service_records_load_through_real_dynamodb_resource():
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    names = {"station-reservation": "p4-bg-stations", "billing-wallet": "p4-bg-wallets", "energy-dispatch": "p4-bg-dispatch"}
    with moto.mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        for name in names.values():
            dynamodb.create_table(
                TableName=name,
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
        # 150 referenced reservations exceed the 100-key BatchGetItem limit.
        for index in range(150):
            dynamodb.Table(names["station-reservation"]).put_item(Item={"id": f"r{index}", "status": "reserved"})
        dynamodb.Table(names["billing-wallet"]).put_item(Item={"id": "c1", "status": "charged"})
        sagas = [{"reservation_id": f"r{index}"} for index in range(150)] + [{"charge_id": "c1"}, {"activation_id": "missing"}]
        records = _load_referenced_service_records(dynamodb, names, sagas)
    assert len(records["station-reservation"]) == 150
    assert records["billing-wallet"] == [{"id": "c1", "status": "charged"}]
    assert records["energy-dispatch"] == []
