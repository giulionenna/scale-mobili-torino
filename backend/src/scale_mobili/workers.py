from uuid import uuid4

from scale_mobili.aggregates import rebuild_snapshot
from scale_mobili.config import get_settings
from scale_mobili.domain import Actor
from scale_mobili.platform import PlatformService
from scale_mobili.runtime import build_runtime


def service():
    settings = get_settings()
    store, blobs = build_runtime(settings)
    return PlatformService(store, settings, blobs)


def aggregate_handler(event, context):
    return rebuild_snapshot(service())


def collector_handler(event, context):
    svc = service()
    actor = Actor(id="system:source-collector", moderator=True, scopes=frozenset({"reports:write"}))
    execution = str(event.get("execution_id") or uuid4())[:64]
    outcomes = []
    for source in svc.sources():
        if source["synthetic"]:
            continue
        result = svc.collect_source(
            source["source_id"], actor, "collect:" + execution + ":" + source["source_id"]
        )
        outcomes.append({"source_id": source["source_id"], "outcome": result["outcome"]})
    return {"acquisitions": outcomes}
