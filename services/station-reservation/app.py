import hashlib
import json
import os
from datetime import datetime, timezone

from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from common.dynamodb import dynamodb_resource, ensure_table
from common.environment import environment_table_name

app = FastAPI(title="AegisVolt Station Reservation")
TABLE = environment_table_name("stations")
table = dynamodb_resource().Table(TABLE)

STATIONS = (
    {
        "id": "st-1",
        "name": "North Hall",
        "latitude": 40.71,
        "longitude": -74.01,
        "connectors": ({"id": "c-1", "type": "CCS", "power_kw": 150.0},),
    },
)


class Reservation(BaseModel):
    station_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    wallet_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reservation_id(idempotency_key: str) -> str:
    return f"reservation-{idempotency_key}"


def _connector_id(station_id: str, connector_id: str) -> str:
    return f"connector-{station_id}-{connector_id}"


def _fingerprint(reservation: Reservation) -> str:
    payload = json.dumps(
        {
            "station_id": reservation.station_id,
            "connector_id": reservation.connector_id,
            "wallet_id": reservation.wallet_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _get_reservation(reservation_id: str) -> dict | None:
    return table.get_item(
        Key={"id": reservation_id},
        ConsistentRead=True,
    ).get("Item")


def _matching_reservation(reservation: Reservation) -> dict | None:
    existing = _get_reservation(_reservation_id(reservation.idempotency_key))
    if not existing:
        return None
    if existing.get("request_fingerprint") != _fingerprint(reservation):
        raise HTTPException(409, "Idempotency key was already used for a different reservation")
    return existing


@app.on_event("startup")
async def startup():
    global table
    table = ensure_table(TABLE)


@app.get("/health")
def health():
    return {"service": "station-reservation", "status": "ok"}


@app.get("/stations")
def stations():
    result = []
    for station in STATIONS:
        connectors = []
        for connector in station["connectors"]:
            lock = table.get_item(
                Key={"id": _connector_id(station["id"], connector["id"])},
                ConsistentRead=True,
            ).get("Item")
            status = "available"
            if lock and lock.get("status") != "available":
                status = "reserved"
            connectors.append({**connector, "status": status})
        result.append(
            {
                **{key: value for key, value in station.items() if key != "connectors"},
                "status": "available" if any(c["status"] == "available" for c in connectors) else "occupied",
                "connectors": connectors,
            }
        )
    return result


@app.post("/reservations")
def reserve(reservation: Reservation):
    station = next((item for item in STATIONS if item["id"] == reservation.station_id), None)
    if station is None:
        raise HTTPException(404, "Station not found")
    if not any(item["id"] == reservation.connector_id for item in station["connectors"]):
        raise HTTPException(404, "Connector not found")

    reservation_id = _reservation_id(reservation.idempotency_key)
    connector_lock_id = _connector_id(reservation.station_id, reservation.connector_id)
    fingerprint = _fingerprint(reservation)
    timestamp = _now()
    existing = _matching_reservation(reservation)
    if existing:
        if existing.get("status") in {"reserved", "cancelled"}:
            return existing
        if existing.get("status") == "failed":
            raise HTTPException(409, existing.get("failure_reason", "Reservation failed"))
        if existing.get("status") != "reserving":
            raise HTTPException(409, "Reservation is not in a reservable state")
    else:
        item = {
            "id": reservation_id,
            "record_type": "reservation",
            "station_id": reservation.station_id,
            "connector_id": reservation.connector_id,
            "wallet_id": reservation.wallet_id,
            "idempotency_key": reservation.idempotency_key,
            "request_fingerprint": fingerprint,
            "status": "reserving",
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        try:
            table.put_item(Item=item, ConditionExpression="attribute_not_exists(id)")
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
            existing = _matching_reservation(reservation)
            if not existing:
                raise HTTPException(503, "Reservation outcome is uncertain; retry with the same idempotency key")
            if existing.get("status") in {"reserved", "cancelled"}:
                return existing
            if existing.get("status") == "failed":
                raise HTTPException(409, existing.get("failure_reason", "Reservation failed"))

    lock_item = {
        "id": connector_lock_id,
        "record_type": "connector_lock",
        "station_id": reservation.station_id,
        "connector_id": reservation.connector_id,
        "reservation_id": reservation_id,
        "status": "reserved",
        "updated_at": timestamp,
    }
    try:
        table.put_item(
            Item=lock_item,
            ConditionExpression="attribute_not_exists(id) OR #status = :available",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":available": "available"},
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        lock = table.get_item(
            Key={"id": connector_lock_id},
            ConsistentRead=True,
        ).get("Item")
        if not lock or lock.get("reservation_id") != reservation_id:
            reason = "Connector is already reserved"
            table.update_item(
                Key={"id": reservation_id},
                UpdateExpression="SET #status = :failed, failure_reason = :reason, updated_at = :updated",
                ConditionExpression="#status = :reserving",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":reserving": "reserving",
                    ":failed": "failed",
                    ":reason": reason,
                    ":updated": _now(),
                },
            )
            raise HTTPException(409, reason)

    try:
        table.update_item(
            Key={"id": reservation_id},
            UpdateExpression="SET #status = :reserved, updated_at = :updated",
            ConditionExpression="#status = :reserving AND request_fingerprint = :fingerprint",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":reserving": "reserving",
                ":reserved": "reserved",
                ":fingerprint": fingerprint,
                ":updated": _now(),
            },
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        current = _get_reservation(reservation_id)
        if current and current.get("status") == "reserved":
            return current
        raise HTTPException(503, "Reservation outcome is uncertain; retry with the same idempotency key")
    return _get_reservation(reservation_id)


@app.post("/reservations/{reservation_id}/cancel")
def cancel(reservation_id: str):
    normalized_id = (
        reservation_id
        if reservation_id.startswith("reservation-")
        else f"reservation-{reservation_id}"
    )
    reservation = _get_reservation(normalized_id)
    if not reservation:
        raise HTTPException(404, "Reservation not found")
    if reservation.get("status") == "cancelled":
        return reservation
    if reservation.get("status") not in {"reserved", "cancelling"}:
        raise HTTPException(409, "Reservation is not releasable")

    try:
        table.update_item(
            Key={"id": normalized_id},
            UpdateExpression="SET #status = :cancelling, updated_at = :updated",
            ConditionExpression="#status = :reserved",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":reserved": "reserved",
                ":cancelling": "cancelling",
                ":updated": _now(),
            },
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        current = _get_reservation(normalized_id)
        if current and current.get("status") == "cancelled":
            return current
        if not current or current.get("status") != "cancelling":
            raise HTTPException(409, "Reservation changed before it could be released")
        reservation = current

    connector_lock_id = _connector_id(reservation["station_id"], reservation["connector_id"])
    lock = table.get_item(
        Key={"id": connector_lock_id},
        ConsistentRead=True,
    ).get("Item")
    if lock and lock.get("reservation_id") == normalized_id and lock.get("status") == "reserved":
        try:
            table.update_item(
                Key={"id": connector_lock_id},
                UpdateExpression="SET #status = :available, updated_at = :updated REMOVE reservation_id",
                ConditionExpression="#status = :reserved AND reservation_id = :reservation",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":reserved": "reserved",
                    ":available": "available",
                    ":reservation": normalized_id,
                    ":updated": _now(),
                },
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
            current_lock = table.get_item(
                Key={"id": connector_lock_id},
                ConsistentRead=True,
            ).get("Item")
            if current_lock and current_lock.get("reservation_id") == normalized_id:
                raise HTTPException(503, "Connector release outcome is uncertain; retry cancellation")

    try:
        table.update_item(
            Key={"id": normalized_id},
            UpdateExpression="SET #status = :cancelled, updated_at = :updated",
            ConditionExpression="#status = :cancelling",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":cancelling": "cancelling",
                ":cancelled": "cancelled",
                ":updated": _now(),
            },
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        current = _get_reservation(normalized_id)
        if current and current.get("status") == "cancelled":
            return current
        raise HTTPException(503, "Reservation cancellation outcome is uncertain; retry cancellation")
    return _get_reservation(normalized_id)
