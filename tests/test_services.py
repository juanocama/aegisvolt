from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import uuid

from fastapi import HTTPException

from common.environment import environment_table_name

def _key() -> str:
    return str(uuid.uuid4())


def test_concurrent_reservations_cannot_take_same_connector(backend):
    station = backend["station"]
    wallet_id = f"wallet-{_key()}"
    keys = [_key(), _key()]

    def reserve(key):
        try:
            return station.reserve(
                station.Reservation(
                    station_id="st-1",
                    connector_id="c-1",
                    wallet_id=wallet_id,
                    idempotency_key=key,
                )
            )
        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, keys))

    successful = [item for item in results if isinstance(item, dict)]
    conflicts = [item for item in results if item == 409]
    assert len(successful) == 1
    assert len(conflicts) == 1
    assert station.stations()[0]["connectors"][0]["status"] == "reserved"
    station.cancel(successful[0]["id"])


def test_charge_replay_and_refund_replay_are_atomic(backend):
    billing = backend["billing"]
    wallet_id = f"wallet-{_key()}"
    key = _key()
    payload = billing.Charge(
        wallet_id=wallet_id,
        amount=Decimal("25.00"),
        idempotency_key=key,
        correlation_id=_key(),
    )

    first_charge = billing.charge(payload)
    replayed_charge = billing.charge(payload)
    assert first_charge["id"] == replayed_charge["id"]
    assert billing.wallet(wallet_id)["balance"] == Decimal("75.00")

    def refund():
        return billing.refund(first_charge["id"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        refunds = list(pool.map(lambda _: refund(), range(2)))

    assert all(item["status"] == "refunded" for item in refunds)
    assert billing.wallet(wallet_id)["balance"] == Decimal("100.00")
    assert len(
        [
            item
            for item in billing.table.scan().get("Items", [])
            if item.get("id") == f"refund-{first_charge['id']}"
        ]
    ) == 1


def test_dispatch_stop_preserves_activation_and_telemetry_state(backend):
    dispatch = backend["dispatch"]
    key = _key()
    payload = dispatch.Activation(
        reservation_id=f"reservation-{key}",
        station_id="st-1",
        connector_id="c-1",
        idempotency_key=key,
        correlation_id=_key(),
    )

    activation = dispatch.activate(payload)
    stopped = dispatch.stop(activation["id"])
    replayed_stop = dispatch.stop(activation["id"])

    assert activation["status"] == "active"
    assert stopped["status"] == "stopped"
    assert replayed_stop["status"] == "stopped"
    assert dispatch._get_item(f"telemetry-activation-{key}")["state"] == "stopped"


def test_service_idempotency_key_cannot_change_charge_request(backend):
    billing = backend["billing"]
    key = _key()
    first = billing.Charge(
        wallet_id=f"wallet-{_key()}",
        amount=Decimal("10"),
        idempotency_key=key,
        correlation_id=_key(),
    )
    second = billing.Charge(
        wallet_id=first.wallet_id,
        amount=Decimal("11"),
        idempotency_key=key,
        correlation_id=first.correlation_id,
    )
    billing.charge(first)

    try:
        billing.charge(second)
    except HTTPException as error:
        assert error.status_code == 409
    else:
        raise AssertionError("Changed charge request was accepted for a reused key")


def test_environment_table_defaults_and_mismatches_fail_closed(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.delenv("TABLE_NAME", raising=False)
    assert environment_table_name("wallets") == "aegisvolt-test-wallets"

    monkeypatch.setenv("TABLE_NAME", "aegisvolt-dev-wallets")
    try:
        environment_table_name("wallets")
    except ValueError as error:
        assert "test" in str(error)
    else:
        raise AssertionError("A dev table was accepted in the test environment")
