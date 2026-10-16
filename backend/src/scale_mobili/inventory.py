"""Importazione amministrativa additiva di un censimento documentato, senza stati."""

import hashlib
import json
import time
from uuid import UUID

from scale_mobili.domain import DomainError, timestamp
from scale_mobili.keys import ACTIVE_CATALOG, inventory_identity_key
from scale_mobili.repository import record


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def current_records(store, keys):
    if hasattr(store, "batch_core"):
        return store.batch_core(keys)
    return {
        (key["PK"], key["SK"]): item for key in keys if (item := store.get_core(key)) is not None
    }


def prepare_inventory(dataset):
    if dataset.get("schema_version") != 1 or dataset.get("status_included") is not False:
        raise DomainError("Il censimento deve contenere identità documentate, senza stati")
    stations, devices = dataset["stations"], dataset["devices"]
    ids = [s["station_id"] for s in stations]
    device_ids = [d["device_id"] for d in devices]
    identities = [(d["kind"], d["official_id"].replace(" ", "")) for d in devices]
    if not stations or not devices or len(devices) > 2000:
        raise DomainError("Dimensione del censimento non valida")
    if len(set(ids)) != len(ids) or len(set(device_ids)) != len(device_ids):
        raise DomainError("ID interni duplicati nel censimento")
    if len(set(identities)) != len(identities):
        raise DomainError("Matricole duplicate nel censimento")
    for identifier in [*ids, *device_ids]:
        UUID(identifier)
    entries = []
    for station in stations:
        if station.get("synthetic") is not False or not station.get("source_url"):
            raise DomainError("Stazione reale priva di fonte")
        entries.append(
            record(
                {"PK": "CATALOG#STATIONS", "SK": "STATION#" + station["station_id"]},
                **station,
                version=1,
            )
        )
    for device in devices:
        evidence = device.get("inventory_evidence", {})
        if (
            device["station_id"] not in ids
            or device.get("synthetic") is not False
            or device["kind"] not in {"scala_mobile", "ascensore"}
            or not evidence.get("url", "").startswith("https://gtt-to.acquistitelematici.it/")
            or len(evidence.get("document_sha256", "")) != 64
            or not evidence.get("page")
            or any(field in device for field in ("status", "community", "official", "estimate"))
        ):
            raise DomainError("Impianto senza provenienza valida o contenente stati")
        entries.append(
            record(
                {"PK": "ESC#" + device["device_id"], "SK": "META"},
                **{k: v for k, v in device.items() if k != "device_id"},
                escalator_id=device["device_id"],
                station_pk="STATION#" + device["station_id"],
                station_sk="ESC#" + device["device_id"],
                confirmed=True,
                version=1,
            )
        )
    return [
        {**entry, "inventory_digest": digest(entry), "inventory_dataset": dataset["dataset_id"]}
        for entry in entries
    ]


def import_inventory(store, dataset, *, apply=False, write_delay=0):
    entries = prepare_inventory(dataset)
    dataset_id, fingerprint = dataset["dataset_id"], digest(dataset)
    manifest_key = {"PK": "CATALOG#IMPORTS", "SK": "DATASET#" + dataset_id}
    previous = store.get_core(manifest_key)
    active = store.get_core(ACTIVE_CATALOG)
    if previous and previous["dataset_sha256"] != fingerprint:
        raise DomainError("Versione del dataset già importata con contenuto diverso", 409)
    if active and active["dataset_id"] != dataset_id:
        raise DomainError("Censimento già attivo: preparare una revisione esplicita", 409)
    originals = current_records(
        store,
        [{k: entry[k] for k in ("PK", "SK")} for entry in entries]
        + [
            inventory_identity_key(device["kind"], device["official_id"])
            for device in dataset["devices"]
        ],
    )
    pending, checks = [], []
    # Tutte le collisioni vengono cercate prima della prima scrittura.
    existing_identities = {}
    for station in store.list_stations():
        for device in store.list_escalators(station["station_id"]):
            if not device.get("synthetic") and device.get("official_id"):
                key = (device["kind"], device["official_id"].replace(" ", ""))
                existing_identities[key] = device["escalator_id"]
    for entry in entries:
        old = originals.get((entry["PK"], entry["SK"]))
        if old and (
            old.get("synthetic") is not False
            or old.get("inventory_dataset") != dataset_id
            or old.get("inventory_digest") != entry["inventory_digest"]
        ):
            raise DomainError("Collisione con un record esistente: nessuna sovrascrittura", 409)
        if entry["PK"].startswith("ESC#"):
            identity = (entry["kind"], entry["official_id"].replace(" ", ""))
            if existing_identities.get(identity, entry["escalator_id"]) != entry["escalator_id"]:
                raise DomainError("Matricola già associata a un altro ID interno", 409)
            claim = record(
                inventory_identity_key(entry["kind"], entry["official_id"]),
                escalator_id=entry["escalator_id"],
                inventory_dataset=dataset_id,
                version=1,
            )
            current_claim = originals.get((claim["PK"], claim["SK"]))
            if current_claim and current_claim["escalator_id"] != entry["escalator_id"]:
                raise DomainError("Matricola già riservata da un altro impianto", 409)
            if not old:
                pending.append([(entry, 0), *([] if current_claim else [(claim, 0)])])
        elif not old:
            pending.append([(entry, 0)])
        checks.append((old or entry, int((old or entry)["version"])))
    result = {
        "dataset_id": dataset_id,
        "dataset_sha256": fingerprint,
        "stations": len(dataset["stations"]),
        "devices": len(dataset["devices"]),
        "records_to_create": len(pending),
        "states_to_create": 0,
        "deletions": 0,
        "applied": False,
    }
    if not apply:
        return result
    for puts in pending:
        now = timestamp()
        store.transact(
            [({**item, "inventory_recorded_at": now}, version) for item, version in puts],
            invalidate=False,
        )
        if write_delay:
            time.sleep(write_delay)
    # Un indice arretrato non deve attivare un censimento visibilmente incompleto.
    expected = {d["device_id"] for d in dataset["devices"]}
    for attempt in range(5):
        visible = {
            d["escalator_id"]
            for station in dataset["stations"]
            for d in store.list_escalators(station["station_id"])
        }
        if expected <= visible:
            break
        if attempt == 4:
            raise DomainError("Indice stazioni ancora incompleto: import salvato, ritentare", 503)
        time.sleep(0.2 * 2**attempt)
    if not previous:
        manifest = record(
            manifest_key, **{**result, "applied": True}, version=1, recorded_at=timestamp()
        )
        activation = record(
            ACTIVE_CATALOG,
            dataset_id=dataset_id,
            version=1,
            activated_at=timestamp(),
        )
        # Rilettura prima dell'attivazione; non è una snapshot atomica dei 238 metadata.
        current = current_records(
            store, [{k: entry[k] for k in ("PK", "SK")} for entry, _ in checks]
        )
        for entry, version in checks:
            original = current.get((entry["PK"], entry["SK"]))
            if not original or int(original["version"]) != version:
                raise DomainError("Censimento modificato durante l'import: verificare", 409)
        store.transact([(manifest, 0), (activation, 0)])
    return {**result, "applied": True, "active": True}
