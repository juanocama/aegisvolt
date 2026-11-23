"""Read-only, environment-scoped health and SAGA audit for Prefect."""

import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlparse

import boto3
import httpx
from prefect import flow, task

ENVIRONMENTS = ("dev", "test", "prod")
SERVICE_NAMES = ("gateway", "station-reservation", "billing-wallet", "energy-dispatch")
TERMINAL_STATES = {"COMPLETED", "COMPENSATED", "FAILED", "STOPPED"}
ACTIVE_STATES = {
    "STARTED", "RESERVING", "RESERVATION_UNCERTAIN", "RESERVATION_COMPLETED",
    "CHARGING", "CHARGE_UNCERTAIN", "CHARGE_FAILED", "CHARGE_COMPLETED",
    "ACTIVATING", "ACTIVATION_UNCERTAIN", "COMPENSATING",
}
DEFAULT_STALE_AFTER_SECONDS = 300
SERVICE_TABLE_SUFFIXES = {
    "station-reservation": "stations",
    "billing-wallet": "wallets",
    "energy-dispatch": "dispatch",
}


def load_environment_config(raw: str) -> dict:
    if not raw:
        raise ValueError("Set AEGISVOLT_AUDIT_ENVIRONMENTS_JSON for private dev, test, and prod endpoints and tables.")
    config = json.loads(raw)
    if set(config) != set(ENVIRONMENTS):
        raise ValueError("Audit configuration must define exactly dev, test, and prod.")
    for environment, values in config.items():
        expected_tables = {
            "sagas": f"aegisvolt-{environment}-sagas",
            **{service: f"aegisvolt-{environment}-{suffix}" for service, suffix in SERVICE_TABLE_SUFFIXES.items()},
        }
        if values.get("tables") != expected_tables:
            raise ValueError(f"{environment} audit table names must match the environment-specific AegisVolt tables.")
        for service in SERVICE_NAMES:
            parsed = urlparse(values.get("urls", {}).get(service, ""))
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
                raise ValueError(f"Configure a private HTTP(S) URL for {environment}/{service}.")
    return config


@task
def check_environment_health(config: dict) -> dict:
    results = {}
    with httpx.Client(timeout=5) as client:
        for environment, values in config.items():
            results[environment] = {}
            for service, base_url in values["urls"].items():
                try:
                    response = client.get(f"{base_url.rstrip('/')}/health")
                    response.raise_for_status()
                    results[environment][service] = {"healthy": True, "status_code": response.status_code}
                except httpx.HTTPError as error:
                    results[environment][service] = {"healthy": False, "error_type": type(error).__name__}
    return results


def _scan_all(table) -> list[dict]:
    # A resource-derived client already (de)serializes DynamoDB attribute values.
    paginator = table.meta.client.get_paginator("scan")
    return [item for page in paginator.paginate(TableName=table.name) for item in page.get("Items", [])]


def _load_referenced_service_records(dynamodb, table_names: dict, sagas: list[dict]) -> dict[str, list[dict]]:
    """BatchGet only service rows referenced by SAGA items (all pages/chunks)."""
    reference_fields = {
        "station-reservation": "reservation_id",
        "billing-wallet": "charge_id",
        "energy-dispatch": "activation_id",
    }
    ids_by_service = {
        service: sorted({saga[field] for saga in sagas if saga.get(field)})
        for service, field in reference_fields.items()
    }
    # The resource client (de)serializes attribute values itself, so keys and
    # returned items are plain Python values, exactly like Table operations.
    client = dynamodb.meta.client
    records = {service: [] for service in reference_fields}
    pending = []
    for service, ids in ids_by_service.items():
        pending.extend((service, table_names[service], item_id) for item_id in ids)

    # A single BatchGetItem call can contain at most 100 keys across tables.
    while pending:
        chunk, pending = pending[:100], pending[100:]
        request_items = {}
        service_by_table = {}
        for service, table_name, item_id in chunk:
            request_items.setdefault(table_name, {"Keys": []})["Keys"].append({"id": item_id})
            service_by_table[table_name] = service
        response = client.batch_get_item(RequestItems=request_items)
        for table_name, items in response.get("Responses", {}).items():
            records[service_by_table[table_name]].extend(items)
        unprocessed = response.get("UnprocessedKeys", {})
        retries = 0
        while unprocessed and retries < 5:
            time.sleep(min(0.1 * (2 ** retries), 1.0))
            response = client.batch_get_item(RequestItems=unprocessed)
            for table_name, items in response.get("Responses", {}).items():
                records[service_by_table[table_name]].extend(items)
            unprocessed = response.get("UnprocessedKeys", {})
            retries += 1
        if unprocessed:
            raise RuntimeError("DynamoDB BatchGetItem returned unprocessed service records after five retries")
    return records


def _parse_timestamp(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def summarize_sagas(
    items: list[dict],
    service_records: dict[str, list[dict]],
    *,
    now: datetime | None = None,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    orphan_audit_complete: bool = True,
) -> dict:
    if stale_after_seconds <= 0:
        raise ValueError("stale_after_seconds must be a positive integer")
    now = now or datetime.now(timezone.utc)
    now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
    states = {}
    audits = []
    known_correlations = {item.get("correlation_id") for item in items if item.get("correlation_id")}
    orphan_records = []
    records_by_service = {
        service: {record.get("id"): record for record in records if record.get("id")}
        for service, records in service_records.items()
    }
    for service, records in service_records.items():
        for record in records:
            correlation_id = record.get("correlation_id")
            if record.get("record_type") in {"reservation", "charge", "activation"} and correlation_id and correlation_id not in known_correlations:
                orphan_records.append({"service": service, "record_id": record.get("id"), "correlation_id": correlation_id})

    for saga in items:
        state = saga.get("state", "UNKNOWN")
        states[state] = states.get(state, 0) + 1
        events = saga.get("events", [])
        completed_steps = [event.get("step") for event in events if event.get("outcome") == "succeeded"]
        failed_steps = [event.get("step") for event in events if event.get("outcome") in {"failed", "uncertain"}]
        compensation_events = [event for event in events if event.get("step") in {"compensation", "refund", "release_reservation"}]
        issues = []
        if state == "COMPENSATION_FAILED":
            issues.append("compensation_failed")
        elif state == "FAILED":
            issues.append("failed_state")
        elif state not in TERMINAL_STATES:
            updated_at = _parse_timestamp(saga.get("updated_at"))
            lease_expires_at = saga.get("lease_expires_at", 0)
            lease_is_active = isinstance(lease_expires_at, (int, float, Decimal)) and lease_expires_at > now.timestamp()
            if updated_at is None:
                issues.append("non_terminal_missing_or_invalid_updated_at")
            elif (now - updated_at).total_seconds() >= stale_after_seconds and not lease_is_active:
                issues.append("stale_non_terminal_state")
            elif state not in ACTIVE_STATES:
                issues.append("unknown_non_terminal_state")
        if saga.get("pending_compensations"):
            issues.append("pending_compensations")
        references = (
            ("reservation_id", "station-reservation", {"reserved", "cancelled"}),
            ("charge_id", "billing-wallet", {"charged"}),
            ("activation_id", "energy-dispatch", {"active", "failed"}),
        )
        # In-flight operations can legitimately lack downstream records. Validate
        # references after completion or when compensation has failed.
        validate_references = state in TERMINAL_STATES or state == "COMPENSATION_FAILED"
        for field, service, allowed_statuses in (references if validate_references else ()):
            record_id = saga.get(field)
            if not record_id:
                continue
            record = records_by_service[service].get(record_id)
            if record is None:
                issues.append(f"missing_{field}_record")
            elif record.get("status") not in allowed_statuses:
                issues.append(f"unexpected_{field}_status")
        if state == "COMPLETED" and not all(saga.get(field) for field in ("reservation_id", "charge_id", "activation_id")):
            issues.append("completed_saga_missing_step_reference")
        audits.append({
            "saga_id": saga.get("id"),
            "correlation_id": saga.get("correlation_id"),
            "state": state,
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "compensation_attempts": sum(event.get("step") == "compensation" and event.get("outcome") == "started" for event in events),
            "compensation_retries": sum(event.get("step") == "compensation_retry" and event.get("outcome") == "started" for event in events),
            "compensation_outcomes": [{"step": event.get("step"), "outcome": event.get("outcome")} for event in compensation_events],
            "issues": issues,
        })
    return {
        "counts_by_state": states,
        "sagas": audits,
        "orphan_service_records": orphan_records if orphan_audit_complete else None,
        "orphan_audit_complete": orphan_audit_complete,
        "inconsistent_sagas": [saga for saga in audits if saga["issues"]],
        "records_without_correlation_id": {
            service: sum(1 for record in records if record.get("record_type") in {"reservation", "charge", "activation"} and not record.get("correlation_id"))
            for service, records in service_records.items()
        } if orphan_audit_complete else None,
    }


@task
def audit_environment_sagas(
    environment: str,
    table_names: dict,
    aws_endpoint: str | None,
    region: str,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    full_orphan_scan: bool = False,
) -> dict:
    session = boto3.Session(region_name=region)
    dynamodb = session.resource("dynamodb", endpoint_url=aws_endpoint) if aws_endpoint else session.resource("dynamodb")
    saga_items = _scan_all(dynamodb.Table(table_names["sagas"]))
    service_records = _load_referenced_service_records(dynamodb, table_names, saga_items)
    orphan_audit_complete = full_orphan_scan
    if full_orphan_scan:
        service_records = {
            service: _scan_all(dynamodb.Table(table_names[service]))
            for service in SERVICE_TABLE_SUFFIXES
        }
    return {
        "environment": environment,
        **summarize_sagas(
            saga_items,
            service_records,
            stale_after_seconds=stale_after_seconds,
            orphan_audit_complete=orphan_audit_complete,
        ),
    }


@task
def publish_metrics(audits: list[dict], region: str, aws_endpoint: str | None) -> None:
    session = boto3.Session(region_name=region)
    cloudwatch = session.client("cloudwatch", endpoint_url=aws_endpoint) if aws_endpoint else session.client("cloudwatch")
    for audit in audits:
        metric_data = [
            {"MetricName": "Sagas", "Value": count, "Unit": "Count", "Dimensions": [{"Name": "Environment", "Value": audit["environment"]}, {"Name": "State", "Value": state}]}
            for state, count in audit["counts_by_state"].items()
        ]
        metric_data.extend([
            {"MetricName": "InconsistentSagas", "Value": len(audit["inconsistent_sagas"]), "Unit": "Count", "Dimensions": [{"Name": "Environment", "Value": audit["environment"]}]},
            {"MetricName": "OrphanAuditComplete", "Value": int(audit["orphan_audit_complete"]), "Unit": "Count", "Dimensions": [{"Name": "Environment", "Value": audit["environment"]}]},
        ])
        if audit["orphan_audit_complete"]:
            metric_data.append({"MetricName": "OrphanServiceRecords", "Value": len(audit["orphan_service_records"]), "Unit": "Count", "Dimensions": [{"Name": "Environment", "Value": audit["environment"]}]})
        for offset in range(0, len(metric_data), 20):
            cloudwatch.put_metric_data(Namespace="AegisVolt/SAGA", MetricData=metric_data[offset:offset + 20])


@flow(name="AegisVolt environment audit")
def audit() -> dict:
    config = load_environment_config(os.getenv("AEGISVOLT_AUDIT_ENVIRONMENTS_JSON", ""))
    region = os.getenv("AWS_DEFAULT_REGION", "").strip()
    if not region:
        raise ValueError("AWS_DEFAULT_REGION is required for the AegisVolt environment audit.")
    try:
        stale_after_seconds = int(os.getenv("SAGA_STALE_AFTER_SECONDS", str(DEFAULT_STALE_AFTER_SECONDS)))
    except ValueError as error:
        raise ValueError("SAGA_STALE_AFTER_SECONDS must be a positive integer.") from error
    if stale_after_seconds <= 0:
        raise ValueError("SAGA_STALE_AFTER_SECONDS must be a positive integer.")
    orphan_scan_value = os.getenv("SAGA_FULL_ORPHAN_SCAN_ENABLED", "false").strip().lower()
    if orphan_scan_value not in {"true", "false"}:
        raise ValueError("SAGA_FULL_ORPHAN_SCAN_ENABLED must be true or false.")
    full_orphan_scan = orphan_scan_value == "true"
    health = check_environment_health(config)
    endpoint = os.getenv("AWS_ENDPOINT_URL")
    audits = [
        audit_environment_sagas(environment, values["tables"], endpoint, region, stale_after_seconds, full_orphan_scan)
        for environment, values in config.items()
    ]
    publish_metrics(audits, region, endpoint)
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "health": health, "sagas": audits}
