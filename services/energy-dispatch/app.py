import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from common.dynamodb import dynamodb_resource

app=FastAPI(title="AegisVolt Energy Dispatch")
TABLE=os.getenv("TABLE_NAME","aegisvolt-dev-dispatch")
table=dynamodb_resource().Table(TABLE)

class Activation(BaseModel):
    reservation_id: str
    connector_id: str
    idempotency_key: str
    correlation_id: str
    fault: bool=False

@app.on_event("startup")
async def startup():
    db=dynamodb_resource()
    try: db.Table(TABLE).load()
    except Exception:
        db.create_table(TableName=TABLE, KeySchema=[{"AttributeName":"id","KeyType":"HASH"}],
                        AttributeDefinitions=[{"AttributeName":"id","AttributeType":"S"}], BillingMode="PAY_PER_REQUEST")

@app.get("/health")
def health(): return {"service":"energy-dispatch","status":"ok"}

@app.get("/telemetry")
def telemetry():
    return [{"station_id":"st-1","connector_id":"c-1","power_kw":72.5,"energy_kwh":4.2,"state":"idle"}]

@app.post("/activations")
def activate(payload: Activation):
    key="activation-"+payload.idempotency_key
    existing=table.get_item(Key={"id":key}).get("Item")
    if existing: return existing
    if payload.fault:
        raise HTTPException(503,"Simulated charger fault")
    item={"id":key,"reservation_id":payload.reservation_id,"connector_id":payload.connector_id,
          "status":"active","correlation_id":payload.correlation_id}
    table.put_item(Item=item)
    return item

@app.post("/activations/{activation_id}/stop")
def stop(activation_id: str):
    item={"id":activation_id if activation_id.startswith("activation-") else "activation-"+activation_id,"status":"stopped"}
    table.put_item(Item=item)
    return item
