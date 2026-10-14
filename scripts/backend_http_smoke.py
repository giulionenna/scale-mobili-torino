"""Collaudo HTTP del backend; solo identità e dati sintetici in demo/local.

Il backend deve essere avviato separatamente. Passare --url per cambiare porta.
"""

import argparse
import io
import json
from uuid import uuid4

import httpx
from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    with httpx.Client(base_url=args.url, timeout=30) as client:
        health = client.get("/health").json()
        assert health["mode"] in {"demo", "local"}, (
            "Questo collaudo non usa risorse AWS"
        )

        def post(path, body=None, moderator=False):
            response = client.post(
                path,
                json=body,
                headers={
                    "Authorization": "Bearer "
                    + ("demo-moderator" if moderator else "demo-user-1"),
                    "Idempotency-Key": "http-smoke-" + str(uuid4()),
                },
            )
            response.raise_for_status()
            return response.json()

        headers = {"Authorization": "Bearer demo-user-1"}
        mod = {"Authorization": "Bearer demo-moderator"}
        assert client.get("/api/stats/private").status_code == 401
        assert client.get("/api/stats/availability").json()["total"] >= 9
        pending = post(
            "/api/proposals",
            {
                "station_id": "demo-station",
                "kind": "ascensore",
                "name": "Ascensore HTTP di prova",
                "location": "Percorso sintetico",
                "description": "Collaudo, non impianto reale",
            },
        )
        approved = post(
            f"/api/moderation/proposals/{pending['proposal_id']}/review",
            {
                "decision": "approved",
                "version": pending["version"],
                "reason": "Proposta fittizia verificata",
            },
            True,
        )
        device_id = approved["device_id"]
        assert (
            client.get(f"/api/devices/{device_id}/status").json()["community"] is None
        )
        output = io.BytesIO()
        Image.new("RGB", (80, 60), (40, 60, 100)).save(output, format="PNG")
        body = output.getvalue()
        photo = post(
            "/api/photos/uploads",
            {
                "device_id": device_id,
                "content_type": "image/png",
                "size_bytes": len(body),
            },
        )
        form = photo["upload"]
        if form["method"] == "PUT":
            upload = client.put(form["url"], content=body, headers=headers)
        else:
            upload = client.post(
                form["url"],
                data=form["fields"],
                files={"file": ("fixture.png", body, "image/png")},
            )
        upload.raise_for_status()
        completed = post(f"/api/photos/{photo['photo_id']}/complete")
        assert completed["status"] == "prepared"
        assert client.get(f"/api/photos/{photo['photo_id']}/image").status_code == 404
        report = post(
            f"/api/devices/{device_id}/reports",
            {
                "station_id": "demo-station",
                "status": "guasta",
                "photo_id": photo["photo_id"],
                "description": "Osservazione HTTP sintetica",
            },
        )
        assert report["device_id"] == device_id
        queue = client.get("/api/moderation/photo/queue", headers=mod).json()["items"]
        current = next(p for p in queue if p["photo_id"] == photo["photo_id"])
        post(
            f"/api/moderation/photos/{photo['photo_id']}/review",
            {
                "decision": "approved",
                "version": current["version"],
                "reason": "Fotografia fittizia verificata",
            },
            True,
        )
        assert client.get(f"/api/photos/{photo['photo_id']}/image").content.startswith(
            b"\xff\xd8"
        )
        source = post(
            "/api/moderation/sources",
            {
                "name": "Fonte HTTP fittizia",
                "url": "https://example.invalid/source",
                "meaning": "Una fixture non è un report GTT reale.",
                "synthetic": True,
            },
            True,
        )
        acquired = post(
            f"/api/moderation/sources/{source['source_id']}/fixture",
            {"content": "Stato fittizio: guasta"},
            True,
        )
        original = client.get(
            "/api/moderation/sources/original",
            params={"reference": acquired["reference"]},
            headers=mod,
        )
        original.raise_for_status()
        if "application/json" in original.headers["content-type"]:
            assert (
                client.get(original.json()["download_url"]).content
                == b"Stato fittizio: guasta"
            )
        else:
            assert original.content == b"Stato fittizio: guasta"
        post(
            "/api/moderation/interpretations",
            {
                "device_id": device_id,
                "acquisition_reference": acquired["reference"],
                "status": "guasta",
                "reason": "Interpretazione della fixture",
            },
            True,
        )
        stats = client.get("/api/stats/private", headers=headers).json()
        assert stats["alignment"]["percentage"] == 100
        assert any(s["device_id"] == device_id for s in stats["incidents"]["new_stops"])
        assert client.get("/api/feed").json()["items"][0]["photo_url"]
        print(
            json.dumps(
                {
                    "http_smoke": "passed",
                    "mode": health["mode"],
                    "device_id": device_id,
                    "photo_id": photo["photo_id"],
                    "source_id": source["source_id"],
                }
            )
        )


if __name__ == "__main__":
    main()
