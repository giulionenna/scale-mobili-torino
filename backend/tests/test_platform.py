import io
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image

from scale_mobili.aggregates import get_snapshot, rebuild_snapshot
from scale_mobili.blobs import MemoryBlobs
from scale_mobili.domain import (
    Actor,
    DeviceReportInput,
    DomainError,
    InterpretationInput,
    PhotoUploadInput,
    ProposalInput,
    ReportInput,
    ReviewInput,
    SourceInput,
)
from scale_mobili.platform import PlatformService, entity
from scale_mobili.repository import WORK, MemoryRepository


@pytest.fixture
def svc(store, settings):
    return PlatformService(store, settings, MemoryBlobs())


@pytest.fixture
def moderator():
    return Actor(
        id="demo-moderator", moderator=True, scopes=frozenset({"reports:write", "stats:read"})
    )


def proposal():
    return ProposalInput(
        station_id="demo-station",
        kind="ascensore",
        name="Ascensore di prova",
        location="Percorso fittizio est",
        description="Solo dati sintetici",
    )


def test_proposal_idempotency_approval_and_no_invented_state(svc, actor, moderator):
    first = svc.propose(proposal(), actor, "proposal-request")
    assert svc.propose(proposal(), actor, "proposal-request") == first
    assert len(svc.devices("demo-station")) == 2
    assert svc.own_proposals(actor)["items"][0]["proposal_id"] == first["proposal_id"]
    other = Actor(id="demo-user-2", scopes=actor.scopes)
    assert svc.own_proposals(other)["items"] == []
    review = ReviewInput(decision="approved", version=1, reason="Posizione fittizia verificata")
    with pytest.raises(DomainError, match="moderatore"):
        svc.review_proposal(first["proposal_id"], review, actor, "review-denied")
    result = svc.review_proposal(first["proposal_id"], review, moderator, "review-approved")
    assert svc.review_proposal(first["proposal_id"], review, moderator, "review-approved") == result
    assert len(svc.devices("demo-station")) == 3
    assert svc.status(result["device_id"])["community"] is None
    with pytest.raises(DomainError, match="modificata"):
        svc.review_proposal(first["proposal_id"], review, moderator, "another-review")
    assert svc.queue("proposal", moderator)["items"] == []


def test_rejection_and_cursor_isolation(svc, actor, moderator):
    first = svc.propose(proposal(), actor, "proposal-first")
    svc.propose(proposal(), actor, "proposal-second")
    page = svc.own_proposals(actor, limit=1)
    assert page["next_cursor"]
    with pytest.raises(DomainError, match="Cursore"):
        svc.own_proposals(Actor(id="another", scopes=actor.scopes), page["next_cursor"])
    with pytest.raises(DomainError, match="Cursore"):
        svc.queue("photo", moderator, page["next_cursor"])
    svc.review_proposal(
        first["proposal_id"],
        ReviewInput(decision="rejected", version=1, reason="Duplicato fittizio"),
        moderator,
        "reject-request",
    )
    assert len(svc.devices("demo-station")) == 2


def image():
    picture = Image.new("RGB", (80, 60), (40, 60, 100))
    exif = picture.getexif()
    exif[270] = "Private metadata must disappear"
    output = io.BytesIO()
    picture.save(output, format="JPEG", exif=exif)
    return output.getvalue()


def prepared_photo(svc, actor, **parent):
    body = image()
    upload = svc.reserve_photo(
        PhotoUploadInput(**parent, content_type="image/jpeg", size_bytes=len(body)),
        actor,
        "reserve-" + next(iter(parent)),
    )
    photo_id = upload["photo_id"]
    record = svc.store.get_core(entity("PHOTO", photo_id))
    svc.blobs.put(svc.photos_bucket, record["object_key"], body, "image/jpeg")
    result = svc.finish_photo(photo_id, actor, "complete-" + photo_id)
    assert svc.finish_photo(photo_id, actor, "complete-" + photo_id) == result
    assert (svc.photos_bucket, record["object_key"]) not in svc.blobs.objects
    return photo_id


def test_photo_sanitization_private_queue_and_publication(svc, actor, moderator):
    photo_id = prepared_photo(svc, actor, device_id="demo-esc-1")
    with pytest.raises(DomainError):
        svc.photo_bytes(photo_id)
    assert svc.queue("photo", moderator)["items"] == []
    clean = Image.open(io.BytesIO(svc.photo_bytes(photo_id, actor)))
    assert clean.size == (80, 60) and not clean.getexif()
    payload = DeviceReportInput(station_id="demo-station", status="guasta", photo_id=photo_id)
    report = svc.submit("demo-esc-1", payload, actor, "report-photo")
    assert svc.submit("demo-esc-1", payload, actor, "report-photo") == report
    assert "photo_url" not in svc.feed()["items"][0]
    with pytest.raises(DomainError):
        svc.submit("demo-esc-1", payload, actor, "second-report-photo")
    photo = svc.queue("photo", moderator)["items"][0]
    svc.review_photo(
        photo_id,
        ReviewInput(decision="approved", version=photo["version"], reason="Foto fittizia valida"),
        moderator,
        "photo-approved",
    )
    assert svc.photo_bytes(photo_id)
    assert svc.feed()["items"][0]["photo_url"].endswith("/image")
    assert "actor_id" not in svc.feed()["items"][0]
    current = svc.photo_metadata(svc.photo_for_owner(photo_id, moderator))
    svc.review_photo(
        photo_id,
        ReviewInput(
            decision="rejected",
            version=current["version"],
            reason="Ritiro della pubblicazione di prova",
        ),
        moderator,
        "photo-revoked",
    )
    with pytest.raises(DomainError):
        svc.photo_bytes(photo_id)
    assert "photo_url" not in svc.feed()["items"][0]


def test_proposal_photo_waits_for_catalog_approval(svc, actor, moderator):
    proposed = svc.propose(proposal(), actor, "proposal-with-photo")
    photo_id = prepared_photo(svc, actor, proposal_id=proposed["proposal_id"])
    assert svc.queue("photo", moderator)["items"] == []
    current = svc.own_proposals(actor)["items"][0]
    accepted = svc.review_proposal(
        proposed["proposal_id"],
        ReviewInput(
            decision="approved", version=current["version"], reason="Censimento fittizio valido"
        ),
        moderator,
        "approve-with-photo",
    )
    photo = svc.queue("photo", moderator)["items"][0]
    assert photo["device_id"] == accepted["device_id"] and photo["photo_id"] == photo_id
    svc.review_photo(
        photo_id,
        ReviewInput(
            decision="rejected", version=photo["version"], reason="Foto fittizia da respingere"
        ),
        moderator,
        "reject-photo",
    )
    with pytest.raises(DomainError):
        svc.photo_bytes(photo_id)


def test_invalid_file_and_owner_rejected(svc, actor):
    photo = svc.reserve_photo(
        PhotoUploadInput(device_id="demo-esc-1", content_type="image/png", size_bytes=8),
        actor,
        "invalid-file",
    )
    item = svc.store.get_core(entity("PHOTO", photo["photo_id"]))
    svc.blobs.put(svc.photos_bucket, item["object_key"], b"notimage", "image/png")
    with pytest.raises(DomainError, match="Foto non valida"):
        svc.finish_photo(photo["photo_id"], actor, "complete-invalid")
    with pytest.raises(DomainError):
        svc.photo_bytes(photo["photo_id"], Actor(id="other", scopes=actor.scopes))


def test_source_dedup_failure_and_explicit_interpretation(svc, actor, moderator):
    source = svc.register_source(
        SourceInput(
            name="Fonte fittizia",
            url="https://example.invalid/test",
            meaning="Il report descrive solo alcune manutenzioni, non il funzionamento generale.",
            synthetic=True,
        ),
        moderator,
        "create-source",
    )
    acquired = []
    for i, content in enumerate([b"one", b"one", b"two"]):
        acquired.append(
            svc.collect_source(
                source["source_id"],
                moderator,
                f"acquisition-{i}",
                fetcher=lambda _source, body=content: {"body": body, "content_type": "text/plain"},
            )
        )

    def failing(_source):
        raise OSError("Example failure")

    failed = svc.collect_source(source["source_id"], moderator, "acquisition-failed", failing)
    assert failed["outcome"] == "failed" and "content_hash" not in failed
    assert len([key for key in svc.blobs.objects if key[0] == svc.sources_bucket]) == 2
    assert acquired[0]["content_hash"] == acquired[1]["content_hash"] != acquired[2]["content_hash"]
    assert svc.status("demo-esc-1")["official"] is None
    evidence = svc.interpret_source(
        InterpretationInput(
            device_id="demo-esc-1",
            acquisition_reference=acquired[0]["reference"],
            status="guasta",
            reason="Interpretazione manuale fittizia",
        ),
        moderator,
        "interpret-source",
    )
    assert evidence["published_at"] is None and evidence["acquired_at"]
    assert svc.status("demo-esc-1")["official"]["status"] == "guasta"
    svc.submit("demo-esc-1", ReportInput(status="guasta"), actor, "same-community")
    assert svc.status("demo-esc-1")["official"]["status"] == "guasta"
    assert svc.private_statistics(actor)["alignment"]["percentage"] == 100


def test_real_source_never_attached_to_synthetic_device(svc, moderator):
    source = svc.register_source(
        SourceInput(
            name="GTT esempio di URL",
            url="https://www.gtt.to.it/cms/test",
            meaning="Fonte reale, contenuto simulato solo nel test.",
        ),
        moderator,
        "real-source-url",
    )
    acquired = svc.collect_source(
        source["source_id"],
        moderator,
        "mock-real-source",
        lambda _: {"body": b"mock original", "content_type": "text/plain"},
    )
    with pytest.raises(DomainError, match="reale"):
        svc.interpret_source(
            InterpretationInput(
                device_id="demo-esc-1",
                acquisition_reference=acquired["reference"],
                status="funzionante",
                reason="Must be rejected",
            ),
            moderator,
            "reject-cross-data",
        )
    with pytest.raises(DomainError):
        svc.register_source(
            SourceInput(
                name="Unsafe source",
                url="https://localhost/private",
                meaning="Source must not allow SSRF",
            ),
            moderator,
            "unsafe-source",
        )


def test_stats_out_of_order_streaks_recovery_and_invalidations(svc, actor):
    assert svc.availability()["percentage"] == 0
    assert svc.private_statistics(actor)["alignment"]["percentage"] is None
    now = datetime.now(UTC)
    for i in [3, 2]:
        svc.submit(
            "demo-esc-1",
            ReportInput(status="guasta", observed_at=now - timedelta(minutes=i)),
            actor,
            f"stop-report-{i}",
        )
    stats = svc.private_statistics(actor)
    assert stats["incidents"]["streaks"][0]["observation_count"] == 2
    assert stats["incidents"]["new_stops"][0]["continuous_duration"] is None
    svc.submit(
        "demo-esc-1",
        ReportInput(status="funzionante", observed_at=now - timedelta(minutes=1)),
        actor,
        "recovered-device",
    )
    svc.submit(
        "demo-esc-1",
        ReportInput(status="guasta", observed_at=now - timedelta(days=2)),
        actor,
        "late-older-report",
    )
    assert svc.availability()["percentage"] == 50
    assert svc.private_statistics(actor)["incidents"]["streaks"] == []

    def concurrent():
        svc.submit("demo-esc-2", ReportInput(status="guasta"), actor, "during-rebuild")

    assert not rebuild_snapshot(svc, concurrent)["completed"]
    assert get_snapshot(svc)["pending_recalculation"]
    assert rebuild_snapshot(svc)["completed"]
    assert not get_snapshot(svc)["pending_recalculation"]
    assert int(svc.store.get_core(WORK)["done_version"]) == int(svc.store.get_core(WORK)["version"])


def test_parallel_proposal_retry_and_distributed_quota(settings, actor):
    svc = PlatformService(MemoryRepository(write_limit=2), settings, MemoryBlobs())
    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(
            pool.map(lambda _: svc.propose(proposal(), actor, "same-parallel-proposal"), range(8))
        )
    assert len({p["proposal_id"] for p in values}) == 1
    svc.propose(proposal(), actor, "next-proposal")
    with pytest.raises(DomainError) as caught:
        svc.propose(proposal(), actor, "quota-exhausted")
    assert caught.value.status_code == 429


def test_station_correction_keeps_id_and_rejects_stale_index(svc, actor, moderator):
    from scale_mobili.domain import StationMoveInput
    from scale_mobili.repository import record

    svc.store.transact(
        [
            (
                record(
                    {"PK": "CATALOG#STATIONS", "SK": "STATION#demo-other"},
                    station_id="demo-other",
                    name="Altra stazione fittizia",
                    synthetic=True,
                    version=1,
                ),
                0,
            )
        ]
    )
    reported = svc.submit(
        "demo-esc-1",
        ReportInput(status="guasta", station_id="demo-station"),
        actor,
        "before-station-move",
    )
    moved = svc.move_device(
        "demo-esc-1",
        StationMoveInput(
            station_id="demo-other", version=1, reason="Associazione fittizia rettificata"
        ),
        moderator,
        "move-device-station",
    )
    assert moved["device_id"] == "demo-esc-1"
    assert not any(d["device_id"] == "demo-esc-1" for d in svc.devices("demo-station"))
    assert svc.devices("demo-other")[0]["device_id"] == "demo-esc-1"
    assert (
        svc.submit(
            "demo-esc-1",
            ReportInput(status="guasta", station_id="demo-station"),
            actor,
            "before-station-move",
        )
        == reported
    )
    with pytest.raises(DomainError):
        svc.submit(
            "demo-esc-1",
            ReportInput(status="guasta", station_id="demo-station"),
            actor,
            "invalid-old-station",
        )
    assert svc.history("demo-esc-1")["items"][0]["station_id"] == "demo-station"


def test_merge_preserves_originals_and_alias_correction(svc, actor, moderator):
    from scale_mobili.domain import CorrectionInput, MergeDeviceInput

    p = proposal().model_copy(update={"kind": "scala_mobile"})
    pending = svc.propose(p, actor, "duplicate-proposal")
    accepted = svc.review_proposal(
        pending["proposal_id"],
        ReviewInput(decision="approved", version=1, reason="Fixture di duplicato"),
        moderator,
        "duplicate-approved",
    )
    duplicate = accepted["device_id"]
    older = datetime.now(UTC) - timedelta(minutes=5)
    svc.submit(
        "demo-esc-1", ReportInput(status="guasta", observed_at=older), actor, "canonical-old-report"
    )
    original = svc.submit(
        duplicate, ReportInput(status="funzionante"), actor, "duplicate-latest-report"
    )
    merged = svc.merge_device(
        duplicate,
        MergeDeviceInput(
            canonical_device_id="demo-esc-1",
            version=1,
            canonical_version=1,
            reason="Stessa scala fittizia verificata",
        ),
        moderator,
        "merge-duplicate",
    )
    assert duplicate in merged["aliases"] and len(svc.devices("demo-station")) == 2
    assert svc.status(duplicate)["device_id"] == "demo-esc-1"
    assert svc.status("demo-esc-1")["community"]["status"] == "funzionante"
    assert len([r for r in svc.history(duplicate)["items"] if r["kind"] == "report"]) == 2
    assert (
        svc.submit(duplicate, ReportInput(status="funzionante"), actor, "duplicate-latest-report")
        == original
    )
    svc.submit(
        "demo-esc-1",
        CorrectionInput(status="guasta", reason="Rettifica dopo la fusione"),
        actor,
        "correct-merged-report",
        "correction",
        original["reference"],
    )
    assert svc.status(duplicate)["community"]["status"] == "guasta"
    assert svc.private_statistics(actor)["total"] == 2
    assert len([r for r in svc.history("demo-esc-1")["items"] if r["kind"] == "report"]) == 2


def test_favorite_stations_private_persistent_idempotent_and_no_observation(svc, actor, settings):
    from scale_mobili.domain import FavoriteStationsInput

    other = Actor(id="another-user", scopes=actor.scopes)
    payload = FavoriteStationsInput(station_ids=["demo-station", "demo-station"], version=0)
    before = svc.store.get_core(WORK)
    result = svc.save_favorite_stations(payload, actor, "favorites-first")
    assert result == {"station_ids": ["demo-station"], "version": 1}
    assert svc.save_favorite_stations(payload, actor, "favorites-first") == result
    restarted = PlatformService(svc.store, settings, MemoryBlobs())
    assert restarted.favorite_stations(actor) == result
    assert restarted.favorite_stations(other) == {"station_ids": [], "version": 0}
    assert svc.store.get_core(WORK) == before
    assert svc.status("demo-esc-1")["community"] is None
    assert not svc.store.history("demo-esc-1", "9999", None, 10)[0]
    with pytest.raises(DomainError, match="modificati"):
        svc.save_favorite_stations(payload, actor, "favorites-stale")
    with pytest.raises(DomainError, match="diverso"):
        svc.save_favorite_stations(
            FavoriteStationsInput(station_ids=[], version=1), actor, "favorites-first"
        )
    with pytest.raises(DomainError, match="Scope"):
        svc.save_favorite_stations(payload, Actor(id="no-scope"), "favorites-denied")
    with pytest.raises(DomainError, match="Stazione"):
        svc.save_favorite_stations(
            FavoriteStationsInput(station_ids=["missing"], version=1), actor, "favorites-missing"
        )
    assert svc.favorite_stations(actor) == result
    assert svc.save_favorite_stations(
        FavoriteStationsInput(station_ids=[], version=1), actor, "favorites-remove"
    ) == {"station_ids": [], "version": 2}


def test_favorites_concurrent_sessions_cannot_overwrite(svc, actor):
    from scale_mobili.domain import FavoriteStationsInput

    def save(index):
        try:
            return svc.save_favorite_stations(
                FavoriteStationsInput(station_ids=["demo-station"] if index else [], version=0),
                actor,
                f"favorites-concurrent-{index}",
            )
        except DomainError as error:
            assert error.status_code == 409
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, range(2)))
    assert sum(value is not None for value in results) == 1
    assert svc.favorite_stations(actor)["version"] == 1
