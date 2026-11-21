import os
import boto3
from botocore.exceptions import ClientError


def _dynamodb_kwargs():
    kwargs = {"region_name": os.getenv("AWS_DEFAULT_REGION", "us-east-1")}
    endpoint = os.getenv("AWS_ENDPOINT_URL")
    if endpoint:
        kwargs["endpoint_url"] = endpoint
        kwargs.setdefault("aws_access_key_id", os.getenv("AWS_ACCESS_KEY_ID", "test"))
        kwargs.setdefault("aws_secret_access_key", os.getenv("AWS_SECRET_ACCESS_KEY", "test"))
    return kwargs


def dynamodb_resource():
    return boto3.resource("dynamodb", **_dynamodb_kwargs())


def dynamodb_client():
    return boto3.client("dynamodb", **_dynamodb_kwargs())


def ensure_table(table_name, partition_key="id"):
    db = dynamodb_resource()
    table = db.Table(table_name)
    try:
        table.load()
        return table
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            raise

    try:
        table = db.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": partition_key, "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": partition_key, "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ResourceInUseException":
            raise
        table = db.Table(table_name)

    table.wait_until_exists()
    return table
