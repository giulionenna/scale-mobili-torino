import json
import time
from datetime import UTC, datetime, timedelta

from fastapi.encoders import jsonable_encoder

from scale_mobili.domain import DomainError, percentage, timestamp
from scale_mobili.repository import WORK, record
from scale_mobili.store import ConcurrentWrite

SNAPSHOT = {"PK": "STATS#global", "SK": "CURRENT"}


def rebuild_snapshot(service, before_commit=None):
    """Eseguito dal worker: ricalcolo sostituibile dalle evidenze canoniche."""
    existing_work = service.store.get_core(WORK)
    work = existing_work or record(WORK, version=1)
    expected_work = int(existing_work["version"]) if existing_work else 0
    devices = service.catalog()
    comparable, stops, feed_count = [], [], 0
    now = datetime.now(UTC)
    for device in devices:
        device_id = device["escalator_id"]
        events = service.all_events(device_id)
        reports = {e["event_id"]: dict(e) for e in events if e["kind"] == "report"}
        for event in sorted(events, key=lambda e: (e["recorded_at"], e["event_id"])):
            if event["kind"] == "correction" and event["target_event_id"] in reports:
                reports[event["target_event_id"]]["status"] = event["status"]
        ordered = sorted(
            reports.values(), key=lambda r: (r["observed_at"], r["recorded_at"]), reverse=True
        )
        feed_count += len(ordered)
        community = ordered[0] if ordered else None
        official = service.store.get_state(device_id).get("official")
        if (
            official
            and community
            and "non_verificabile" not in {official["status"], community["status"]}
        ):
            comparable.append(
                {
                    "device_id": device_id,
                    "station_id": device["station_id"],
                    "name": device["name"],
                    "community_status": community["status"],
                    "observed_at": community["observed_at"],
                    "official": official,
                    "aligned": official["status"] == community["status"],
                }
            )
        sequence = []
        for report in ordered:
            if report["status"] not in {"guasta", "manutenzione"}:
                break
            sequence.append(report)
        if sequence:
            first = sequence[-1]
            observed = datetime.fromisoformat(first["observed_at"].replace("Z", "+00:00"))
            stops.append(
                {
                    "device_id": device_id,
                    "station_id": device["station_id"],
                    "name": device["name"],
                    "kind": device.get("kind", "scala_mobile"),
                    "status": sequence[0]["status"],
                    "observation_count": len(sequence),
                    "first_observed_at": first["observed_at"],
                    "latest_observed_at": sequence[0]["observed_at"],
                    "first_known": len(sequence) == len(ordered),
                    "new_in_24h": now - timedelta(hours=24) <= observed <= now,
                    "continuous_duration": None,
                }
            )
    previous = service.store.get_core(SNAPSHOT)
    version = int(previous["version"]) if previous else 0
    aligned = sum(row["aligned"] for row in comparable)
    item = record(
        SNAPSHOT,
        version=version + 1,
        generated_at=timestamp(),
        evidence_version=int(work["version"]),
        total=len(devices),
        report_count=feed_count,
        alignment={
            "percentage": percentage(aligned, len(comparable)),
            "aligned": aligned,
            "comparable": len(comparable),
            "excluded": len(devices) - len(comparable),
            "method": "exact_latest_known_status_equality",
            "items": comparable,
        },
        incidents={
            "new_stops": [s for s in stops if s["new_in_24h"]],
            "streaks": sorted(
                [s for s in stops if s["observation_count"] >= 2],
                key=lambda s: s["observation_count"],
                reverse=True,
            ),
            "method": "consecutive_corrected_observations_not_continuous_outage",
        },
        catalog_consistency="eventually_consistent_station_index",
        synthetic_devices=sum(bool(d.get("synthetic")) for d in devices),
        temporal_gaps="unknown",
    )
    if len(json.dumps(jsonable_encoder(item), ensure_ascii=False).encode()) > 350000:
        raise DomainError("Dettagli aggregati oltre il limite del record del prototipo", 503)
    if before_commit:
        before_commit()
    try:
        service.store.transact(
            [(item, version), ({**work, "done_version": int(work["version"])}, expected_work)],
            invalidate=False,
        )
    except ConcurrentWrite:
        return {"completed": False, "reason": "Evidence changed; work remains pending"}
    return {"completed": True, "generated_at": item["generated_at"], "total": item["total"]}


def get_snapshot(service):
    item = service.store.get_core(SNAPSHOT)
    if not item:
        raise DomainError("Statistiche non ancora disponibili: eseguire il ricalcolo", 503)
    work = service.store.get_core(WORK) or {"version": 0}
    generated = datetime.fromisoformat(item["generated_at"].replace("Z", "+00:00")).timestamp()
    pending = int(work["version"]) != int(item["evidence_version"])
    stale = time.time() - generated > service.settings.snapshot_max_age_seconds
    return {
        k: v
        for k, v in {
            **item,
            "pending_recalculation": pending,
            "stale": stale,
            "snapshot": True,
        }.items()
        if k not in {"PK", "SK"}
    }
