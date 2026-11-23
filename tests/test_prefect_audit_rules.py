"""SAGA consistency rules used by the Prefect audit (spec 2.5, rubric 6.4)."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("audit_flow_rules", ROOT / "observability/prefect/audit_flow.py")
audit_flow = importlib.util.module_from_spec(spec)
sys.modules["audit_flow_rules"] = audit_flow
spec.loader.exec_module(audit_flow)

NOW = "2026-11-23T00:00:00+00:00"


def _saga(state, **refs):
    return {"id": f"saga-{state}", "correlation_id": "c", "state": state, "updated_at": NOW, "events": [], **refs}


def _records(charge=None, reservation=None, activation=None):
    return {
        "billing-wallet": [{"id": "ch", "status": charge}] if charge else [],
        "station-reservation": [{"id": "rs", "status": reservation}] if reservation else [],
        "energy-dispatch": [{"id": "ac", "status": activation}] if activation else [],
    }


def _issues(saga, records):
    result = audit_flow.summarize_sagas([saga], records, orphan_audit_complete=False)
    return result["sagas"][0]["issues"]


def test_properly_compensated_saga_is_consistent():
    saga = _saga("COMPENSATED", charge_id="ch", reservation_id="rs", activation_id="ac")
    assert _issues(saga, _records("refunded", "cancelled", "failed")) == []


def test_compensated_saga_that_kept_the_money_is_flagged():
    saga = _saga("COMPENSATED", charge_id="ch", reservation_id="rs")
    assert "compensated_saga_charge_id_is_charged" in _issues(saga, _records("charged", "cancelled"))


def test_compensated_saga_that_kept_the_connector_is_flagged():
    saga = _saga("COMPENSATED", charge_id="ch", reservation_id="rs")
    assert "compensated_saga_reservation_id_is_reserved" in _issues(saga, _records("refunded", "reserved"))


def test_stopped_saga_is_consistent():
    saga = _saga("STOPPED", charge_id="ch", reservation_id="rs", activation_id="ac")
    assert _issues(saga, _records("charged", "cancelled", "stopped")) == []
