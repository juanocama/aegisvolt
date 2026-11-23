"""Full business flow through the public contract (GraphQL), spec 2.3 and rubric 6.3/6.4."""

import urllib.request
import uuid

import pytest

CHARGE = """
mutation($w:String!,$s:String!,$c:String!,$a:Float!,$k:String!){
  reserveAndActivateCharge(walletId:$w,stationId:$s,connectorId:$c,amount:$a,idempotencyKey:$k){
    success sagaId correlationId state message
  }
}"""
STOP = "mutation($id:String!){ stopAndRelease(sagaId:$id){ state reservationStatus activationStatus } }"
WALLET = "query($w:String!){ wallet(walletId:$w){ balance currency } }"
STATIONS = "{ stations { id status connectors { id status } } }"
FAULT = "SIMULATE_CHARGER_HARDWARE_FAULT"


def _connector(stack):
    station = stack.data(STATIONS)["stations"][0]
    connector = station["connectors"][0]
    return station["id"], connector["id"], connector["status"]


def _charge(stack, wallet, amount, key=None):
    station_id, connector_id, _ = _connector(stack)
    variables = {"w": wallet, "s": station_id, "c": connector_id, "a": amount, "k": key or str(uuid.uuid4())}
    return stack.data(CHARGE, variables)["reserveAndActivateCharge"], variables


@pytest.fixture(autouse=True)
def _fault_flag_off(request, stack):
    """Mutating tests run with the fault flag off and restore it afterwards.
    Read-only smoke tests (the only ones run against prod) never write flags."""
    if request.node.get_closest_marker("mutating") is None:
        yield
        return
    if stack.read_only:
        pytest.skip("E2E_READ_ONLY: mutating scenario not run in this environment")
    stack.set_flag(FAULT, False)
    stack.wait_for_flag(FAULT, False)
    yield
    stack.set_flag(FAULT, False)


def test_dashboard_reports_expected_environment(stack):
    dashboard = stack.data("{ dashboard { environment servicesOk } }")["dashboard"]
    assert dashboard == {"environment": stack.environment, "servicesOk": True}


def test_official_flags_are_exposed(stack):
    names = [flag["name"] for flag in stack.data("{ flags { name enabled } }")["flags"]]
    assert names == ["ENABLE_DYNAMIC_SURGE_PRICING", "ENABLE_FAST_CHARGE_BOOST", FAULT]


@pytest.mark.mutating
def test_happy_path_charges_once_and_releases(stack):
    wallet = f"e2e-{uuid.uuid4().hex[:8]}"
    result, variables = _charge(stack, wallet, 20.0)
    assert result["state"] == "COMPLETED", result
    replay = stack.data(CHARGE, variables)["reserveAndActivateCharge"]
    assert replay["sagaId"] == result["sagaId"] and replay["state"] == "COMPLETED"
    assert stack.data(WALLET, {"w": wallet})["wallet"]["balance"] == 80.0

    conflict = stack.gql(CHARGE, dict(variables, a=21.0))
    assert conflict.get("errors"), "same idempotency key with different payload must be rejected"

    stopped = stack.data(STOP, {"id": result["sagaId"]})["stopAndRelease"]
    assert stopped["state"] == "STOPPED"
    assert _connector(stack)[2] == "available"


@pytest.mark.mutating
def test_insufficient_funds_releases_connector(stack):
    wallet = f"e2e-{uuid.uuid4().hex[:8]}"
    result, _ = _charge(stack, wallet, 1000.0)
    assert result["state"] == "COMPENSATED", result
    assert "Insufficient funds" in result["message"]
    assert stack.data(WALLET, {"w": wallet})["wallet"]["balance"] == 100.0
    assert _connector(stack)[2] == "available"


@pytest.mark.mutating
def test_runtime_fault_flag_triggers_refund_then_release_without_redeploy(stack):
    stack.set_flag(FAULT, True)
    stack.wait_for_flag(FAULT, True)
    wallet = f"e2e-{uuid.uuid4().hex[:8]}"
    result, _ = _charge(stack, wallet, 30.0)
    assert result["state"] == "COMPENSATED", result
    assert stack.data(WALLET, {"w": wallet})["wallet"]["balance"] == 100.0
    assert _connector(stack)[2] == "available"
    sagas = {s["id"]: s for s in stack.data("{ sagas { id state chargeStatus reservationStatus } }")["sagas"]}
    assert sagas[result["sagaId"]]["chargeStatus"] == "refunded"
    assert sagas[result["sagaId"]]["reservationStatus"] == "cancelled"


def test_frontend_serves_spa_and_proxies_graphql(stack):
    if not stack.frontend_url:
        pytest.skip("E2E_FRONTEND_URL not set")
    with urllib.request.urlopen(stack.frontend_url + "/", timeout=10) as response:
        assert response.status == 200 and b'id="root"' in response.read()
    through_frontend = stack.data("{ dashboard { environment } }", url=stack.frontend_url + "/graphql")
    assert through_frontend["dashboard"]["environment"] == stack.environment
