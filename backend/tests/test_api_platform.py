import base64
import io
import json

import boto3
from fastapi.testclient import TestClient
from moto import mock_aws
from PIL import Image

from scale_mobili.app import create_app
from scale_mobili.blobs import S3Blobs


def headers(key="api-request", moderator=False):
    return {
        "Authorization": "Bearer " + ("demo-moderator" if moderator else "demo-user-1"),
        "Idempotency-Key": key,
    }


def test_public_and_private_statistics_and_new_report_contract(settings):
    with TestClient(create_app(settings)) as client:
        availability = client.get("/api/stats/availability")
        assert availability.status_code == 200 and availability.json()["total"] == 9
        overview = client.get("/api/overview").json()
        assert len(overview["stations"]) == 4 and len(overview["devices"]) == 9
        assert all(state["community"] is None for state in overview["states"].values())
        assert overview["availability"]["working"] == 0
        assert "alignment" not in overview and "incidents" not in overview
        assert all("PK" not in device for device in overview["devices"])
        assert "alignment" not in availability.json()
        assert client.get("/api/stats/private").status_code == 401
        assert (
            client.get("/api/stats/private", headers=headers()).json()["alignment"]["comparable"]
            == 0
        )
        assert client.get("/api/devices/demo-esc-2").json()["kind"] == "ascensore"
        route = "/api/devices/demo-esc-1/reports"
        assert client.post(route, headers=headers(), json={"status": "guasta"}).status_code == 422
        assert (
            client.post(
                route, headers=headers(), json={"station_id": "demo-station-2", "status": "guasta"}
            ).status_code
            == 400
        )
        result = client.post(
            route,
            headers=headers(),
            json={"station_id": "demo-station", "status": "guasta", "description": "Fixture HTTP"},
        )
        assert result.status_code == 201
        overview = client.get("/api/overview").json()
        assert overview["states"]["demo-esc-1"]["community"]["status"] == "guasta"
        assert overview["availability"]["observed_devices"] == 1
        assert client.get("/api/feed").json()["items"][0]["description"] == "Fixture HTTP"
        assert client.get("/api/moderation/proposal/queue", headers=headers()).status_code == 403
        assert client.post(
            "/api/moderation/statistics/rebuild", headers=headers(moderator=True)
        ).json()["completed"]


def test_photo_http_contract_and_real_decode(settings):
    with TestClient(create_app(settings)) as client:
        canvas = io.BytesIO()
        Image.new("RGB", (64, 64)).save(canvas, format="PNG")
        body = canvas.getvalue()
        photo = client.post(
            "/api/photos/uploads",
            headers=headers("api-photo-reserve"),
            json={"device_id": "demo-esc-1", "content_type": "image/png", "size_bytes": len(body)},
        ).json()
        photo_id = photo["photo_id"]
        assert (
            client.put(photo["upload"]["url"], headers=headers(), content=body).status_code == 204
        )
        assert (
            client.post(
                f"/api/photos/{photo_id}/complete", headers=headers("api-photo-complete")
            ).status_code
            == 200
        )
        assert client.get(f"/api/photos/{photo_id}/image").status_code == 404
        assert client.get(f"/api/photos/{photo_id}/preview", headers=headers()).content.startswith(
            b"\xff\xd8"
        )
        assert (
            client.post(
                "/api/devices/demo-esc-1/reports",
                headers=headers("api-report-photo"),
                json={"station_id": "demo-station", "status": "guasta", "photo_id": photo_id},
            ).status_code
            == 201
        )
        pending = client.get("/api/moderation/photo/queue", headers=headers(moderator=True)).json()[
            "items"
        ][0]
        reviewed = client.post(
            f"/api/moderation/photos/{photo_id}/review",
            headers=headers("api-approve-photo", True),
            json={
                "decision": "approved",
                "version": pending["version"],
                "reason": "Fotografia di test valida",
            },
        )
        assert reviewed.status_code == 200
        response = client.get(f"/api/photos/{photo_id}/image")
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"


def test_s3_private_storage_and_exact_signed_upload_policy():
    with mock_aws():
        client = boto3.client("s3", region_name="eu-south-1")
        client.create_bucket(
            Bucket="test-private-photos",
            CreateBucketConfiguration={"LocationConstraint": "eu-south-1"},
        )
        storage = S3Blobs(client)
        storage.put("test-private-photos", "sanitized/test.jpg", b"fixture", "image/jpeg")
        assert (
            client.head_object(Bucket="test-private-photos", Key="sanitized/test.jpg")[
                "ServerSideEncryption"
            ]
            == "AES256"
        )
        assert storage.get("test-private-photos", "sanitized/test.jpg")[0] == b"fixture"
        form = storage.upload_form("test-private-photos", "uploads/test", "image/png", 1024)
        policy = json.loads(base64.b64decode(form["fields"]["policy"]))
        assert ["content-length-range", 1024, 1024] in policy["conditions"]
        assert {"Content-Type": "image/png"} in policy["conditions"]
        assert {"x-amz-server-side-encryption": "AES256"} in policy["conditions"]
        assert "public-read" not in json.dumps(form)


def test_new_mcp_tools_share_authentication_and_statistics(settings):
    from test_api_mcp import rpc

    with TestClient(create_app(settings)) as client:
        arguments = {"name": "get_private_statistics", "arguments": {}}
        result = rpc(client, "tools/call", arguments).json()["result"]
        assert result["isError"] and "mcp/www_authenticate" in result["_meta"]
        result = rpc(client, "tools/call", arguments, "Bearer demo-user-1").json()["result"]
        assert not result.get("isError")
        assert json.loads(result["content"][0]["text"])["alignment"]["percentage"] is None
        arguments = {
            "name": "submit_device_report",
            "arguments": {
                "station_id": "demo-station",
                "device_id": "demo-esc-1",
                "status": "funzionante",
                "idempotency_key": "mcp-new-report",
            },
        }
        assert (
            not rpc(client, "tools/call", arguments, "Bearer demo-user-1")
            .json()["result"]
            .get("isError")
        )
        assert (
            client.get("/api/devices/demo-esc-1/status").json()["community"]["status"]
            == "funzionante"
        )


def test_synthetic_source_fixture_idempotency_and_private_original(settings):
    with TestClient(create_app(settings)) as client:
        source = client.post(
            "/api/moderation/sources",
            headers=headers("fixture-source", True),
            json={
                "name": "Fixture di fonte",
                "url": "https://example.invalid/test",
                "meaning": "Fonte sintetica di collaudo, non un report GTT.",
                "synthetic": True,
            },
        ).json()
        route = f"/api/moderation/sources/{source['source_id']}/fixture"
        first = client.post(
            route, headers=headers("fixture-first", True), json={"content": "Originale sintetico"}
        )
        assert first.status_code == 200
        assert (
            client.post(
                route, headers=headers("fixture-first", True), json={"content": "Diverso originale"}
            ).status_code
            == 409
        )
        reference = first.json()["reference"]
        assert (
            client.get(
                "/api/moderation/sources/original", params={"reference": reference}
            ).status_code
            == 401
        )
        original = client.get(
            "/api/moderation/sources/original",
            params={"reference": reference},
            headers=headers(moderator=True),
        )
        assert original.content == b"Originale sintetico"
        data = first.json()
        assert data["acquisition_started_at"] <= data["acquired_at"] <= data["recorded_at"]


def test_percentages_match_frontend_rounding():
    from scale_mobili.domain import percentage

    assert percentage(1, 8) == 13
    assert percentage(3, 8) == 38
    assert percentage(6, 9) == 67
    assert percentage(0, 0) is None
