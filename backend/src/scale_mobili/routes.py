from fastapi import Depends, Header, Query, Request
from fastapi.responses import Response

from scale_mobili.aggregates import rebuild_snapshot
from scale_mobili.auth import authenticate, oauth_scopes
from scale_mobili.domain import (
    CorrectionInput,
    DeviceReportInput,
    FavoriteStationsInput,
    InterpretationInput,
    MergeDeviceInput,
    PhotoUploadInput,
    ProposalInput,
    ReviewInput,
    SourceFixtureInput,
    SourceInput,
    StationMoveInput,
)


def register_routes(app, service, settings):
    def current_actor(authorization: str | None = Header(None)):
        return authenticate(authorization, settings)

    actor_dependency = Depends(current_actor)

    @app.get("/api/config")
    def configuration():
        return {
            "mode": settings.mode,
            "cognito_domain": settings.cognito_domain,
            "cognito_client_id": settings.cognito_client_id,
            "resource": settings.public_url.rstrip("/") + "/mcp",
            "scopes": ["openid", *oauth_scopes(settings)],
        }

    @app.get("/api/me")
    def me(actor=actor_dependency):
        return {
            "id": actor.id,
            "moderator": actor.moderator,
            "administrator": actor.administrator,
            "scopes": sorted(actor.scopes),
        }

    @app.get("/api/me/favorite-stations")
    def favorite_stations(actor=actor_dependency):
        return service.favorite_stations(actor)

    @app.put("/api/me/favorite-stations")
    def save_favorite_stations(
        body: FavoriteStationsInput,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        return service.save_favorite_stations(body, actor, idempotency_key)

    @app.get("/api/stations/{station_id}/devices")
    def devices(station_id: str):
        return {"items": service.devices(station_id)}

    @app.get("/api/devices/{device_id}")
    def device(device_id: str):
        meta = service.require_escalator(device_id)
        return {
            "device_id": device_id,
            **{
                k: meta.get(k)
                for k in (
                    "escalator_id",
                    "station_id",
                    "name",
                    "kind",
                    "location",
                    "synthetic",
                    "version",
                )
            },
        }

    @app.get("/api/devices/{device_id}/status")
    def device_status(device_id: str):
        return service.status(device_id)

    @app.get("/api/devices/{device_id}/history")
    def device_history(
        device_id: str, cursor: str | None = None, limit: int = Query(20, ge=1, le=100)
    ):
        return service.history(device_id, cursor, limit)

    @app.post("/api/devices/{device_id}/reports", status_code=201)
    def device_report(
        device_id: str,
        body: DeviceReportInput,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        return service.submit(device_id, body, actor, idempotency_key)

    @app.get("/api/feed")
    def feed(cursor: str | None = None, limit: int = Query(20, ge=1, le=100)):
        return service.feed(cursor, limit)

    @app.post("/api/devices/{device_id}/corrections", status_code=201)
    def correct(
        device_id: str,
        body: CorrectionInput,
        reference: str,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        return service.submit(device_id, body, actor, idempotency_key, "correction", reference)

    @app.post("/api/devices/{device_id}/confirmations", status_code=201)
    def confirm(
        device_id: str,
        reference: str,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        return service.submit(device_id, None, actor, idempotency_key, "confirmation", reference)

    @app.post("/api/moderation/devices/{device_id}/station")
    def move_device(
        device_id: str,
        body: StationMoveInput,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        return service.move_device(device_id, body, actor, idempotency_key)

    @app.post("/api/moderation/devices/{device_id}/merge")
    def merge_device(
        device_id: str,
        body: MergeDeviceInput,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        return service.merge_device(device_id, body, actor, idempotency_key)

    @app.get("/api/stats/availability")
    def availability():
        return service.availability()

    @app.get("/api/overview")
    def overview():
        return service.public_overview()

    @app.get("/api/stats/private")
    def private_statistics(actor=actor_dependency):
        return service.private_statistics(actor)

    @app.post("/api/proposals", status_code=201)
    def propose(
        body: ProposalInput,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        return service.propose(body, actor, idempotency_key)

    @app.get("/api/me/proposals")
    def own_proposals(
        cursor: str | None = None,
        limit: int = Query(20, ge=1, le=100),
        actor=actor_dependency,
    ):
        return service.own_proposals(actor, cursor, limit)

    @app.get("/api/moderation/{kind}/queue")
    def queue(
        kind: str,
        cursor: str | None = None,
        limit: int = Query(20, ge=1, le=100),
        actor=actor_dependency,
    ):
        return service.queue(kind, actor, cursor, limit)

    @app.post("/api/moderation/proposals/{proposal_id}/review")
    def review_proposal(
        proposal_id: str,
        body: ReviewInput,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        return service.review_proposal(proposal_id, body, actor, idempotency_key)

    @app.post("/api/photos/uploads", status_code=201)
    def reserve_photo(
        body: PhotoUploadInput,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        return service.reserve_photo(body, actor, idempotency_key)

    @app.put("/api/photos/{photo_id}/upload", status_code=204)
    async def upload_demo(photo_id: str, request: Request, actor=actor_dependency):
        service.upload_demo_photo(photo_id, actor, await request.body())
        return Response(status_code=204)

    @app.post("/api/photos/{photo_id}/complete")
    def finish_photo(
        photo_id: str, actor=actor_dependency, idempotency_key: str | None = Header(None)
    ):
        return service.finish_photo(photo_id, actor, idempotency_key)

    @app.post("/api/moderation/photos/{photo_id}/review")
    def review_photo(
        photo_id: str,
        body: ReviewInput,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        return service.review_photo(photo_id, body, actor, idempotency_key)

    @app.get("/api/moderation/photos/{photo_id}")
    def photo_review_metadata(photo_id: str, actor=actor_dependency):
        service.moderator(actor)
        return service.photo_metadata(service.photo_for_owner(photo_id, actor))

    @app.get("/api/photos/{photo_id}/preview")
    def preview(photo_id: str, actor=actor_dependency):
        return Response(service.photo_bytes(photo_id, actor), media_type="image/jpeg")

    @app.get("/api/photos/{photo_id}/image")
    def public_photo(photo_id: str):
        return Response(service.photo_bytes(photo_id), media_type="image/jpeg")

    @app.get("/api/sources")
    def sources():
        return {"items": service.sources()}

    @app.post("/api/moderation/sources", status_code=201)
    def register_source(
        body: SourceInput, actor=actor_dependency, idempotency_key: str | None = Header(None)
    ):
        return service.register_source(body, actor, idempotency_key)

    @app.post("/api/moderation/sources/{source_id}/acquire")
    def acquire_source(
        source_id: str, actor=actor_dependency, idempotency_key: str | None = Header(None)
    ):
        return service.collect_source(source_id, actor, idempotency_key)

    @app.post("/api/moderation/interpretations", status_code=201)
    def interpret(
        body: InterpretationInput,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        return service.interpret_source(body, actor, idempotency_key)

    @app.post("/api/moderation/sources/{source_id}/fixture")
    def source_fixture(
        source_id: str,
        body: SourceFixtureInput,
        actor=actor_dependency,
        idempotency_key: str | None = Header(None),
    ):
        return service.source_fixture(source_id, body, actor, idempotency_key)

    @app.get("/api/moderation/sources/original")
    def original(reference: str, actor=actor_dependency):
        blob = service.original_source(reference, actor)
        url = service.blobs.download_url(service.sources_bucket, blob["object_key"])
        if url:
            return {"download_url": url, "expires_in": 60, "content_hash": blob["content_hash"]}
        return Response(
            service.blobs.get(service.sources_bucket, blob["object_key"])[0],
            media_type="application/octet-stream",
            headers={"Content-Disposition": "attachment"},
        )

    @app.post("/api/moderation/statistics/rebuild")
    def rebuild(actor=actor_dependency):
        service.moderator(actor)
        return rebuild_snapshot(service)
