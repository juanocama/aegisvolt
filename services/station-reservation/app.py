import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from common.dynamodb import dynamodb_resource

app = FastAPI(title="AegisVolt Station Reservation")
TABLE = os.getenv("TABLE_NAME", "aegisvolt-dev-stations")
table = dynamodb_resource().Table(TABLE)

class Reservation(BaseModel):
    station_id: str
    connector_id: str
    wallet_id: str
    idempotency_key: str

@app.on_event("startup")
async def startup():
    db = dynamodb_resource()
    try:
        db.Table(TABLE).load()
    except Exception:
        db.create_table(TableName=TABLE, KeySchema=[{"AttributeName":"id","KeyType":"HASH"}],
                        AttributeDefinitions=[{"AttributeName":"id","AttributeType":"S"}], BillingMode="PAY_PER_REQUEST")

@app.get("/health")
def health():
    return {"service":"station-reservation","status":"ok"}

@app.get("/stations")
def stations():
    response = table.scan(Limit=100)
    items = response.get("Items", [])
    if not items:
        return [
            {"id":"st-1","name":"North Hall","status":"available","latitude":40.71,"longitude":-74.01,
             "connectors":[{"id":"c-1","type":"CCS","status":"available","power_kw":150}]},
        ]
    return items

@app.post("/reservations")
def reserve(reservation: Reservation):
    existing = table.get_item(Key={"id":"reservation-"+reservation.idempotency_key}).get("Item")
    if existing:
        return existing
    item = {"id":"reservation-"+reservation.idempotency_key, "station_id":reservation.station_id,
            "connector_id":reservation.connector_id, "wallet_id":reservation.wallet_id,
            "status":"reserved"}
    table.put_item(Item=item)
    return item

@app.post("/reservations/{reservation_id}/cancel")
def cancel(reservation_id: str):
    if not reservation_id:
        raise HTTPException(400, "reservation_id required")
    table.put_item(Item={"id":reservation_id if reservation_id.startswith("reservation-") else "reservation-"+reservation_id,
                         "status":"cancelled"})
    return {"id":reservation_id, "status":"cancelled"}
