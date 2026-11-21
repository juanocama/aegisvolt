import hashlib
import json
import os
from decimal import Decimal

from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from common.dynamodb import dynamodb_client, dynamodb_resource, ensure_table
from common.environment import environment_table_name

app = FastAPI(title="AegisVolt Energy Dispatch")
TABLE = environment_table_name("dispatch")
table = dynamodb_resource().Table(TABLE)
dynamodb = dynamodb_client()


class Activation(BaseModel):
    reservation_id: str = Field(min_length=1)
    station_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    fault: bool = False


def _activation_id(idempotency_key: str) -> str:
    return f"activation-{idempotency_key}"


def _telemetry_id(activation_id: str) -> str:
    return f"telemetry-{activation_id}"


def _fingerprint(payload: Activation) -> str:
    request = json.dumps(
        {
            "reservation_id": payload.reservation_id,
            "station_id": payload.station_id,
            "connector_id": payload.connector_id,
            "fault": payload.fault,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(request.encode("utf-8")).hexdigest()


def _get_item(item_id: str) -> dict | None:
    return table.get_item(
        Key={"id": item_id},
        ConsistentRead=True,
    ).get("Item")


def _existing_activation(payload: Activation) -> dict | None:
    existing = _get_item(_activation_id(payload.idempotency_key))
    if not existing:
        return None
    if existing.get("request_fingerprint") != _fingerprint(payload):
        raise HTTPException(409, "Idempotency key was already used for a different activation")
    if existing.get("status") == "failed":
        raise HTTPException(409, existing.get("error", "Charger activation failed"))
    return existing


@app.on_event("startup")
async def startup():
    global table
    table = ensure_table(TABLE)


@app.get("/health")
def health():
    return {"service": "energy-dispatch", "status": "ok"}


@app.get("/telemetry")
def telemetry():
    response = table.scan(
        Limit=100,
        FilterExpression=Attr("record_type").eq("telemetry"),
    )
    items = response.get("Items", [])
    if not items:
        return [
            {
                "station_id": "st-1",
                "connector_id": "c-1",
                "power_kw": 72.5,
                "energy_kwh": 4.2,
                "state": "idle",
            }
        ]
    return [
        {
            "station_id": item["station_id"],
            "connector_id": item["connector_id"],
            "power_kw": float(item["power_kw"]),
            "energy_kwh": float(item["energy_kwh"]),
            "state": item["state"],
        }
        for item in items
    ]


@app.post("/activations")
def activate(payload: Activation):
    existing = _existing_activation(payload)
    if existing:
        return existing

    activation_id = _activation_id(payload.idempotency_key)
    fingerprint = _fingerprint(payload)
    activation = {
        "id": activation_id,
        "record_type": "activation",
        "reservation_id": payload.reservation_id,
        "station_id": payload.station_id,
        "connector_id": payload.connector_id,
        "correlation_id": payload.correlation_id,
        "request_fingerprint": fingerprint,
        "status": "failed" if payload.fault else "active",
    }

    if payload.fault:
        activation["error"] = "Simulated charger hardware fault"
        try:
            table.put_item(
                Item=activation,
                ConditionExpression="attribute_not_exists(id)",
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
            existing = _existing_activation(payload)
            if existing:
                return existing
        raise HTTPException(409, activation["error"])

    telemetry_item = {
        "id": _telemetry_id(activation_id),
        "record_type": "telemetry",
        "station_id": payload.station_id,
        "connector_id": payload.connector_id,
        "activation_id": activation_id,
        "power_kw": Decimal("0"),
        "energy_kwh": Decimal("0"),
        "state": "active",
    }
    try:
        dynamodb.transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": TABLE,
                        "Key": {"id": {"S": activation_id}},
                        "UpdateExpression": (
                            "SET record_type = :type, reservation_id = :reservation, "
                            "station_id = :station, connector_id = :connector, "
                            "correlation_id = :correlation, request_fingerprint = :fingerprint, "
                            "#status = :status"
                        ),
                        "ConditionExpression": "attribute_not_exists(id)",
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": {
                            ":type": {"S": activation["record_type"]},
                            ":reservation": {"S": activation["reservation_id"]},
                            ":station": {"S": activation["station_id"]},
                            ":connector": {"S": activation["connector_id"]},
                            ":correlation": {"S": activation["correlation_id"]},
                            ":fingerprint": {"S": activation["request_fingerprint"]},
                            ":status": {"S": activation["status"]},
                        },
                    }
                },
                {
                    "Update": {
                        "TableName": TABLE,
                        "Key": {"id": {"S": telemetry_item["id"]}},
                        "UpdateExpression": (
                            "SET record_type = :type, station_id = :station, "
                            "connector_id = :connector, activation_id = :activation, "
                            "power_kw = :power, energy_kwh = :energy, #state = :state"
                        ),
                        "ConditionExpression": "attribute_not_exists(id)",
                        "ExpressionAttributeNames": {"#state": "state"},
                        "ExpressionAttributeValues": {
                            ":type": {"S": telemetry_item["record_type"]},
                            ":station": {"S": telemetry_item["station_id"]},
                            ":connector": {"S": telemetry_item["connector_id"]},
                            ":activation": {"S": telemetry_item["activation_id"]},
                            ":power": {"N": "0"},
                            ":energy": {"N": "0"},
                            ":state": {"S": telemetry_item["state"]},
                        },
                    }
                },
            ]
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
            raise
        existing = _existing_activation(payload)
        if existing:
            return existing
        raise HTTPException(503, "Activation outcome is uncertain; retry with the same idempotency key")
    return activation


@app.post("/activations/{activation_id}/stop")
def stop(activation_id: str):
    normalized_id = (
        activation_id
        if activation_id.startswith("activation-")
        else f"activation-{activation_id}"
    )
    activation = _get_item(normalized_id)
    if not activation:
        raise HTTPException(404, "Activation not found")
    if activation.get("status") == "stopped":
        return activation
    if activation.get("status") != "active":
        raise HTTPException(409, "Activation is not active")

    telemetry_id = _telemetry_id(normalized_id)
    telemetry_item = _get_item(telemetry_id)
    try:
        if telemetry_item:
            dynamodb.transact_write_items(
                TransactItems=[
                    {
                        "Update": {
                            "TableName": TABLE,
                            "Key": {"id": {"S": normalized_id}},
                            "UpdateExpression": "SET #status = :stopped",
                            "ConditionExpression": "#status = :active",
                            "ExpressionAttributeNames": {"#status": "status"},
                            "ExpressionAttributeValues": {
                                ":active": {"S": "active"},
                                ":stopped": {"S": "stopped"},
                            },
                        }
                    },
                    {
                        "Update": {
                            "TableName": TABLE,
                            "Key": {"id": {"S": telemetry_id}},
                            "UpdateExpression": "SET #state = :stopped, power_kw = :zero",
                            "ConditionExpression": "#state = :active",
                            "ExpressionAttributeNames": {"#state": "state"},
                            "ExpressionAttributeValues": {
                                ":active": {"S": "active"},
                                ":stopped": {"S": "stopped"},
                                ":zero": {"N": "0"},
                            },
                        }
                    },
                ]
            )
        else:
            table.update_item(
                Key={"id": normalized_id},
                UpdateExpression="SET #status = :stopped",
                ConditionExpression="#status = :active",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":active": "active", ":stopped": "stopped"},
            )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
            raise
        current = _get_item(normalized_id)
        if current and current.get("status") == "stopped":
            return current
        raise HTTPException(409, "Activation changed before it could be stopped")

    return _get_item(normalized_id)
