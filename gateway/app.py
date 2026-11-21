import os
import uuid
from typing import Optional, List

import httpx
import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from common.dynamodb import dynamodb_resource

STATION_URL=os.getenv("STATION_URL","http://localhost:8001")
BILLING_URL=os.getenv("BILLING_URL","http://localhost:8002")
DISPATCH_URL=os.getenv("DISPATCH_URL","http://localhost:8003")
SAGA_TABLE=os.getenv("SAGA_TABLE","aegisvolt-dev-sagas")

app=FastAPI(title="AegisVolt GraphQL Gateway")
db=dynamodb_resource()
try:
    saga_table=db.Table(SAGA_TABLE)
    saga_table.load()
except Exception:
    saga_table=db.create_table(TableName=SAGA_TABLE,KeySchema=[{"AttributeName":"id","KeyType":"HASH"}],
                               AttributeDefinitions=[{"AttributeName":"id","AttributeType":"S"}],BillingMode="PAY_PER_REQUEST")

@app.get("/health")
def health(): return {"status":"ok","service":"graphql-gateway"}

@strawberry.type
class Connector:
    id:str
    type:str
    status:str
    power_kw:float

@strawberry.type
class Station:
    id:str
    name:str
    status:str
    latitude:float
    longitude:float
    connectors:Optional[List[Connector]]

@strawberry.type
class Telemetry:
    station_id:str
    connector_id:str
    power_kw:float
    energy_kwh:float
    state:str

@strawberry.type
class Wallet:
    id:str
    balance:float
    currency:str

@strawberry.type
class FeatureFlag:
    name:str
    enabled:bool

@strawberry.type
class Saga:
    id:str
    correlation_id:str
    state:str
    reservation_status:str
    charge_status:str
    activation_status:str
    error:Optional[str]

@strawberry.type
class ChargeResult:
    success:bool
    saga_id:str
    correlation_id:str
    state:str
    message:str

@strawberry.type
class Dashboard:
    environment:str
    services_ok:bool

def persist(saga):
    saga_table.put_item(Item=saga)

def get_saga(saga_id):
    return saga_table.get_item(Key={"id":saga_id}).get("Item")

def compensate(saga):
    saga["reservation_status"]="compensating"
    saga["charge_status"]="compensating"
    persist(saga)
    try:
        if saga.get("charge_id"):
            httpx.post(f"{BILLING_URL}/charges/{saga['charge_id']}/refund",timeout=5)
        if saga.get("reservation_id"):
            httpx.post(f"{STATION_URL}/reservations/{saga['reservation_id']}/cancel",timeout=5)
        saga["charge_status"]="refunded"
        saga["reservation_status"]="cancelled"
        saga["state"]="COMPENSATED"
    except httpx.HTTPError as exc:
        saga["state"]="COMPENSATION_FAILED"
        saga["error"]=str(exc)
    persist(saga)

async def execute_saga(wallet_id, station_id, connector_id, amount, idempotency_key, correlation_id, fault=False):
    saga_id="saga-"+idempotency_key
    existing=get_saga(saga_id)
    if existing:
        return existing
    saga={"id":saga_id,"correlation_id":correlation_id,"state":"STARTED","reservation_status":"pending",
          "charge_status":"pending","activation_status":"pending","error":"","wallet_id":wallet_id,
          "station_id":station_id,"connector_id":connector_id,"amount":amount,"fault":fault}
    persist(saga)
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r=await client.post(f"{STATION_URL}/reservations",json={"station_id":station_id,"connector_id":connector_id,
                "wallet_id":wallet_id,"idempotency_key":idempotency_key})
            r.raise_for_status()
            reserved=r.json()
            saga["reservation_id"]=reserved["id"]
            saga["reservation_status"]="reserved"
            saga["state"]="RESERVATION_COMPLETED"
            persist(saga)
        except httpx.HTTPError as exc:
            saga["state"]="FAILED"; saga["error"]=str(exc); persist(saga); return saga

        try:
            r=None
            r=await client.post(f"{BILLING_URL}/charges",json={"wallet_id":wallet_id,"amount":amount,
                "idempotency_key":idempotency_key,"correlation_id":correlation_id})
            r.raise_for_status()
            charged=r.json()
            saga["charge_id"]=charged["id"]
            saga["charge_status"]="charged"
            saga["state"]="CHARGE_COMPLETED"
            persist(saga)
        except httpx.HTTPError as exc:
            saga["charge_status"]="failed"
            saga["state"]="COMPENSATED"
            saga["error"]="Insufficient funds" if r is not None and r.status_code==402 else str(exc)
            saga["reservation_status"]="cancelled"
            await client.post(f"{STATION_URL}/reservations/{saga['reservation_id']}/cancel",timeout=5)
            persist(saga)
            return saga

        try:
            r=await client.post(f"{DISPATCH_URL}/activations",json={"reservation_id":saga["reservation_id"],
                "connector_id":connector_id,"idempotency_key":idempotency_key,
                "correlation_id":correlation_id,"fault":fault})
            r.raise_for_status()
            activated=r.json()
            saga["activation_id"]=activated["id"]
            saga["activation_status"]="active"
            saga["state"]="COMPLETED"
            persist(saga)
        except httpx.HTTPError as exc:
            saga["activation_status"]="failed"
            saga["error"]=str(exc)
            persist(saga)
            compensate(saga)
    return saga

@strawberry.type
class Query:
    @strawberry.field
    async def dashboard(self)->Dashboard:
        async with httpx.AsyncClient(timeout=5) as client:
            h=(await client.get(f"{STATION_URL}/health")).json()
        return Dashboard(environment=os.getenv("ENVIRONMENT","dev"),services_ok=h.get("status")=="ok")

    @strawberry.field
    async def stations(self)->List[Station]:
        async with httpx.AsyncClient(timeout=5) as client:
            data=(await client.get(f"{STATION_URL}/stations")).json()
        return [Station(id=x["id"],name=x["name"],status=x["status"],latitude=x["latitude"],longitude=x["longitude"],
                        connectors=[Connector(id=c["id"],type=c["type"],status=c["status"],power_kw=c["power_kw"]) for c in x.get("connectors",[])]) for x in data]

    @strawberry.field
    async def telemetry(self)->List[Telemetry]:
        async with httpx.AsyncClient(timeout=5) as client:
            data=(await client.get(f"{DISPATCH_URL}/telemetry")).json()
        return [Telemetry(**x) for x in data]

    @strawberry.field
    async def wallet(self,wallet_id:str)->Wallet:
        async with httpx.AsyncClient(timeout=5) as client:
            x=(await client.get(f"{BILLING_URL}/wallets/{wallet_id}")).json()
        return Wallet(id=x["id"],balance=float(x["balance"]),currency=x["currency"])

    @strawberry.field
    def flags(self)->List[FeatureFlag]:
        return [FeatureFlag(name="canaryCharge",enabled=os.getenv("FLAG_CANARY","true").lower()=="true"),
                FeatureFlag(name="chargerFaultSimulation",enabled=os.getenv("FLAG_FAULT","false").lower()=="true")]

    @strawberry.field
    def sagas(self)->List[Saga]:
        data=saga_table.scan(Limit=100).get("Items",[])
        return [Saga(id=x["id"],correlation_id=x["correlation_id"],state=x["state"],
                     reservation_status=x["reservation_status"],charge_status=x["charge_status"],
                     activation_status=x["activation_status"],error=x.get("error") or None) for x in data]

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def reserve_and_activate_charge(self,wallet_id:str,station_id:str,connector_id:str,amount:float,
                                          idempotency_key:str,charge_fault:bool=False)->ChargeResult:
        correlation_id=str(uuid.uuid4())
        saga=await execute_saga(wallet_id,station_id,connector_id,amount,idempotency_key,correlation_id,charge_fault)
        return ChargeResult(success=saga["state"]=="COMPLETED",saga_id=saga["id"],
                            correlation_id=saga["correlation_id"],state=saga["state"],message=saga.get("error",""))

    @strawberry.mutation
    def retry_compensation(self,saga_id:str)->Saga:
        saga=get_saga(saga_id)
        if not saga: raise ValueError("SAGA not found")
        compensate(saga)
        return Saga(id=saga["id"],correlation_id=saga["correlation_id"],state=saga["state"],
                    reservation_status=saga["reservation_status"],charge_status=saga["charge_status"],
                    activation_status=saga["activation_status"],error=saga.get("error") or None)

schema=strawberry.Schema(query=Query,mutation=Mutation)
graphql_app=GraphQLRouter(schema)
app.include_router(graphql_app,prefix="/graphql")
