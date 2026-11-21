import hashlib
import json
import os
from decimal import Decimal

from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from common.dynamodb import dynamodb_client, dynamodb_resource, ensure_table
from common.environment import environment_table_name

app = FastAPI(title="AegisVolt Billing Wallet")
TABLE = environment_table_name("wallets")
table = dynamodb_resource().Table(TABLE)
dynamodb = dynamodb_client()


class Charge(BaseModel):
    wallet_id: str = Field(min_length=1)
    amount: Decimal = Field(gt=Decimal("0"))
    idempotency_key: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


def _amount_text(amount: Decimal) -> str:
    return format(amount.normalize(), "f")


def _charge_id(idempotency_key: str) -> str:
    return f"charge-{idempotency_key}"


def _refund_id(charge_id: str) -> str:
    return f"refund-{charge_id}"


def _charge_fingerprint(payload: Charge) -> str:
    serialized = json.dumps(
        {"wallet_id": payload.wallet_id, "amount": _amount_text(payload.amount)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _get_item(item_id: str) -> dict | None:
    return table.get_item(
        Key={"id": item_id},
        ConsistentRead=True,
    ).get("Item")


def _ensure_wallet(wallet_id: str) -> dict:
    wallet = _get_item(wallet_id)
    if wallet:
        return wallet

    item = {"id": wallet_id, "balance": Decimal("100.00"), "currency": "USD"}
    try:
        table.put_item(Item=item, ConditionExpression="attribute_not_exists(id)")
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
    wallet = _get_item(wallet_id)
    if not wallet:
        raise HTTPException(503, "Wallet could not be initialized")
    return wallet


@app.on_event("startup")
async def startup():
    global table
    table = ensure_table(TABLE)


@app.get("/health")
def health():
    return {"service": "billing-wallet", "status": "ok"}


@app.get("/wallets/{wallet_id}")
def wallet(wallet_id: str):
    return _ensure_wallet(wallet_id)


@app.post("/charges")
def charge(payload: Charge):
    item_id = _charge_id(payload.idempotency_key)
    fingerprint = _charge_fingerprint(payload)
    existing = _get_item(item_id)
    if existing:
        if existing.get("request_fingerprint") != fingerprint:
            raise HTTPException(409, "Idempotency key was already used for a different charge")
        return existing

    _ensure_wallet(payload.wallet_id)
    item = {
        "id": item_id,
        "record_type": "charge",
        "wallet_id": payload.wallet_id,
        "amount": payload.amount,
        "currency": "USD",
        "status": "charged",
        "correlation_id": payload.correlation_id,
        "request_fingerprint": fingerprint,
    }

    try:
        dynamodb.transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": TABLE,
                        "Key": {"id": {"S": payload.wallet_id}},
                        "UpdateExpression": "SET balance = balance - :amount",
                        "ConditionExpression": "attribute_exists(id) AND balance >= :amount",
                        "ExpressionAttributeValues": {":amount": {"N": _amount_text(payload.amount)}},
                    }
                },
                {
                    "Update": {
                        "TableName": TABLE,
                        "Key": {"id": {"S": item["id"]}},
                        "UpdateExpression": (
                            "SET record_type = :type, wallet_id = :wallet, amount = :amount, "
                            "currency = :currency, #status = :status, "
                            "correlation_id = :correlation, request_fingerprint = :fingerprint"
                        ),
                        "ConditionExpression": "attribute_not_exists(id)",
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": {
                            ":type": {"S": item["record_type"]},
                            ":wallet": {"S": item["wallet_id"]},
                            ":amount": {"N": _amount_text(item["amount"])},
                            ":currency": {"S": item["currency"]},
                            ":status": {"S": item["status"]},
                            ":correlation": {"S": item["correlation_id"]},
                            ":fingerprint": {"S": item["request_fingerprint"]},
                        },
                    }
                },
            ]
        )
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        if code != "TransactionCanceledException":
            raise

        existing = _get_item(item_id)
        if existing:
            if existing.get("request_fingerprint") != fingerprint:
                raise HTTPException(409, "Idempotency key was already used for a different charge")
            return existing

        current_wallet = _get_item(payload.wallet_id)
        if current_wallet and current_wallet["balance"] < payload.amount:
            raise HTTPException(402, "Insufficient funds")
        raise HTTPException(503, "Charge outcome is uncertain; retry with the same idempotency key")

    return item


@app.post("/charges/{charge_id}/refund")
def refund(charge_id: str):
    normalized_id = charge_id if charge_id.startswith("charge-") else f"charge-{charge_id}"
    charge_item = _get_item(normalized_id)
    if not charge_item:
        raise HTTPException(404, "Charge not found")

    refund_id = _refund_id(normalized_id)
    existing_refund = _get_item(refund_id)
    if existing_refund:
        return charge_item
    if charge_item.get("status") != "charged":
        raise HTTPException(409, "Charge is not refundable")

    amount = charge_item["amount"]
    wallet_id = charge_item["wallet_id"]
    refund_item = {
        "id": refund_id,
        "record_type": "refund",
        "charge_id": normalized_id,
        "wallet_id": wallet_id,
        "amount": amount,
        "status": "refunded",
    }
    try:
        dynamodb.transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": TABLE,
                        "Key": {"id": {"S": wallet_id}},
                        "UpdateExpression": "SET balance = balance + :amount",
                        "ConditionExpression": "attribute_exists(id)",
                        "ExpressionAttributeValues": {":amount": {"N": _amount_text(amount)}},
                    }
                },
                {
                    "Update": {
                        "TableName": TABLE,
                        "Key": {"id": {"S": normalized_id}},
                        "UpdateExpression": "SET #status = :refunded",
                        "ConditionExpression": "#status = :charged",
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": {
                            ":charged": {"S": "charged"},
                            ":refunded": {"S": "refunded"},
                        },
                    }
                },
                {
                    "Update": {
                        "TableName": TABLE,
                        "Key": {"id": {"S": refund_item["id"]}},
                        "UpdateExpression": (
                            "SET record_type = :type, charge_id = :charge, "
                            "wallet_id = :wallet, amount = :amount, #status = :status"
                        ),
                        "ConditionExpression": "attribute_not_exists(id)",
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": {
                            ":type": {"S": refund_item["record_type"]},
                            ":charge": {"S": refund_item["charge_id"]},
                            ":wallet": {"S": refund_item["wallet_id"]},
                            ":amount": {"N": _amount_text(refund_item["amount"])},
                            ":status": {"S": refund_item["status"]},
                        },
                    }
                },
            ]
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
            raise
        existing_refund = _get_item(refund_id)
        if existing_refund:
            return _get_item(normalized_id)
        current_charge = _get_item(normalized_id)
        if current_charge and current_charge.get("status") == "refunded":
            raise HTTPException(409, "Refund record is missing for a refunded charge")
        raise HTTPException(503, "Refund outcome is uncertain; retry the same refund")

    return _get_item(normalized_id)
