import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import httpx
import strawberry
from botocore.exceptions import ClientError
from fastapi import FastAPI
from graphql import GraphQLError
from strawberry.fastapi import GraphQLRouter

from common.dynamodb import dynamodb_resource, ensure_table
from common.environment import current_environment, environment_table_name
from common.feature_flags import load_feature_flags
from common.observability import current_correlation_id, install_request_logging

STATION_URL = os.getenv("STATION_URL", "http://localhost:8001")
BILLING_URL = os.getenv("BILLING_URL", "http://localhost:8002")
DISPATCH_URL = os.getenv("DISPATCH_URL", "http://localhost:8003")
ENVIRONMENT = current_environment()
SAGA_TABLE = environment_table_name("sagas", "SAGA_TABLE")
SAGA_LEASE_SECONDS = 120
TERMINAL_STATES = {"COMPLETED", "COMPENSATED", "FAILED"}

app = FastAPI(title="AegisVolt GraphQL Gateway")
install_request_logging(app, "gateway")
saga_table = ensure_table(SAGA_TABLE)


@strawberry.type
class Connector:
    id: str
    type: str
    status: str
    power_kw: float


@strawberry.type
class Station:
    id: str
    name: str
    status: str
    latitude: float
    longitude: float
    connectors: Optional[list[Connector]]


@strawberry.type
class Telemetry:
    station_id: str
    connector_id: str
    power_kw: float
    energy_kwh: float
    state: str


@strawberry.type
class Wallet:
    id: str
    balance: float
    currency: str


@strawberry.type
class FeatureFlag:
    name: str
    enabled: bool


@strawberry.type
class Saga:
    id: str
    correlation_id: str
    state: str
    reservation_status: str
    charge_status: str
    activation_status: str
    error: Optional[str]


@strawberry.type
class ChargeResult:
    success: bool
    saga_id: str
    correlation_id: str
    state: str
    message: str


@strawberry.type
class Dashboard:
    environment: str
    services_ok: bool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fingerprint(
    wallet_id: str,
    station_id: str,
    connector_id: str,
    amount: Decimal,
    fault: bool,
) -> str:
    payload = json.dumps(
        {
            "wallet_id": wallet_id,
            "station_id": station_id,
            "connector_id": connector_id,
            "amount": format(amount.normalize(), "f"),
            "fault": fault,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_saga(saga_id: str) -> dict | None:
    return saga_table.get_item(
        Key={"id": saga_id},
        ConsistentRead=True,
    ).get("Item")


def _append_event(saga: dict, step: str, outcome: str, detail: str = "") -> None:
    saga.setdefault("events", []).append(
        {
            "step": step,
            "outcome": outcome,
            "detail": detail,
            "occurred_at": _now(),
        }
    )


def persist(saga: dict, execution_token: str) -> None:
    saga["updated_at"] = _now()
    saga_table.put_item(
        Item=saga,
        ConditionExpression="execution_token = :token",
        ExpressionAttributeValues={":token": execution_token},
    )


def _release_execution(saga_id: str, execution_token: str) -> None:
    try:
        saga_table.update_item(
            Key={"id": saga_id},
            UpdateExpression="REMOVE execution_token, lease_expires_at",
            ConditionExpression="execution_token = :token",
            ExpressionAttributeValues={":token": execution_token},
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise


def _claim_execution(
    saga_id: str,
    request_fingerprint: str,
    wallet_id: str,
    station_id: str,
    connector_id: str,
    amount: Decimal,
    idempotency_key: str,
    correlation_id: str,
    fault: bool,
) -> tuple[dict, str | None, bool]:
    token = str(uuid.uuid4())
    now = int(time.time())
    saga = get_saga(saga_id)
    if saga:
        if saga.get("request_fingerprint") != request_fingerprint:
            raise GraphQLError("Idempotency key was already used for a different request")
        if saga.get("state") in TERMINAL_STATES or saga.get("state") == "COMPENSATION_FAILED":
            return saga, None, False
        if saga.get("state") == "COMPENSATING":
            return saga, None, False
        if saga.get("lease_expires_at", 0) > now:
            return saga, None, False
    else:
        saga = {
            "id": saga_id,
            "correlation_id": correlation_id,
            "request_fingerprint": request_fingerprint,
            "idempotency_key": idempotency_key,
            "state": "STARTED",
            "reservation_status": "pending",
            "charge_status": "pending",
            "activation_status": "pending",
            "error": "",
            "original_error": "",
            "wallet_id": wallet_id,
            "station_id": station_id,
            "connector_id": connector_id,
            "amount": amount,
            "fault": fault,
            "pending_compensations": [],
            "events": [],
            "created_at": _now(),
            "updated_at": _now(),
            "execution_token": token,
            "lease_expires_at": now + SAGA_LEASE_SECONDS,
        }
        _append_event(saga, "saga", "started")
        try:
            saga_table.put_item(
                Item=saga,
                ConditionExpression="attribute_not_exists(id)",
            )
            return saga, token, True
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
            saga = get_saga(saga_id)
            if not saga:
                raise
            if saga.get("request_fingerprint") != request_fingerprint:
                raise GraphQLError("Idempotency key was already used for a different request")
            if saga.get("state") in TERMINAL_STATES or saga.get("state") == "COMPENSATION_FAILED":
                return saga, None, False
            if saga.get("state") == "COMPENSATING":
                return saga, None, False
            if saga.get("lease_expires_at", 0) > now:
                return saga, None, False

    try:
        saga_table.update_item(
            Key={"id": saga_id},
            UpdateExpression="SET execution_token = :token, lease_expires_at = :expiry",
            ConditionExpression=(
                "attribute_exists(id) AND "
                "(attribute_not_exists(execution_token) OR lease_expires_at <= :now)"
            ),
            ExpressionAttributeValues={
                ":token": token,
                ":expiry": now + SAGA_LEASE_SECONDS,
                ":now": now,
            },
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        current = get_saga(saga_id)
        if not current:
            raise
        return current, None, False
    claimed = get_saga(saga_id)
    if not claimed:
        raise RuntimeError(f"SAGA {saga_id} disappeared after execution claim")
    return claimed, token, True


async def _post_idempotent(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
) -> httpx.Response:
    for attempt in range(2):
        try:
            correlation_id = payload.get("correlation_id")
            headers = {"X-Correlation-ID": correlation_id} if correlation_id else {}
            response = await client.post(url, json=payload, headers=headers)
        except httpx.TransportError:
            if attempt == 0:
                continue
            raise
        if response.status_code in {500, 502, 503, 504} and attempt == 0:
            continue
        response.raise_for_status()
        return response
    raise RuntimeError("Idempotent request retry loop exited unexpectedly")


def _is_uncertain(error: httpx.HTTPError) -> bool:
    if isinstance(error, httpx.TransportError):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code >= 500
    return True


async def compensate(
    saga: dict,
    client: httpx.AsyncClient,
    execution_token: str,
) -> dict:
    saga["state"] = "COMPENSATING"
    saga["pending_compensations"] = []
    _append_event(saga, "compensation", "started")
    persist(saga, execution_token)

    if saga.get("charge_id") and saga.get("charge_status") != "refunded":
        saga["pending_compensations"] = ["refund", "release_reservation"]
        _append_event(saga, "refund", "started")
        persist(saga, execution_token)
        try:
            response = await _post_idempotent(
                client,
                f"{BILLING_URL}/charges/{saga['charge_id']}/refund",
                {"correlation_id": saga["correlation_id"]},
            )
            result = response.json()
            if result.get("status") != "refunded":
                raise RuntimeError("Billing service did not confirm the refund")
        except (httpx.HTTPError, RuntimeError) as error:
            saga["state"] = "COMPENSATION_FAILED"
            saga["charge_status"] = "refund_failed"
            saga["pending_compensations"] = ["refund", "release_reservation"]
            saga["error"] = f"Refund failed: {error}"
            _append_event(saga, "refund", "failed", str(error))
            persist(saga, execution_token)
            return saga
        saga["charge_status"] = "refunded"
        saga["pending_compensations"] = ["release_reservation"]
        _append_event(saga, "refund", "succeeded")
        persist(saga, execution_token)

    if saga.get("reservation_id") and saga.get("reservation_status") != "cancelled":
        saga["pending_compensations"] = ["release_reservation"]
        _append_event(saga, "release_reservation", "started")
        persist(saga, execution_token)
        try:
            response = await _post_idempotent(
                client,
                f"{STATION_URL}/reservations/{saga['reservation_id']}/cancel",
                {"correlation_id": saga["correlation_id"]},
            )
            result = response.json()
            if result.get("status") != "cancelled":
                raise RuntimeError("Station service did not confirm reservation release")
        except (httpx.HTTPError, RuntimeError) as error:
            saga["state"] = "COMPENSATION_FAILED"
            saga["reservation_status"] = "release_failed"
            saga["pending_compensations"] = ["release_reservation"]
            saga["error"] = f"Reservation release failed: {error}"
            _append_event(saga, "release_reservation", "failed", str(error))
            persist(saga, execution_token)
            return saga
        saga["reservation_status"] = "cancelled"
        saga["pending_compensations"] = []
        _append_event(saga, "release_reservation", "succeeded")
        persist(saga, execution_token)

    saga["state"] = "COMPENSATED"
    saga["pending_compensations"] = []
    saga["error"] = saga.get("original_error", "")
    _append_event(saga, "compensation", "succeeded")
    persist(saga, execution_token)
    return saga


async def execute_saga(
    wallet_id: str,
    station_id: str,
    connector_id: str,
    amount: float,
    idempotency_key: str,
    correlation_id: str,
    fault: bool = False,
) -> dict:
    if not idempotency_key.strip():
        raise GraphQLError("idempotencyKey must not be empty")
    decimal_amount = Decimal(str(amount))
    if not decimal_amount.is_finite() or decimal_amount <= 0:
        raise GraphQLError("amount must be a positive finite number")

    saga_id = f"saga-{idempotency_key}"
    fingerprint = _fingerprint(
        wallet_id,
        station_id,
        connector_id,
        decimal_amount,
        fault,
    )
    saga, execution_token, claimed = _claim_execution(
        saga_id,
        fingerprint,
        wallet_id,
        station_id,
        connector_id,
        decimal_amount,
        idempotency_key,
        correlation_id,
        fault,
    )
    if not claimed or execution_token is None:
        return saga

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            if not saga.get("reservation_id"):
                saga["state"] = "RESERVING"
                _append_event(saga, "reservation", "started")
                persist(saga, execution_token)
                try:
                    response = await _post_idempotent(
                        client,
                        f"{STATION_URL}/reservations",
                        {
                            "station_id": station_id,
                            "connector_id": connector_id,
                            "wallet_id": wallet_id,
                            "idempotency_key": idempotency_key,
                            "correlation_id": saga["correlation_id"],
                        },
                    )
                    reserved = response.json()
                    if reserved.get("status") != "reserved":
                        raise RuntimeError("Station service did not confirm reservation")
                except (httpx.HTTPError, RuntimeError) as error:
                    uncertain = isinstance(error, httpx.HTTPError) and _is_uncertain(error)
                    saga["state"] = "RESERVATION_UNCERTAIN" if uncertain else "FAILED"
                    saga["reservation_status"] = "uncertain" if uncertain else "failed"
                    saga["error"] = str(error)
                    _append_event(saga, "reservation", "uncertain" if uncertain else "failed", str(error))
                    persist(saga, execution_token)
                    return saga
                saga["reservation_id"] = reserved["id"]
                saga["reservation_status"] = "reserved"
                saga["state"] = "RESERVATION_COMPLETED"
                _append_event(saga, "reservation", "succeeded")
                persist(saga, execution_token)

            if saga.get("charge_status") not in {"charged", "failed", "refunded"}:
                saga["state"] = "CHARGING"
                _append_event(saga, "charge", "started")
                persist(saga, execution_token)
                try:
                    response = await _post_idempotent(
                        client,
                        f"{BILLING_URL}/charges",
                        {
                            "wallet_id": wallet_id,
                            "amount": float(decimal_amount),
                            "idempotency_key": idempotency_key,
                            "correlation_id": saga["correlation_id"],
                        },
                    )
                    charged = response.json()
                    if charged.get("status") != "charged":
                        raise RuntimeError("Billing service did not confirm the charge")
                except httpx.HTTPError as error:
                    status_code = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
                    if status_code == 402:
                        saga["charge_status"] = "failed"
                        saga["state"] = "CHARGE_FAILED"
                        saga["original_error"] = "Insufficient funds"
                        saga["error"] = "Insufficient funds"
                        _append_event(saga, "charge", "insufficient_funds", str(error))
                        persist(saga, execution_token)
                        return await compensate(saga, client, execution_token)
                    if _is_uncertain(error):
                        saga["charge_status"] = "uncertain"
                        saga["state"] = "CHARGE_UNCERTAIN"
                        saga["error"] = str(error)
                        _append_event(saga, "charge", "uncertain", str(error))
                        persist(saga, execution_token)
                        return saga
                    saga["charge_status"] = "failed"
                    saga["state"] = "CHARGE_FAILED"
                    saga["original_error"] = str(error)
                    saga["error"] = str(error)
                    _append_event(saga, "charge", "failed", str(error))
                    persist(saga, execution_token)
                    return await compensate(saga, client, execution_token)
                except RuntimeError as error:
                    saga["charge_status"] = "uncertain"
                    saga["state"] = "CHARGE_UNCERTAIN"
                    saga["error"] = str(error)
                    _append_event(saga, "charge", "uncertain", str(error))
                    persist(saga, execution_token)
                    return saga
                saga["charge_id"] = charged["id"]
                saga["charge_status"] = "charged"
                saga["state"] = "CHARGE_COMPLETED"
                saga["error"] = ""
                _append_event(saga, "charge", "succeeded")
                persist(saga, execution_token)

            if (
                saga.get("charge_status") in {"failed", "refunded"}
                or saga.get("activation_status") == "failed"
            ):
                return await compensate(saga, client, execution_token)

            if saga.get("activation_status") not in {"active", "failed"}:
                saga["state"] = "ACTIVATING"
                _append_event(saga, "activation", "started")
                persist(saga, execution_token)
                try:
                    response = await _post_idempotent(
                        client,
                        f"{DISPATCH_URL}/activations",
                        {
                            "reservation_id": saga["reservation_id"],
                            "station_id": station_id,
                            "connector_id": connector_id,
                            "idempotency_key": idempotency_key,
                            "correlation_id": saga["correlation_id"],
                            "fault": fault,
                        },
                    )
                    activated = response.json()
                    if activated.get("status") != "active":
                        raise RuntimeError("Dispatch service did not confirm activation")
                except httpx.HTTPError as error:
                    if _is_uncertain(error):
                        saga["activation_status"] = "uncertain"
                        saga["state"] = "ACTIVATION_UNCERTAIN"
                        saga["error"] = str(error)
                        _append_event(saga, "activation", "uncertain", str(error))
                        persist(saga, execution_token)
                        return saga
                    saga["activation_status"] = "failed"
                    saga["original_error"] = str(error)
                    saga["error"] = str(error)
                    _append_event(saga, "activation", "failed", str(error))
                    persist(saga, execution_token)
                    return await compensate(saga, client, execution_token)
                except RuntimeError as error:
                    saga["activation_status"] = "uncertain"
                    saga["state"] = "ACTIVATION_UNCERTAIN"
                    saga["error"] = str(error)
                    _append_event(saga, "activation", "uncertain", str(error))
                    persist(saga, execution_token)
                    return saga
                saga["activation_id"] = activated["id"]
                saga["activation_status"] = "active"
                saga["state"] = "COMPLETED"
                saga["error"] = ""
                _append_event(saga, "activation", "succeeded")
                persist(saga, execution_token)
        return saga
    finally:
        _release_execution(saga_id, execution_token)


@strawberry.type
class Query:
    @strawberry.field
    async def dashboard(self) -> Dashboard:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{STATION_URL}/health")
            response.raise_for_status()
            health = response.json()
        return Dashboard(
            environment=ENVIRONMENT,
            services_ok=health.get("status") == "ok",
        )

    @strawberry.field
    async def stations(self) -> list[Station]:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{STATION_URL}/stations")
            response.raise_for_status()
            data = response.json()
        return [
            Station(
                id=item["id"],
                name=item["name"],
                status=item["status"],
                latitude=item["latitude"],
                longitude=item["longitude"],
                connectors=[
                    Connector(
                        id=connector["id"],
                        type=connector["type"],
                        status=connector["status"],
                        power_kw=connector["power_kw"],
                    )
                    for connector in item.get("connectors", [])
                ],
            )
            for item in data
        ]

    @strawberry.field
    async def telemetry(self) -> list[Telemetry]:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{DISPATCH_URL}/telemetry")
            response.raise_for_status()
            data = response.json()
        return [Telemetry(**item) for item in data]

    @strawberry.field
    async def wallet(self, wallet_id: str) -> Wallet:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{BILLING_URL}/wallets/{wallet_id}")
            response.raise_for_status()
            item = response.json()
        return Wallet(id=item["id"], balance=float(item["balance"]), currency=item["currency"])

    @strawberry.field
    def flags(self) -> list[FeatureFlag]:
        return [
            FeatureFlag(name=name, enabled=enabled)
            for name, enabled in load_feature_flags().items()
        ]

    @strawberry.field
    def sagas(self) -> list[Saga]:
        items = saga_table.scan(Limit=100).get("Items", [])
        return [
            Saga(
                id=item["id"],
                correlation_id=item["correlation_id"],
                state=item["state"],
                reservation_status=item["reservation_status"],
                charge_status=item["charge_status"],
                activation_status=item["activation_status"],
                error=item.get("error") or None,
            )
            for item in items
        ]


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def reserve_and_activate_charge(
        self,
        wallet_id: str,
        station_id: str,
        connector_id: str,
        amount: float,
        idempotency_key: str,
        charge_fault: bool = False,
    ) -> ChargeResult:
        flags = load_feature_flags()
        effective_fault = charge_fault and flags["SIMULATE_CHARGER_HARDWARE_FAULT"]
        saga = await execute_saga(
            wallet_id,
            station_id,
            connector_id,
            amount,
            idempotency_key,
            current_correlation_id() or str(uuid.uuid4()),
            effective_fault,
        )
        return ChargeResult(
            success=saga["state"] == "COMPLETED",
            saga_id=saga["id"],
            correlation_id=saga["correlation_id"],
            state=saga["state"],
            message=saga.get("error", ""),
        )

    @strawberry.mutation
    async def stop_and_release(self, saga_id: str) -> Saga:
        saga = get_saga(saga_id)
        if not saga:
            raise GraphQLError("SAGA not found")

        if saga.get("state") not in {"COMPLETED", "STOPPED"}:
            raise GraphQLError("SAGA is not in a stoppable state")
        if saga.get("state") == "STOPPED":
            return Saga(
                id=saga["id"],
                correlation_id=saga["correlation_id"],
                state=saga["state"],
                reservation_status=saga["reservation_status"],
                charge_status=saga["charge_status"],
                activation_status=saga["activation_status"],
                error=saga.get("error") or None,
            )

        activation_id = saga.get("activation_id")
        reservation_id = saga.get("reservation_id")
        if not activation_id or not reservation_id:
            raise GraphQLError("SAGA is missing activation or reservation state")

        async with httpx.AsyncClient(timeout=5) as client:
            activation_response = await client.post(
                f"{DISPATCH_URL}/activations/{activation_id}/stop",
                headers={"X-Correlation-ID": saga["correlation_id"]},
            )
            if activation_response.status_code >= 400:
                raise GraphQLError(
                    f"Could not stop activation: HTTP {activation_response.status_code}"
                )

            reservation_response = await client.post(
                f"{STATION_URL}/reservations/{reservation_id}/cancel",
                headers={"X-Correlation-ID": saga["correlation_id"]},
            )
            if reservation_response.status_code >= 400:
                raise GraphQLError(
                    f"Activation stopped, but could not release reservation: "
                    f"HTTP {reservation_response.status_code}"
                )

        current = get_saga(saga_id)
        if not current:
            raise RuntimeError(f"SAGA {saga_id} disappeared while stopping")
        now = _now()
        try:
            saga_table.update_item(
                Key={"id": saga_id},
                UpdateExpression=(
                    "SET #state = :stopped, activation_status = :activation, "
                    "reservation_status = :reservation, updated_at = :updated"
                ),
                ExpressionAttributeNames={"#state": "state"},
                ExpressionAttributeValues={
                    ":stopped": "STOPPED",
                    ":activation": "stopped",
                    ":reservation": "cancelled",
                    ":updated": now,
                },
            )
        except ClientError as error:
            raise RuntimeError(f"Could not persist stopped SAGA state: {error}") from error

        current = get_saga(saga_id)
        return Saga(
            id=current["id"],
            correlation_id=current["correlation_id"],
            state=current["state"],
            reservation_status=current["reservation_status"],
            charge_status=current["charge_status"],
            activation_status=current["activation_status"],
            error=current.get("error") or None,
        )

    @strawberry.mutation
    async def retry_compensation(self, saga_id: str) -> Saga:
        saga = get_saga(saga_id)
        if not saga:
            raise GraphQLError("SAGA not found")
        if saga.get("state") == "COMPENSATED":
            return Saga(
                id=saga["id"],
                correlation_id=saga["correlation_id"],
                state=saga["state"],
                reservation_status=saga["reservation_status"],
                charge_status=saga["charge_status"],
                activation_status=saga["activation_status"],
                error=saga.get("error") or None,
            )
        if saga.get("state") != "COMPENSATION_FAILED":
            raise GraphQLError("SAGA is not eligible for compensation retry")

        token = str(uuid.uuid4())
        now = int(time.time())
        event = {
            "step": "compensation_retry",
            "outcome": "started",
            "detail": "",
            "occurred_at": _now(),
        }
        try:
            saga_table.update_item(
                Key={"id": saga_id},
                UpdateExpression=(
                    "SET #state = :compensating, execution_token = :token, "
                    "lease_expires_at = :expiry, events = list_append(if_not_exists(events, :empty), :event)"
                ),
                ConditionExpression=(
                    "(#state = :failed OR #state = :compensating) AND "
                    "(attribute_not_exists(execution_token) OR lease_expires_at <= :now)"
                ),
                ExpressionAttributeNames={"#state": "state"},
                ExpressionAttributeValues={
                    ":compensating": "COMPENSATING",
                    ":failed": "COMPENSATION_FAILED",
                    ":token": token,
                    ":expiry": now + SAGA_LEASE_SECONDS,
                    ":now": now,
                    ":empty": [],
                    ":event": [event],
                },
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
            current = get_saga(saga_id)
            if current and current.get("state") == "COMPENSATED":
                saga = current
            elif current and current.get("state") in {"COMPENSATION_FAILED", "COMPENSATING"}:
                raise GraphQLError("SAGA compensation is already being retried")
            else:
                raise GraphQLError("SAGA is not eligible for compensation retry")
        else:
            saga = get_saga(saga_id)
            if not saga:
                raise RuntimeError(f"SAGA {saga_id} disappeared after compensation claim")
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    saga = await compensate(saga, client, token)
            finally:
                _release_execution(saga_id, token)

        return Saga(
            id=saga["id"],
            correlation_id=saga["correlation_id"],
            state=saga["state"],
            reservation_status=saga["reservation_status"],
            charge_status=saga["charge_status"],
            activation_status=saga["activation_status"],
            error=saga.get("error") or None,
        )


schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema)


@app.get("/health")
async def health():
    """Process health for Kubernetes and the internal ALB target group."""
    return {"status": "ok"}


app.include_router(graphql_app, prefix="/graphql")
