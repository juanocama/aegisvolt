"""End-to-end suite against a running AegisVolt stack (Compose or a deployed env).

Required:
  E2E_GRAPHQL_URL   GraphQL endpoint (e.g. http://localhost:8010/graphql or the
                    private API Gateway URL from inside the VPC)
Optional:
  E2E_FRONTEND_URL  Frontend base URL; enables the browser-path checks
  E2E_ENVIRONMENT   expected environment name (default dev)
  E2E_READ_ONLY     true = only read-only smoke tests (used for prod)
  AWS_ENDPOINT_URL  emulator endpoint when toggling flags locally
The suite fails (does not skip) when E2E_GRAPHQL_URL is missing.
"""

import json
import os
import time
import urllib.request
import uuid

import boto3
import pytest


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        pytest.fail(f"{name} must be set for the E2E suite", pytrace=False)
    return value


class Stack:
    def __init__(self):
        self.graphql_url = _require("E2E_GRAPHQL_URL")
        self.frontend_url = os.getenv("E2E_FRONTEND_URL", "").rstrip("/") or None
        self.environment = os.getenv("E2E_ENVIRONMENT", "dev")
        self.read_only = os.getenv("E2E_READ_ONLY", "false").strip().lower() == "true"
        kwargs = {"region_name": os.getenv("AWS_DEFAULT_REGION", "us-east-1")}
        if os.getenv("AWS_ENDPOINT_URL"):
            kwargs["endpoint_url"] = os.environ["AWS_ENDPOINT_URL"]
        self.flags_table = boto3.resource("dynamodb", **kwargs).Table(f"aegisvolt-{self.environment}-flags")

    def gql(self, query: str, variables: dict | None = None, url: str | None = None) -> dict:
        request = urllib.request.Request(
            url or self.graphql_url,
            json.dumps({"query": query, "variables": variables or {}}).encode(),
            {"Content-Type": "application/json", "X-Correlation-ID": str(uuid.uuid4())},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            assert response.status == 200
            return json.loads(response.read())

    def data(self, query: str, variables: dict | None = None, url: str | None = None) -> dict:
        body = self.gql(query, variables, url)
        assert not body.get("errors"), body
        return body["data"]

    def set_flag(self, name: str, enabled: bool) -> None:
        self.flags_table.update_item(
            Key={"id": name},
            UpdateExpression="SET enabled = :v",
            ConditionExpression="attribute_exists(id)",
            ExpressionAttributeValues={":v": enabled},
        )

    def wait_for_flag(self, name: str, enabled: bool, timeout: float = 15) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            flags = {f["name"]: f["enabled"] for f in self.data("{ flags { name enabled } }")["flags"]}
            if flags[name] is enabled:
                return
            time.sleep(0.5)
        raise AssertionError(f"{name} did not become {enabled} within {timeout}s")


def pytest_configure(config):
    config.addinivalue_line("markers", "mutating: creates charges or toggles flags (skipped when E2E_READ_ONLY=true)")


@pytest.fixture(scope="session")
def stack() -> Stack:
    return Stack()
