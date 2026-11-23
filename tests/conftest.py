import importlib.util
import os
from pathlib import Path
import sys

import httpx
import pytest
from moto import mock_aws


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["ENVIRONMENT"] = "dev"
os.environ.pop("AWS_ENDPOINT_URL", None)

_aws = mock_aws()


def _serialize_moto_transactions():
    """Moto 5 snapshots *all* tables with deepcopy and restores that snapshot
    when a TransactWriteItems fails, without any lock. Under concurrent threads
    a failing transaction can therefore undo another thread's committed one,
    which real DynamoDB (serializable transactions) never does. Serialize them
    so concurrency tests exercise the application, not this emulator race."""
    import threading

    from moto.dynamodb.models import DynamoDBBackend

    original = DynamoDBBackend.transact_write_items
    if getattr(original, "_aegisvolt_serialized", False):
        return
    lock = threading.Lock()

    def serialized(self, transact_items):
        with lock:
            return original(self, transact_items)

    serialized._aegisvolt_serialized = True
    DynamoDBBackend.transact_write_items = serialized


def pytest_sessionstart(session):
    _serialize_moto_transactions()
    _aws.start()
    import boto3

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    for table_name in (
        "aegisvolt-dev-stations",
        "aegisvolt-dev-wallets",
        "aegisvolt-dev-dispatch",
        "aegisvolt-dev-sagas",
    ):
        try:
            dynamodb.create_table(
                TableName=table_name,
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
        except dynamodb.meta.client.exceptions.ResourceInUseException:
            pass


def pytest_sessionfinish(session, exitstatus):
    _aws.stop()


def _load_service(name: str, folder: str):
    module_name = f"phase1_{name}"
    if module_name in sys.modules:
        return sys.modules[module_name]
    source = ROOT / "services" / folder / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load service module from {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class InProcessServiceTransport(httpx.AsyncBaseTransport):
    def __init__(self, apps: dict, behavior: dict):
        self.apps = apps
        self.behavior = behavior

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if (
            self.behavior.get("fail_refund")
            and request.url.host == "billing"
            and request.url.path.endswith("/refund")
        ):
            return httpx.Response(500, json={"detail": "Injected refund outage"}, request=request)

        service_name = {
            "station": "station",
            "billing": "billing",
            "dispatch": "dispatch",
        }.get(request.url.host)
        if service_name is None:
            raise RuntimeError(f"Unexpected in-process service host: {request.url.host}")

        transport = httpx.ASGITransport(app=self.apps[service_name])
        response = await transport.handle_async_request(request)
        if (
            self.behavior.get("lose_charge_response_count", 0) > 0
            and request.url.host == "billing"
            and request.url.path == "/charges"
        ):
            self.behavior["lose_charge_response_count"] -= 1
            self.behavior["charge_response_lost"] = True
            await response.aread()
            raise httpx.ReadTimeout("Injected response loss after charge commit", request=request)
        return response


@pytest.fixture
def backend(monkeypatch):
    from gateway import app as gateway

    apps = {
        "station": _load_service("station", "station-reservation").app,
        "billing": _load_service("billing", "billing-wallet").app,
        "dispatch": _load_service("dispatch", "energy-dispatch").app,
    }
    gateway.STATION_URL = "http://station:8001"
    gateway.BILLING_URL = "http://billing:8002"
    gateway.DISPATCH_URL = "http://dispatch:8003"
    behavior = {}
    real_async_client = httpx.AsyncClient

    def routed_async_client(*args, **kwargs):
        kwargs["transport"] = InProcessServiceTransport(apps, behavior)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(gateway.httpx, "AsyncClient", routed_async_client)
    return {
        "gateway": gateway,
        "apps": apps,
        "behavior": behavior,
        "station": _load_service("station", "station-reservation"),
        "billing": _load_service("billing", "billing-wallet"),
        "dispatch": _load_service("dispatch", "energy-dispatch"),
    }
