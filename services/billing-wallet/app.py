import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from common.dynamodb import dynamodb_resource

app = FastAPI(title="AegisVolt Billing Wallet")
TABLE = os.getenv("TABLE_NAME", "aegisvolt-dev-wallets")
table = dynamodb_resource().Table(TABLE)

class Charge(BaseModel):
    wallet_id: str
    amount: float
    idempotency_key: str
    correlation_id: str

@app.on_event("startup")
async def startup():
    db=dynamodb_resource()
    try: db.Table(TABLE).load()
    except Exception:
        db.create_table(TableName=TABLE, KeySchema=[{"AttributeName":"id","KeyType":"HASH"}],
                        AttributeDefinitions=[{"AttributeName":"id","AttributeType":"S"}], BillingMode="PAY_PER_REQUEST")

@app.get("/health")
def health(): return {"service":"billing-wallet","status":"ok"}

@app.get("/wallets/{wallet_id}")
def wallet(wallet_id: str):
    item = table.get_item(Key={"id":wallet_id}).get("Item")
    if not item:
        item={"id":wallet_id,"balance":100.0,"currency":"USD"}
        table.put_item(Item=item)
    return item

@app.post("/charges")
def charge(payload: Charge):
    key="charge-"+payload.idempotency_key
    existing=table.get_item(Key={"id":key}).get("Item")
    if existing: return existing
    wallet=table.get_item(Key={"id":payload.wallet_id}).get("Item") or {"id":payload.wallet_id,"balance":100.0,"currency":"USD"}
    if wallet["balance"] < payload.amount:
        raise HTTPException(402, "Insufficient funds")
    wallet["balance"]=float(wallet["balance"])-payload.amount
    table.put_item(Item=wallet)
    item={"id":key,"wallet_id":payload.wallet_id,"amount":payload.amount,"status":"charged",
          "correlation_id":payload.correlation_id}
    table.put_item(Item=item)
    return item

@app.post("/charges/{charge_id}/refund")
def refund(charge_id: str):
    charge=table.get_item(Key={"id":charge_id if charge_id.startswith("charge-") else "charge-"+charge_id}).get("Item")
    if not charge: return {"id":charge_id,"status":"refunded"}
    wallet=table.get_item(Key={"id":charge["wallet_id"]}).get("Item")
    if wallet:
        wallet["balance"]=float(wallet["balance"])+float(charge["amount"])
        table.put_item(Item=wallet)
    charge["status"]="refunded"
    table.put_item(Item=charge)
    return charge
