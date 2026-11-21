import os
import boto3
import httpx
from prefect import flow, task

@task
def check_health(url):
    try:
        r=httpx.get(url,timeout=5)
        r.raise_for_status()
        return True
    except Exception:
        return False

@task
def audit_sagas():
    endpoint=os.getenv("AWS_ENDPOINT_URL")
    kwargs={"region_name":os.getenv("AWS_DEFAULT_REGION","us-east-1")}
    if endpoint:
        kwargs.update(endpoint_url=endpoint,aws_access_key_id="test",aws_secret_access_key="test")
    db=boto3.resource("dynamodb",**kwargs)
    table=db.Table(os.getenv("SAGA_TABLE","aegisvolt-dev-sagas"))
    counts={}
    for item in table.scan().get("Items",[]):
        state=item.get("state","UNKNOWN")
        counts[state]=counts.get(state,0)+1
    return counts

@task
def publish_metric(counts):
    endpoint=os.getenv("AWS_ENDPOINT_URL")
    kwargs={"region_name":os.getenv("AWS_DEFAULT_REGION","us-east-1")}
    if endpoint:
        kwargs.update(endpoint_url=endpoint,aws_access_key_id="test",aws_secret_access_key="test")
    cloudwatch=boto3.client("cloudwatch",**kwargs)
    for state,count in counts.items():
        cloudwatch.put_metric_data(Namespace="AegisVolt/SAGA",MetricData=[{"MetricName":"Sagas","Value":count,"Unit":"Count","Dimensions":[{"Name":"State","Value":state}]}])

@flow(name="AegisVolt environment audit")
def audit():
    base=os.getenv("GATEWAY_URL","http://localhost:8000")
    health=check_health(base+"/health")
    counts=audit_sagas()
    publish_metric(counts)
    return {"health":health,"sagas":counts}
