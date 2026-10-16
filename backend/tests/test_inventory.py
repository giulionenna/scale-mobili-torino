import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest

from scale_mobili.blobs import MemoryBlobs
from scale_mobili.domain import DomainError, ReportInput
from scale_mobili.inventory import import_inventory
from scale_mobili.keys import ACTIVE_CATALOG
from scale_mobili.platform import PlatformService
from scale_mobili.store import DynamoStore


@pytest.fixture
def census():
    return json.loads(
        (Path(__file__).resolve().parents[2] / "data/torino-m1-2026-10-16.json").read_text()
    )


def test_inventory_complete_documented_and_without_states(store, settings, census, actor):
    svc = PlatformService(store, settings, MemoryBlobs())
    original = svc.submit("demo-esc-1", ReportInput(status="guasta"), actor, "keep-demo-history")
    dry = import_inventory(store, census)
    assert dry["records_to_create"] == 238
    assert store.get_core(ACTIVE_CATALOG) is None
    assert all(station["synthetic"] for station in svc.stations())
    result = import_inventory(store, census, apply=True)
    assert result["devices"] == 215
    assert len(svc.stations()) == 23
    assert svc.stations()[0]["name"] == "Fermi"
    assert svc.stations()[-1]["name"] == "Bengasi"
    overview = svc.public_overview()
    assert len(overview["devices"]) == 215
    assert sum(d["kind"] == "scala_mobile" for d in overview["devices"]) == 142
    assert sum(d["kind"] == "ascensore" for d in overview["devices"]) == 73
    assert overview["availability"]["total"] == 215
    assert overview["availability"]["observed_devices"] == 0
    assert overview["availability"]["synthetic"] is False
    assert all(
        s["community"] is None and s["official"] is None for s in overview["states"].values()
    )
    assert all(d["inventory_evidence"]["page"] for d in overview["devices"])
    assert import_inventory(store, census, apply=True)["records_to_create"] == 0
    assert svc.history("demo-esc-1")["items"][0]["event_id"] == original["event_id"]
    assert svc.feed()["items"] == []
    assert all(not d["synthetic"] for d in svc.catalog())


def test_partial_import_stays_hidden_and_resumes(store, settings, census, monkeypatch):
    svc = PlatformService(store, settings, MemoryBlobs())
    transact = store.transact
    attempts = 0

    def interrupted(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 26:
            raise RuntimeError("simulated interruption")
        transact(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(store, "transact", interrupted)
        with pytest.raises(RuntimeError, match="interruption"):
            import_inventory(store, census, apply=True)
    assert store.get_core(ACTIVE_CATALOG) is None
    assert all(station["synthetic"] for station in svc.stations())
    assert import_inventory(store, census, apply=True)["records_to_create"] == 213
    assert len(svc.public_overview()["devices"]) == 215


def test_inventory_collision_does_not_overwrite_or_start_import(store, census):
    from scale_mobili.inventory import prepare_inventory

    collision = prepare_inventory(census)[-1]
    store.transact([({**collision, "inventory_dataset": "different-import"}, 0)])
    with pytest.raises(DomainError, match="Collisione"):
        import_inventory(store, census, apply=True)
    first = census["stations"][0]["station_id"]
    assert store.get_core({"PK": "CATALOG#STATIONS", "SK": "STATION#" + first}) is None
    assert store.get_core(ACTIVE_CATALOG) is None


def test_changed_dataset_and_duplicate_identity_are_rejected(store, census):
    import_inventory(store, census, apply=True)
    altered = deepcopy(census)
    altered["devices"][0]["name"] = "Changed"
    with pytest.raises(DomainError, match="contenuto diverso"):
        import_inventory(store, altered, apply=True)
    altered = deepcopy(census)
    altered["devices"][0]["device_id"] = str(uuid4())
    altered["dataset_id"] = "another-dataset"
    # Nuove revisioni richiedono un percorso esplicito, non una sostituzione implicita.
    with pytest.raises(DomainError, match="revisione esplicita"):
        import_inventory(store, altered, apply=True)


def test_inventory_does_not_accept_status_or_missing_provenance(store, census):
    census["devices"][0]["status"] = "funzionante"
    with pytest.raises(DomainError, match="contenente stati"):
        import_inventory(store, census, apply=True)
    del census["devices"][0]["status"]
    del census["devices"][0]["inventory_evidence"]["document_sha256"]
    with pytest.raises(DomainError, match="provenienza"):
        import_inventory(store, census, apply=True)
    assert store.get_core(ACTIVE_CATALOG) is None


def test_overview_reads_states_in_batches_without_per_device_status(
    store, settings, census, monkeypatch
):
    import_inventory(store, census, apply=True)
    svc = PlatformService(store, settings, MemoryBlobs())

    def forbidden(*args):
        raise AssertionError("status individuale nella panoramica")

    monkeypatch.setattr(svc, "status", forbidden)
    overview = svc.public_overview()
    assert len(overview["states"]) == 215


def test_batch_reads_retry_only_unprocessed_keys_and_fail_closed(monkeypatch):
    import scale_mobili.store as module

    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    keys = [{"PK": f"ESC#{n}", "SK": "META"} for n in range(215)]
    calls = []

    class Table:
        name = "core"

    class Resource:
        def batch_get_item(self, RequestItems):
            request = RequestItems["core"]
            assert request["ConsistentRead"] is True
            batch = request["Keys"]
            calls.append(batch)
            if len(calls) == 1:
                return {
                    "Responses": {"core": batch[1:]},
                    "UnprocessedKeys": {"core": {**request, "Keys": batch[:1]}},
                }
            return {"Responses": {"core": batch}, "UnprocessedKeys": {}}

    store = object.__new__(DynamoStore)
    store.core, store.resource = Table(), Resource()
    assert len(store.batch_core(keys)) == 215
    assert [len(batch) for batch in calls] == [100, 1, 100, 15]

    def incomplete(RequestItems):
        return {"Responses": {}, "UnprocessedKeys": RequestItems}

    monkeypatch.setattr(store.resource, "batch_get_item", incomplete)
    with pytest.raises(DomainError, match="incompleta"):
        store.batch_core(keys[:1])
