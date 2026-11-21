import os
import boto3


def dynamodb_resource():
    kwargs = {"region_name": os.getenv("AWS_DEFAULT_REGION", "us-east-1")}
    endpoint = os.getenv("AWS_ENDPOINT_URL")
    if endpoint:
        kwargs["endpoint_url"] = endpoint
        kwargs.setdefault("aws_access_key_id", os.getenv("AWS_ACCESS_KEY_ID", "test"))
        kwargs.setdefault("aws_secret_access_key", os.getenv("AWS_SECRET_ACCESS_KEY", "test"))
    return boto3.resource("dynamodb", **kwargs)


def ensure_table(table_name, partition_key="id"):
    db = dynamodb_resource()
    try:
        return db.Table(table_name)
    except Exception:
        return db.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": partition_key, "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": partition_key, "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
