import asyncio
import uuid

from fastapi.testclient import TestClient


CHARGE_MUTATION = """
mutation Charge(
  $walletId: String!,
  $stationId: String!,
  $connectorId: String!,
  $amount: Float!,
  $idempotencyKey: String!,
  $chargeFault: Boolean! = false
) {
  reserveAndActivateCharge(
    walletId: $walletId,
    stationId: $stationId,
    connectorId: $connectorId,
    amount: $amount,
    idempotencyKey: $idempotencyKey,
    chargeFault: $chargeFault
  ) {
    success
    sagaId
    correlationId
    state
    message
  }
}
"""

RETRY_MUTATION = """
mutation Retry($sagaId: String!) {
  retryCompensation(sagaId: $sagaId) {
    id
    state
    reservationStatus
    chargeStatus
    activationStatus
    error
  }
}
"""


def _key() -> str:
    return str(uuid.uuid4())


def _charge(client, wallet_id: str, idempotency_key: str, amount: float = 25.0, fault: bool = False):
    response = client.post(
        "/graphql",
        json={
            "query": CHARGE_MUTATION,
            "variables": {
                "walletId": wallet_id,
                "stationId": "st-1",
                "connectorId": "c-1",
                "amount": amount,
                "idempotencyKey": idempotency_key,
                "chargeFault": fault,
            },
        },
    )
    return response.json()


def _wallet(backend, wallet_id: str):
    return backend["billing"].wallet(wallet_id)


def _connector(backend):
    return backend["station"].stations()[0]["connectors"][0]["status"]


def test_successful_charging_workflow(backend):
    gateway = backend["gateway"]
    key = _key()
    wallet_id = f"wallet-{key}"

    with TestClient(gateway.app) as client:
        result = _charge(client, wallet_id, key)["data"]["reserveAndActivateCharge"]

    assert result["success"] is True
    assert result["state"] == "COMPLETED"
    assert _wallet(backend, wallet_id)["balance"] == 75
    assert _connector(backend) == "reserved"
    assert backend["dispatch"].telemetry()[0]["state"] == "active"

    saga = gateway.get_saga(result["sagaId"])
    assert [event["step"] for event in saga["events"] if event["outcome"] == "succeeded"] == [
        "reservation",
        "charge",
        "activation",
    ]
    backend["station"].cancel(saga["reservation_id"])


def test_insufficient_balance_releases_reservation(backend):
    gateway = backend["gateway"]
    key = _key()
    wallet_id = f"wallet-{key}"

    with TestClient(gateway.app) as client:
        result = _charge(client, wallet_id, key, amount=101)["data"]["reserveAndActivateCharge"]

    saga = gateway.get_saga(result["sagaId"])
    assert result["success"] is False
    assert result["state"] == "COMPENSATED"
    assert saga["charge_status"] == "failed"
    assert saga["reservation_status"] == "cancelled"
    assert "Insufficient funds" in result["message"]
    assert _wallet(backend, wallet_id)["balance"] == 100
    assert _connector(backend) == "available"


def test_official_hardware_fault_flag_compensates_successfully(backend, monkeypatch):
    gateway = backend["gateway"]
    monkeypatch.setenv("SIMULATE_CHARGER_HARDWARE_FAULT", "true")
    key = _key()
    wallet_id = f"wallet-{key}"

    with TestClient(gateway.app) as client:
        result = _charge(client, wallet_id, key, fault=True)["data"]["reserveAndActivateCharge"]

    saga = gateway.get_saga(result["sagaId"])
    activation = backend["dispatch"]._get_item(f"activation-{key}")
    assert result["state"] == "COMPENSATED"
    assert saga["charge_status"] == "refunded"
    assert saga["reservation_status"] == "cancelled"
    assert activation["status"] == "failed"
    assert _wallet(backend, wallet_id)["balance"] == 100
    assert _connector(backend) == "available"
    monkeypatch.setenv("SIMULATE_CHARGER_HARDWARE_FAULT", "false")


def test_enabled_fault_flag_alone_triggers_compensation(backend, monkeypatch):
    gateway = backend["gateway"]
    monkeypatch.setenv("SIMULATE_CHARGER_HARDWARE_FAULT", "true")
    key = _key()
    wallet_id = f"wallet-{key}"

    with TestClient(gateway.app) as client:
        result = _charge(client, wallet_id, key, fault=False)["data"]["reserveAndActivateCharge"]

    saga = gateway.get_saga(result["sagaId"])
    assert result["state"] == "COMPENSATED"
    assert saga["charge_status"] == "refunded"
    assert saga["reservation_status"] == "cancelled"
    assert _wallet(backend, wallet_id)["balance"] == 100
    assert _connector(backend) == "available"
    monkeypatch.setenv("SIMULATE_CHARGER_HARDWARE_FAULT", "false")


def test_failed_compensation_is_not_reported_success_and_can_be_retried(backend, monkeypatch):
    gateway = backend["gateway"]
    backend["behavior"]["fail_refund"] = True
    monkeypatch.setenv("SIMULATE_CHARGER_HARDWARE_FAULT", "true")
    key = _key()
    wallet_id = f"wallet-{key}"

    with TestClient(gateway.app) as client:
        result = _charge(client, wallet_id, key, fault=True)["data"]["reserveAndActivateCharge"]
        saga = gateway.get_saga(result["sagaId"])
        assert result["success"] is False
        assert result["state"] == "COMPENSATION_FAILED"
        assert saga["charge_status"] == "refund_failed"
        assert saga["reservation_status"] == "reserved"
        assert saga["pending_compensations"] == ["refund", "release_reservation"]
        assert _wallet(backend, wallet_id)["balance"] == 75
        assert _connector(backend) == "reserved"

        backend["behavior"]["fail_refund"] = False
        response = client.post(
            "/graphql",
            json={"query": RETRY_MUTATION, "variables": {"sagaId": result["sagaId"]}},
        ).json()

    retried = response["data"]["retryCompensation"]
    assert retried["state"] == "COMPENSATED"
    assert retried["chargeStatus"] == "refunded"
    assert retried["reservationStatus"] == "cancelled"
    assert _wallet(backend, wallet_id)["balance"] == 100
    assert _connector(backend) == "available"
    monkeypatch.setenv("SIMULATE_CHARGER_HARDWARE_FAULT", "false")


def test_duplicate_idempotency_request_does_not_repeat_effects(backend):
    gateway = backend["gateway"]
    key = _key()
    wallet_id = f"wallet-{key}"

    with TestClient(gateway.app) as client:
        first = _charge(client, wallet_id, key)["data"]["reserveAndActivateCharge"]
        second = _charge(client, wallet_id, key)["data"]["reserveAndActivateCharge"]
        conflict = _charge(client, wallet_id, key, amount=26)

    assert first["state"] == "COMPLETED"
    assert second == first
    assert conflict.get("errors")
    assert _wallet(backend, wallet_id)["balance"] == 75
    assert backend["billing"]._get_item(f"charge-{key}")["status"] == "charged"
    assert backend["dispatch"]._get_item(f"activation-{key}")["status"] == "active"
    backend["station"].cancel(f"reservation-{key}")


def test_concurrent_duplicate_saga_requests_share_one_execution(backend):
    gateway = backend["gateway"]
    key = _key()
    wallet_id = f"wallet-{key}"

    async def execute_twice():
        return await asyncio.gather(
            gateway.execute_saga(wallet_id, "st-1", "c-1", 25, key, "corr-a"),
            gateway.execute_saga(wallet_id, "st-1", "c-1", 25, key, "corr-b"),
        )

    returned = asyncio.run(execute_twice())
    saga = gateway.get_saga(f"saga-{key}")

    assert returned[0]["id"] == returned[1]["id"] == saga["id"]
    assert saga["state"] == "COMPLETED"
    assert _wallet(backend, wallet_id)["balance"] == 75
    assert sum(
        event["step"] == "charge" and event["outcome"] == "succeeded"
        for event in saga["events"]
    ) == 1
    backend["station"].cancel(f"reservation-{key}")


def test_uncertain_charge_response_is_retried_idempotently(backend):
    gateway = backend["gateway"]
    backend["behavior"]["lose_charge_response_count"] = 1
    key = _key()
    wallet_id = f"wallet-{key}"

    with TestClient(gateway.app) as client:
        result = _charge(client, wallet_id, key, fault=True)["data"]["reserveAndActivateCharge"]

    assert backend["behavior"]["charge_response_lost"] is True
    assert result["state"] == "COMPLETED"
    assert _wallet(backend, wallet_id)["balance"] == 75
    assert backend["billing"]._get_item(f"charge-{key}")["status"] == "charged"
    backend["station"].cancel(f"reservation-{key}")


def test_uncertain_charge_can_resume_with_same_idempotency_key(backend):
    gateway = backend["gateway"]
    backend["behavior"]["lose_charge_response_count"] = 2
    key = _key()
    wallet_id = f"wallet-{key}"

    with TestClient(gateway.app) as client:
        first = _charge(client, wallet_id, key)["data"]["reserveAndActivateCharge"]
        assert first["state"] == "CHARGE_UNCERTAIN"
        backend["behavior"]["lose_charge_response_count"] = 0
        retried = _charge(client, wallet_id, key)["data"]["reserveAndActivateCharge"]

    assert retried["success"] is True
    assert retried["state"] == "COMPLETED"
    assert _wallet(backend, wallet_id)["balance"] == 75
    assert backend["billing"]._get_item(f"charge-{key}")["status"] == "charged"
    backend["station"].cancel(f"reservation-{key}")


def test_feature_flags_use_official_names_and_fail_on_invalid_values(backend, monkeypatch):
    gateway = backend["gateway"]
    monkeypatch.setenv("ENABLE_DYNAMIC_SURGE_PRICING", "true")
    monkeypatch.setenv("ENABLE_FAST_CHARGE_BOOST", "false")
    monkeypatch.setenv("SIMULATE_CHARGER_HARDWARE_FAULT", "false")

    with TestClient(gateway.app) as client:
        flags = client.post("/graphql", json={"query": "{ flags { name enabled } }"}).json()
        assert flags["data"]["flags"] == [
            {"name": "ENABLE_DYNAMIC_SURGE_PRICING", "enabled": True},
            {"name": "ENABLE_FAST_CHARGE_BOOST", "enabled": False},
            {"name": "SIMULATE_CHARGER_HARDWARE_FAULT", "enabled": False},
        ]
        monkeypatch.setenv("ENABLE_FAST_CHARGE_BOOST", "sometimes")
        invalid = client.post("/graphql", json={"query": "{ flags { name enabled } }"}).json()

    assert invalid.get("errors")


def test_request_fault_input_cannot_inject_when_environment_flag_is_false(backend, monkeypatch):
    gateway = backend["gateway"]
    monkeypatch.setenv("SIMULATE_CHARGER_HARDWARE_FAULT", "false")
    key = _key()
    wallet_id = f"wallet-{key}"

    with TestClient(gateway.app) as client:
        result = _charge(client, wallet_id, key, fault=True)["data"]["reserveAndActivateCharge"]

    assert result["state"] == "COMPLETED"
    assert backend["billing"].wallet(wallet_id)["balance"] == 75
    backend["station"].cancel(f"reservation-{key}")
