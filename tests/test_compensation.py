import uuid

from fastapi.testclient import TestClient


def test_retry_compensation_rejects_non_failed_saga(backend):
    gateway = backend["gateway"]
    saga_id = f"saga-{uuid.uuid4()}"
    gateway.saga_table.put_item(
        Item={
            "id": saga_id,
            "correlation_id": "test-correlation",
            "state": "COMPLETED",
            "reservation_status": "reserved",
            "charge_status": "charged",
            "activation_status": "active",
        }
    )

    with TestClient(gateway.app) as client:
        response = client.post(
            "/graphql",
            json={
                "query": (
                    "mutation Retry($sagaId: String!) { "
                    "retryCompensation(sagaId: $sagaId) { id state } }"
                ),
                "variables": {"sagaId": saga_id},
            },
        ).json()

    assert response.get("errors")
    assert gateway.get_saga(saga_id)["state"] == "COMPLETED"
