import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from scale_mobili.domain import Actor, CorrectionInput, DomainError, ReportInput
from scale_mobili.keys import idempotency_key
from scale_mobili.service import Service
from scale_mobili.store import ConcurrentWrite, MemoryStore


def test_missing_is_distinct_from_unverifiable(store, actor):
    svc = Service(store)
    assert svc.status("demo-esc-1")["community"] is None
    svc.submit("demo-esc-1", ReportInput(status="non_verificabile"), actor, "report-first")
    assert svc.status("demo-esc-1")["community"]["status"] == "non_verificabile"
    assert svc.status("demo-esc-1")["official"] is None


def test_idempotency_and_conflicting_content(store, actor):
    svc = Service(store)
    payload = ReportInput(status="guasta")
    first = svc.submit("demo-esc-1", payload, actor, "same-request")
    assert svc.submit("demo-esc-1", payload, actor, "same-request") == first
    assert len(svc.history("demo-esc-1")["items"]) == 1
    with pytest.raises(DomainError, match="contenuto diverso"):
        svc.submit("demo-esc-1", ReportInput(status="funzionante"), actor, "same-request")


def test_expiry_checked_even_before_ttl_cleanup(actor):
    store = MemoryStore()
    svc = Service(store)
    first = svc.submit("demo-esc-1", ReportInput(status="guasta"), actor, "same-request")
    store.idempotency[idempotency_key(actor.id, "same-request")["PK"]]["expires_at"] = (
        int(time.time()) - 1
    )
    second = svc.submit("demo-esc-1", ReportInput(status="guasta"), actor, "same-request")
    assert first["event_id"] != second["event_id"]


def test_correction_keeps_original_and_enforces_ownership(store, actor):
    svc = Service(store)
    first = svc.submit("demo-esc-1", ReportInput(status="guasta"), actor, "first-report")
    other = Actor(id="other", scopes=actor.scopes)
    correction = CorrectionInput(status="funzionante", reason="Errore nella prima osservazione")
    with pytest.raises(DomainError, match="solo le tue"):
        svc.submit(
            "demo-esc-1", correction, other, "bad-correction", "correction", first["reference"]
        )
    svc.submit("demo-esc-1", correction, actor, "good-correction", "correction", first["reference"])
    items = svc.history("demo-esc-1")["items"]
    assert items[0]["status"] == "guasta"
    assert items[1]["target_event_id"] == first["event_id"]
    assert svc.status("demo-esc-1")["community"]["status"] == "funzionante"
    assert all("actor_id" not in event and "reason" not in event for event in items)


def test_late_report_and_correction_do_not_override_newer_observation(store, actor):
    svc = Service(store)
    now = datetime.now(UTC)
    svc.submit(
        "demo-esc-1", ReportInput(status="funzionante", observed_at=now), actor, "new-observed"
    )
    old = svc.submit(
        "demo-esc-1",
        ReportInput(status="guasta", observed_at=now - timedelta(days=1)),
        actor,
        "old-observed",
    )
    assert svc.status("demo-esc-1")["community"]["status"] == "funzionante"
    svc.submit(
        "demo-esc-1",
        CorrectionInput(status="manutenzione", reason="Correzione vecchia"),
        actor,
        "old-correction",
        "correction",
        old["reference"],
    )
    assert svc.status("demo-esc-1")["community"]["status"] == "funzionante"


def test_confirmation_is_not_a_new_status(store, actor):
    svc = Service(store)
    first = svc.submit("demo-esc-1", ReportInput(status="guasta"), actor, "first-report")
    svc.submit("demo-esc-1", None, actor, "confirmation", "confirmation", first["reference"])
    assert svc.status("demo-esc-1")["community"]["report_count"] == 1
    assert svc.history("demo-esc-1")["items"][1]["kind"] == "confirmation"


def test_history_cursor_bound_to_escalator_and_signed(store, actor):
    svc = Service(store)
    for i in range(3):
        svc.submit("demo-esc-1", ReportInput(status="guasta"), actor, f"report-{i:03}")
    first = svc.history("demo-esc-1", limit=1)
    cursor = first["next_cursor"]
    assert cursor
    with pytest.raises(DomainError):
        svc.history("demo-esc-2", cursor)
    with pytest.raises(DomainError):
        svc.history("demo-esc-1", cursor[:-8] + "tampered")
    # Una nuova registrazione non deve entrare nelle pagine successive.
    svc.submit("demo-esc-1", ReportInput(status="funzionante"), actor, "report-later")
    rest = svc.history("demo-esc-1", cursor, limit=100)
    assert len(rest["items"]) == 2
    assert rest["upper_bound"] == first["upper_bound"]
    assert rest["snapshot"] is False


def test_scope_and_unknown_escalator(store, actor):
    svc = Service(store)
    with pytest.raises(DomainError, match="Scope"):
        svc.submit("demo-esc-1", ReportInput(status="guasta"), Actor(id="no-scope"), "bad-request")
    with pytest.raises(DomainError, match="non trovato"):
        svc.submit("invented-official-id", ReportInput(status="guasta"), actor, "bad-request")


def test_validation_rejects_forged_actor_naive_date_and_future():
    for payload in [
        {"status": "guasta", "actor_id": "someone-else"},
        {"status": "guasta", "observed_at": "2026-01-01T12:00:00"},
        {"status": "guasta", "observed_at": datetime.now(UTC) + timedelta(days=1)},
    ]:
        with pytest.raises(ValidationError):
            ReportInput(**payload)


def test_retry_same_event_after_concurrent_write(store, actor, monkeypatch):
    svc = Service(store)
    original = store.commit
    event_ids = []

    def conflict_once(event, *args):
        event_ids.append(event["event_id"])
        if len(event_ids) == 1:
            raise ConcurrentWrite()
        return original(event, *args)

    monkeypatch.setattr(store, "commit", conflict_once)
    result = svc.submit("demo-esc-1", ReportInput(status="guasta"), actor, "same-request")
    assert event_ids == [result["event_id"], result["event_id"]]
    assert len(svc.history("demo-esc-1")["items"]) == 1


def test_parallel_retries_do_not_duplicate(actor):
    svc = Service(MemoryStore())
    payload = ReportInput(status="guasta")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: svc.submit("demo-esc-1", payload, actor, "parallel-key"), range(8))
        )
    assert len({r["event_id"] for r in results}) == 1
    assert len(svc.history("demo-esc-1")["items"]) == 1


def test_base_record_protects_against_stale_station_index(store):
    if not isinstance(store, MemoryStore):
        # Lascia volutamente station_pk vecchio per simulare una voce GSI arretrata.
        store.core.update_item(
            Key={"PK": "ESC#demo-esc-1", "SK": "META"},
            UpdateExpression="SET station_id = :new, confirmed = :no",
            ExpressionAttributeValues={":new": "other-station", ":no": False},
        )
        assert "demo-esc-1" not in {
            e["escalator_id"] for e in store.list_escalators("demo-station")
        }
