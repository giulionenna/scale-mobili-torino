import json

import pytest
from fastapi.testclient import TestClient

from scale_mobili.app import create_app


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


def rpc(client, method, params=None, authorization=None, message_id=1):
    headers = {"Accept": "application/json, text/event-stream"}
    if authorization:
        headers["Authorization"] = authorization
    message = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if message_id is not None:
        message["id"] = message_id
    return client.post("/mcp", json=message, headers=headers)


def test_protocol_discovery_and_shared_read(client):
    init = rpc(
        client,
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "prototype-tests", "version": "1"},
        },
    )
    assert init.status_code == 200
    assert init.json()["result"]["protocolVersion"] == "2025-06-18"
    assert rpc(client, "notifications/initialized", message_id=None).status_code == 202
    names = {tool["name"] for tool in rpc(client, "tools/list").json()["result"]["tools"]}
    assert {"get_escalator_status", "get_escalator_history", "submit_escalator_report"} <= names
    response = rpc(
        client,
        "tools/call",
        {"name": "get_escalator_status", "arguments": {"escalator_id": "demo-esc-1"}},
    ).json()["result"]
    status = json.loads(response["content"][0]["text"])
    api = client.get("/api/escalators/demo-esc-1/status").json()
    assert status["community"] == api["community"] is None
    assert status["official"] is None


def test_mcp_write_authentication_and_persistence(client):
    args = {"escalator_id": "demo-esc-1", "status": "guasta", "idempotency_key": "mcp-report-1"}
    unauth = rpc(
        client, "tools/call", {"name": "submit_escalator_report", "arguments": args}
    ).json()["result"]
    assert unauth["isError"]
    assert "mcp/www_authenticate" in unauth["_meta"]
    result = rpc(
        client,
        "tools/call",
        {"name": "submit_escalator_report", "arguments": args},
        "Bearer demo-user-1",
    ).json()["result"]
    assert not result.get("isError")
    assert client.get("/api/escalators/demo-esc-1/status").json()["community"]["status"] == "guasta"


def test_api_rejects_anonymous_and_forged_author(client):
    route = "/api/escalators/demo-esc-1/reports"
    no_token = client.post(route, json={"status": "guasta"})
    assert no_token.status_code == 401
    assert "resource_metadata" in no_token.headers["www-authenticate"]
    assert (
        client.post(
            route,
            json={"status": "guasta", "actor_id": "forged"},
            headers={"Authorization": "Bearer demo-user-1", "Idempotency-Key": "valid-request"},
        ).status_code
        == 422
    )
    assert client.get("/health").headers["cache-control"] == "no-store"


def test_oversized_request_and_rebinding_protection(client):
    assert client.post("/api/escalators/demo-esc-1/reports", content="x" * 65537).status_code == 413
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={"Host": "evil.example", "Accept": "application/json, text/event-stream"},
    )
    assert response.status_code == 421


def test_lambda_adapter_handles_health_and_mcp_lifecycle(settings):
    from scale_mobili.app import lambda_handler_factory
    from scale_mobili.store import MemoryStore

    handler = lambda_handler_factory(settings, MemoryStore())

    def event(path, method="GET", body=None):
        return {
            "version": "2.0",
            "routeKey": "$default",
            "rawPath": path,
            "rawQueryString": "",
            "headers": {
                "host": "localhost:8000",
                "content-type": "application/json",
                "accept": "application/json, text/event-stream",
            },
            "requestContext": {
                "http": {
                    "method": method,
                    "path": path,
                    "sourceIp": "127.0.0.1",
                    "protocol": "HTTP/1.1",
                }
            },
            "body": json.dumps(body) if body else "",
            "isBase64Encoded": False,
        }

    assert handler(event("/health"), {})["statusCode"] == 200
    for _ in range(2):
        response = handler(
            event("/mcp", "POST", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}), {}
        )
        assert response["statusCode"] == 200
        assert "tools" in json.loads(response["body"])["result"]
