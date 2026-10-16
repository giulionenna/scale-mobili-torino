import hashlib
import json
import time
from uuid import NAMESPACE_URL, uuid4, uuid5

from scale_mobili.catalog import CatalogMixin
from scale_mobili.domain import DomainError, percentage, public_event, timestamp
from scale_mobili.keys import favorite_stations_key, idempotency_key
from scale_mobili.photos import sanitize_photo
from scale_mobili.repository import record
from scale_mobili.service import Service
from scale_mobili.sources import SourcesMixin
from scale_mobili.store import ConcurrentWrite


def entity(kind, identifier):
    return {"PK": f"{kind}#{identifier}", "SK": "META"}


def event_record(parent, kind, actor, event_id, recorded_at, **fields):
    return record(
        {"PK": parent, "SK": f"EVENT#{recorded_at}#{event_id}"},
        event_id=event_id,
        entity_type="event",
        kind=kind,
        actor_id=actor.id,
        recorded_at=recorded_at,
        **fields,
    )


class PlatformService(CatalogMixin, SourcesMixin, Service):
    def __init__(self, store, settings, blobs):
        super().__init__(store, settings.cursor_secret)
        self.settings, self.blobs = settings, blobs
        self.photos_bucket = settings.photos_bucket or "demo-photos"
        self.sources_bucket = settings.sources_bucket or "demo-sources"

    @staticmethod
    def require_scope(actor, scope="reports:write"):
        if scope not in actor.scopes:
            raise DomainError(f"Scope {scope} richiesto", 403)

    def moderator(self, actor):
        self.require_scope(actor)
        if not actor.moderator:
            raise DomainError("Operazione riservata al moderatore", 403)

    def station(self, station_id):
        value = self.store.get_core({"PK": "CATALOG#STATIONS", "SK": "STATION#" + station_id})
        if not value:
            raise DomainError("Stazione non trovata", 404)
        return value

    def _write(self, actor, request_key, operation, body, factory, *, invalidate=True):
        self.require_scope(actor)
        if not request_key or not 8 <= len(request_key) <= 128:
            raise DomainError("Idempotency-Key richiede da 8 a 128 caratteri")
        digest = hashlib.sha256(
            json.dumps([operation, body], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        receipt_key = idempotency_key(actor.id, request_key)
        now, when, event_id = int(time.time()), timestamp(), str(uuid4())
        for _ in range(4):
            previous = self.store.get_core(receipt_key)
            if previous and previous["expires_at"] > now:
                if previous["digest"] != digest:
                    raise DomainError("Chiave di idempotenza già usata con contenuto diverso", 409)
                return previous["result"]
            puts, events, checks, result = factory(event_id, when)
            version = int(previous.get("version", 1)) if previous else 0
            receipt = record(
                receipt_key,
                version=version + 1,
                digest=digest,
                result=result,
                expires_at=now + 86400,
            )
            try:
                self.store.transact(
                    [*puts, (receipt, version)], events, checks, actor, invalidate=invalidate
                )
                return result
            except ConcurrentWrite:
                continue
        raise DomainError("Scrittura concorrente: ritenta con la stessa chiave", 409)

    def favorite_stations(self, actor):
        item = self.store.get_core(favorite_stations_key(actor.id)) or {}
        return {"station_ids": item.get("station_ids", []), "version": int(item.get("version", 0))}

    def save_favorite_stations(self, payload, actor, request_key):
        def factory(event_id, when):
            current = self.favorite_stations(actor)
            if current["version"] != payload.version:
                raise DomainError(
                    "Preferiti modificati da un'altra sessione: ricarica e riprova", 409
                )
            ids = sorted(set(payload.station_ids))
            stations = [self.station(identifier) for identifier in ids]
            result = {"station_ids": ids, "version": payload.version + 1}
            item = record(favorite_stations_key(actor.id), **result, updated_at=when)
            return (
                [(item, payload.version)],
                [],
                [(station, int(station.get("version", 1))) for station in stations],
                result,
            )

        return self._write(
            actor,
            request_key,
            "favorite_stations",
            payload.model_dump(mode="json"),
            factory,
            invalidate=False,
        )

    def _page(self, scope, actor, cursor, limit, loader):
        if not 1 <= limit <= 100:
            raise DomainError("Il limite deve essere tra 1 e 100")
        after = None
        if cursor:
            decoded = self._decode(cursor)
            if (
                decoded.get("kind") != scope
                or decoded.get("actor") != actor
                or decoded.get("expires_at", 0) <= int(time.time())
            ):
                raise DomainError("Cursore scaduto o appartenente a un'altra richiesta")
            after = decoded.get("after")
        items, after = loader(after)
        return {
            "items": items,
            "next_cursor": self._encode(
                {
                    "kind": scope,
                    "actor": actor,
                    "after": after,
                    "expires_at": int(time.time()) + 3600,
                }
            )
            if after
            else None,
            "snapshot": False,
        }

    def devices(self, station_id):
        self.station(station_id)
        return [
            {
                **item,
                "device_id": item["escalator_id"],
                "kind": item.get("kind", "scala_mobile"),
                "location": item.get("location", ""),
            }
            for item in self.escalators(station_id)
        ]

    def escalators(self, station_id):
        # Rimuove chiavi fisiche e attributi privati mantenendo gli ID già pubblicati.
        return [
            {
                k: e.get(k)
                for k in (
                    "escalator_id",
                    "station_id",
                    "name",
                    "kind",
                    "location",
                    "synthetic",
                    "official_id",
                    "operator",
                    "version",
                )
            }
            for e in self.store.list_escalators(station_id)
        ]

    def status(self, device_id):
        requested_id = device_id
        device_id = self.resolve_device(device_id)["escalator_id"]
        result = super().status(device_id)
        result["requested_device_id"] = requested_id
        result["device_id"] = device_id
        result["official"] = self.store.get_state(device_id).get("official")
        result["missing_reason"] = (
            "Nessuna informazione disponibile"
            if not result["community"] and not result["official"]
            else None
        )
        return result

    def submit(self, device_id, payload, actor, request_key, kind="report", target_reference=None):
        if kind == "report" and payload.photo_id:
            photo = self.store.get_core(entity("PHOTO", payload.photo_id))
            if (
                not photo
                or photo["actor_id"] != actor.id
                or not photo.get("device_id")
                or self.resolve_device(photo["device_id"])["escalator_id"]
                != self.resolve_device(device_id)["escalator_id"]
            ):
                raise DomainError("Foto non disponibile per questo utente e impianto", 403)
        return super().submit(device_id, payload, actor, request_key, kind, target_reference)

    def propose(self, payload, actor, request_key):
        proposal_id = str(uuid4())

        def factory(event_id, when):
            station = self.station(payload.station_id)
            item = record(
                entity("PROPOSAL", proposal_id),
                **payload.model_dump(),
                proposal_id=proposal_id,
                actor_id=actor.id,
                status="pending",
                version=1,
                created_at=when,
                synthetic=station.get("synthetic", False),
                review_pk="REVIEW#proposal#PENDING",
                review_sk=when + "#" + proposal_id,
            )
            event = event_record(
                item["PK"], "proposal_created", actor, event_id, when, proposal_id=proposal_id
            )
            return (
                [(item, 0)],
                [event],
                [(station, int(station.get("version", 1)))],
                self._proposal(item),
            )

        return self._write(actor, request_key, "propose", payload.model_dump(mode="json"), factory)

    @staticmethod
    def _proposal(item):
        return {
            k: v
            for k, v in item.items()
            if k not in {"PK", "SK", "actor_id", "review_pk", "review_sk"}
        }

    def own_proposals(self, actor, cursor=None, limit=20):
        def load(after):
            events, last = self.store.page_actor(actor.id, timestamp(), limit, after)
            ids = {e["proposal_id"] for e in events if e.get("kind") == "proposal_created"}
            items = [self.store.get_core(entity("PROPOSAL", identifier)) for identifier in ids]
            return [self._proposal(p) for p in items if p and p["actor_id"] == actor.id], last

        return self._page("own_proposals", actor.id, cursor, limit, load)

    def queue(self, kind, actor, cursor=None, limit=20):
        self.moderator(actor)
        if kind not in {"proposal", "photo"}:
            raise DomainError("Coda non valida")

        def load(after):
            items, last = self.store.page_core(
                f"REVIEW#{kind}#PENDING", limit=limit, after=after, index="review_queue"
            )
            return [
                self._proposal(item) if kind == "proposal" else self.photo_metadata(item)
                for item in items
                if item.get("status") == "pending"
            ], last

        return self._page("queue:" + kind, actor.id, cursor, limit, load)

    def review_proposal(self, proposal_id, payload, actor, request_key):
        self.moderator(actor)

        def factory(event_id, when):
            item = self.store.get_core(entity("PROPOSAL", proposal_id))
            if not item:
                raise DomainError("Proposta non trovata", 404)
            if item["status"] != "pending" or int(item["version"]) != payload.version:
                raise DomainError("Proposta già modificata: ricarica la coda", 409)
            updated = {k: v for k, v in item.items() if k not in {"review_pk", "review_sk"}}
            updated.update(status=payload.decision, version=payload.version + 1, reviewed_at=when)
            puts, checks = [], []
            if payload.decision == "approved":
                station = self.station(item["station_id"])
                checks.append((station, int(station.get("version", 1))))
                device_id = str(uuid5(NAMESPACE_URL, "scale-mobili:proposal:" + proposal_id))
                updated["device_id"] = device_id
                device = record(
                    entity("ESC", device_id),
                    escalator_id=device_id,
                    station_id=item["station_id"],
                    kind=item["kind"],
                    name=item["name"],
                    location=item["location"],
                    confirmed=True,
                    synthetic=item["synthetic"],
                    official_id=None,
                    operator=None,
                    version=1,
                    station_pk="STATION#" + item["station_id"],
                    station_sk="ESC#" + device_id,
                )
                puts.append((device, 0))
                if item.get("photo_id"):
                    photo = self.store.get_core(entity("PHOTO", item["photo_id"]))
                    if photo and photo["status"] == "prepared":
                        puts.append(
                            (
                                {
                                    **photo,
                                    "device_id": device_id,
                                    "status": "pending",
                                    "version": int(photo["version"]) + 1,
                                    "review_pk": "REVIEW#photo#PENDING",
                                    "review_sk": photo["created_at"] + "#" + photo["photo_id"],
                                },
                                int(photo["version"]),
                            )
                        )
            event = event_record(
                item["PK"],
                "proposal_reviewed",
                actor,
                event_id,
                when,
                proposal_id=proposal_id,
                decision=payload.decision,
                reason=payload.reason,
            )
            return [*puts, (updated, payload.version)], [event], checks, self._proposal(updated)

        return self._write(
            actor,
            request_key,
            "review_proposal:" + proposal_id,
            payload.model_dump(mode="json"),
            factory,
        )

    @staticmethod
    def photo_metadata(photo):
        return {
            k: photo.get(k)
            for k in (
                "photo_id",
                "device_id",
                "proposal_id",
                "status",
                "version",
                "created_at",
                "processed_at",
                "width",
                "height",
            )
        }

    def reserve_photo(self, payload, actor, request_key):
        photo_id = str(uuid4())

        def factory(event_id, when):
            parent = (
                self.require_escalator(payload.device_id)
                if payload.device_id
                else self.store.get_core(entity("PROPOSAL", payload.proposal_id))
            )
            if not parent or (payload.proposal_id and parent["actor_id"] != actor.id):
                raise DomainError("Impianto o proposta non disponibile", 403)
            if payload.proposal_id and parent["status"] == "rejected":
                raise DomainError("Proposta respinta", 409)
            item = record(
                entity("PHOTO", photo_id),
                **payload.model_dump(),
                photo_id=photo_id,
                actor_id=actor.id,
                status="uploading",
                version=1,
                created_at=when,
                expires_at=int(time.time()) + 3600,
                object_key="uploads/" + photo_id,
            )
            checks = (
                [
                    (
                        record(
                            entity("ESC", payload.device_id),
                            **{k: v for k, v in parent.items() if k not in {"PK", "SK"}},
                        ),
                        int(parent.get("version", 1)),
                    )
                ]
                if payload.device_id
                else [(parent, int(parent["version"]))]
            )
            return [(item, 0)], [], checks, self.photo_metadata(item)

        result = self._write(
            actor, request_key, "reserve_photo", payload.model_dump(mode="json"), factory
        )
        item = self.store.get_core(entity("PHOTO", result["photo_id"]))
        if item["status"] != "uploading" or item["expires_at"] <= int(time.time()):
            raise DomainError("Upload scaduto o già completato", 409)
        form = self.blobs.upload_form(
            self.photos_bucket, item["object_key"], item["content_type"], int(item["size_bytes"])
        )
        if self.settings.mode == "demo":
            form["url"] = "/api/photos/" + result["photo_id"] + "/upload"
        return {
            **result,
            "upload": form,
            "expires_in": min(600, item["expires_at"] - int(time.time())),
        }

    def photo_for_owner(self, photo_id, actor):
        photo = self.store.get_core(entity("PHOTO", photo_id))
        if not photo or (photo["actor_id"] != actor.id and not actor.moderator):
            raise DomainError("Foto non disponibile", 404)
        return photo

    def upload_demo_photo(self, photo_id, actor, body):
        self.require_scope(actor)
        if self.settings.mode != "demo":
            raise DomainError("Usare l'upload S3 autorizzato", 404)
        photo = self.photo_for_owner(photo_id, actor)
        if photo["status"] != "uploading" or photo["expires_at"] <= int(time.time()):
            raise DomainError("Upload scaduto o completato", 409)
        if len(body) != photo["size_bytes"]:
            raise DomainError("Dimensione diversa da quella dichiarata")
        self.blobs.put(self.photos_bucket, photo["object_key"], body, photo["content_type"])

    def finish_photo(self, photo_id, actor, request_key):
        def factory(event_id, when):
            photo = self.photo_for_owner(photo_id, actor)
            if photo["status"] != "uploading":
                raise DomainError("Foto già elaborata", 409)
            if photo["expires_at"] <= int(time.time()):
                raise DomainError("Upload scaduto", 409)
            body, _ = self.blobs.get(self.photos_bucket, photo["object_key"], 5 * 1024 * 1024)
            if len(body) != photo["size_bytes"]:
                raise DomainError("Dimensione del file diversa da quella dichiarata")
            clean, width, height = sanitize_photo(body)
            key = "sanitized/" + photo_id + "/" + hashlib.sha256(clean).hexdigest() + ".jpg"
            self.blobs.put(self.photos_bucket, key, clean, "image/jpeg")
            updated = {k: v for k, v in photo.items() if k != "expires_at"}
            updated.update(
                status="prepared",
                version=int(photo["version"]) + 1,
                sanitized_key=key,
                width=width,
                height=height,
                processed_at=when,
            )
            puts = []
            if photo.get("proposal_id"):
                proposal = self.store.get_core(entity("PROPOSAL", photo["proposal_id"]))
                if (
                    not proposal
                    or proposal["actor_id"] != actor.id
                    or proposal["status"] == "rejected"
                    or proposal.get("photo_id")
                ):
                    raise DomainError("Proposta non disponibile per questa foto", 409)
                puts.append(
                    (
                        {**proposal, "photo_id": photo_id, "version": int(proposal["version"]) + 1},
                        int(proposal["version"]),
                    )
                )
                if proposal["status"] == "approved":
                    updated.update(
                        status="pending",
                        device_id=proposal["device_id"],
                        review_pk="REVIEW#photo#PENDING",
                        review_sk=photo["created_at"] + "#" + photo_id,
                    )
            return [*puts, (updated, int(photo["version"]))], [], [], self.photo_metadata(updated)

        result = self._write(actor, request_key, "finish_photo:" + photo_id, {}, factory)
        photo = self.photo_for_owner(photo_id, actor)
        self.blobs.delete(self.photos_bucket, photo["object_key"])
        return result

    def review_photo(self, photo_id, payload, actor, request_key):
        self.moderator(actor)

        def factory(event_id, when):
            photo = self.photo_for_owner(photo_id, actor)
            allowed = photo["status"] == "pending" or (
                photo["status"] == "approved" and payload.decision == "rejected"
            )
            if not allowed or int(photo["version"]) != payload.version:
                raise DomainError("Foto già modificata: ricarica la coda", 409)
            device = self.require_escalator(photo["device_id"])
            updated = {k: v for k, v in photo.items() if k not in {"review_pk", "review_sk"}}
            updated.update(status=payload.decision, version=payload.version + 1, reviewed_at=when)
            event = event_record(
                "ESC#" + photo["device_id"],
                "photo_reviewed",
                actor,
                event_id,
                when,
                escalator_id=photo["device_id"],
                photo_id=photo_id,
                decision=payload.decision,
                reason=payload.reason,
            )
            check = (
                record(
                    entity("ESC", photo["device_id"]),
                    **{
                        k: v
                        for k, v in self.store.get_escalator(photo["device_id"]).items()
                        if k not in {"PK", "SK"}
                    },
                ),
                int(self.store.get_escalator(photo["device_id"]).get("version", 1)),
            )
            checks = [check]
            if device["escalator_id"] != photo["device_id"]:
                checks.append(
                    (
                        record(
                            entity("ESC", device["escalator_id"]),
                            **{k: v for k, v in device.items() if k not in {"PK", "SK"}},
                        ),
                        int(device["version"]),
                    )
                )
            return [(updated, payload.version)], [event], checks, self.photo_metadata(updated)

        return self._write(
            actor, request_key, "review_photo:" + photo_id, payload.model_dump(mode="json"), factory
        )

    def photo_bytes(self, photo_id, actor=None):
        photo = self.store.get_core(entity("PHOTO", photo_id))
        if not photo:
            raise DomainError("Foto non disponibile", 404)
        if actor:
            self.photo_for_owner(photo_id, actor)
        elif photo["status"] != "approved" or not photo.get("device_id"):
            raise DomainError("Foto non disponibile", 404)
        if not photo.get("sanitized_key"):
            raise DomainError("Foto non elaborata", 409)
        if not actor:
            self.require_escalator(photo["device_id"])
        return self.blobs.get(self.photos_bucket, photo["sanitized_key"], 1024 * 1024)[0]

    def feed(self, cursor=None, limit=20):
        def load(after):
            rows, last = self.store.page_core(
                "FEED#REPORTS", limit=limit, after=after, descending=True
            )
            items = []
            for row in rows:
                item = public_event(row)
                if row.get("photo_id"):
                    photo = self.store.get_core(entity("PHOTO", row["photo_id"]))
                    if photo and photo["status"] == "approved":
                        item["photo_url"] = "/api/photos/" + photo["photo_id"] + "/image"
                items.append(item)
            return items, last

        return self._page("feed", None, cursor, limit, load)

    def catalog(self):
        result = []
        for station in self.store.list_stations():
            result.extend(self.store.list_escalators(station["station_id"]))
            if len(result) > self.settings.max_catalog_devices:
                raise DomainError("Censimento oltre il limite del prototipo", 503)
        return result

    def availability(self):
        devices = self.catalog()
        states = [self.store.get_state(d["escalator_id"]).get("community") for d in devices]
        return self._availability(devices, states)

    def public_overview(self):
        devices = [
            device for station in self.stations() for device in self.devices(station["station_id"])
        ]
        if len(devices) > self.settings.max_catalog_devices:
            raise DomainError("Censimento oltre il limite del prototipo", 503)
        states = {device["device_id"]: self.status(device["device_id"]) for device in devices}
        return {
            "stations": self.stations(),
            "devices": devices,
            "states": states,
            "availability": self._availability(
                devices, [state["community"] for state in states.values()]
            ),
        }

    @staticmethod
    def _availability(devices, states):
        working = sum(bool(s and s["status"] == "funzionante") for s in states)
        return {
            "total": len(devices),
            "working": working,
            "percentage": percentage(working, len(devices)),
            "observed_devices": sum(s is not None for s in states),
            "method": "latest_community_observation_over_catalog",
            "catalog_consistency": "eventually_consistent_station_index",
            "synthetic": all(d.get("synthetic", False) for d in devices) if devices else False,
            "generated_at": timestamp(),
            "continuous_availability": False,
        }

    def private_statistics(self, actor):
        self.require_scope(actor, "stats:read")
        from scale_mobili.aggregates import get_snapshot, rebuild_snapshot

        if self.settings.mode != "aws":
            rebuild_snapshot(self)
        return get_snapshot(self)
