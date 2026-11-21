import os
os.environ["AWS_ACCESS_KEY_ID"]="test"
os.environ["AWS_SECRET_ACCESS_KEY"]="test"
os.environ["AWS_DEFAULT_REGION"]="us-east-1"

from moto import mock_aws
mock_aws().start()

import asyncio
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
sys.path.insert(0,str(Path(__file__).parents[1]/"gateway"))
import gateway.app as gateway

class Response:
    def __init__(self,status=200,json_data=None):
        self.status_code=status
        self._json=json_data or {}
    def raise_for_status(self):
        if self.status_code>=400:
            raise gateway.httpx.HTTPStatusError("error",request=None,response=self)
    def json(self): return self._json

class AsyncClient:
    responses=None
    def __init__(self,*a,**k): pass
    async def __aenter__(self): return self
    async def __aexit__(self,*a): pass
    async def post(self,url,json=None,timeout=None):
        if "/reservations" in url and url.endswith("/reservations"):
            return Response(200,{"id":"reservation-ok"})
        if "/charges" in url:
            if json["amount"]>100: return Response(402,{"detail":"Insufficient funds"})
            return Response(200,{"id":"charge-ok"})
        if "/activations" in url:
            if json.get("fault"): return Response(503,{"detail":"Simulated charger fault"})
            return Response(200,{"id":"activation-ok"})
        if "/cancel" in url: return Response(200,{"status":"cancelled"})
        return Response(200,{})

def test_saga_success(monkeypatch):
    monkeypatch.setattr(gateway.httpx,"AsyncClient",AsyncClient)
    saga=asyncio.run(gateway.execute_saga("wallet-1","st-1","c-1",25,"idem-ok","corr-ok"))
    assert saga["state"]=="COMPLETED"
    assert saga["reservation_status"]=="reserved"
    assert saga["charge_status"]=="charged"

def test_saga_insufficient_funds(monkeypatch):
    monkeypatch.setattr(gateway.httpx,"AsyncClient",AsyncClient)
    saga=asyncio.run(gateway.execute_saga("wallet-1","st-1","c-1",101,"idem-low","corr-low"))
    assert saga["state"]=="COMPENSATED"
    assert "Insufficient" in saga["error"]

def test_charger_fault_compensation(monkeypatch):
    monkeypatch.setattr(gateway.httpx,"AsyncClient",AsyncClient)
    monkeypatch.setattr(gateway,"compensate",lambda saga: saga.update({"state":"COMPENSATED","charge_status":"refunded","reservation_status":"cancelled"}))
    saga=asyncio.run(gateway.execute_saga("wallet-1","st-1","c-1",25,"idem-fault","corr-fault",True))
    assert saga["state"]=="COMPENSATED"
    assert saga["charge_status"]=="refunded"

def test_idempotency(monkeypatch):
    monkeypatch.setattr(gateway.httpx,"AsyncClient",AsyncClient)
    first=asyncio.run(gateway.execute_saga("wallet-1","st-1","c-1",25,"idem-repeat","corr-a"))
    second=asyncio.run(gateway.execute_saga("wallet-1","st-1","c-1",25,"idem-repeat","corr-b"))
    assert first["id"]==second["id"]
    assert second["correlation_id"]=="corr-a"
