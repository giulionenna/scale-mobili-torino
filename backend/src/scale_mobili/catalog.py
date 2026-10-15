import time

from scale_mobili.domain import DomainError, public_event, timestamp
from scale_mobili.repository import record
from scale_mobili.service import Service


class CatalogMixin:
    def resolve_device(self, identifier):
        visited = set()
        for _ in range(21):
            if identifier in visited:
                raise DomainError("Ciclo di alias nel censimento", 503)
            visited.add(identifier)
            meta = self.store.get_escalator(identifier)
            if not meta:
                raise DomainError("Impianto non trovato", 404)
            if not meta.get("alias_of"):
                if not meta.get("confirmed"):
                    raise DomainError("Impianto confermato non trovato", 404)
                return meta
            identifier = meta["alias_of"]
        raise DomainError("Catena di alias oltre il limite del prototipo", 503)

    def require_escalator(self, identifier):
        return self.resolve_device(identifier)

    def aliases(self, canonical):
        rows, after = self.store.page_core("ALIAS#" + canonical, limit=100)
        if after:
            raise DomainError("Troppi alias nel prototipo", 503)
        return [r["alias_id"] for r in rows if r["canonical_id"] == canonical]

    def all_events(self, identifier, upper=None):
        canonical = self.resolve_device(identifier)["escalator_id"]
        upper = upper or timestamp()
        events = []
        for device_id in [canonical, *self.aliases(canonical)]:
            events.extend(Service.all_events(self, device_id, upper))
            if len(events) > self.settings.max_device_events:
                raise DomainError("Storico unificato oltre il limite del prototipo", 503)
        return events

    def history(self, identifier, cursor=None, limit=20):
        meta = self.resolve_device(identifier)
        canonical = meta["escalator_id"]
        if not 1 <= limit <= 100:
            raise DomainError("Il limite deve essere tra 1 e 100")
        upper, after = timestamp(), None
        if cursor:
            decoded = self._decode(cursor)
            if (
                decoded.get("kind") != "history"
                or decoded.get("escalator_id") != canonical
                or decoded.get("expires_at", 0) <= int(time.time())
                or decoded.get("catalog_version") != int(meta.get("version", 1))
            ):
                raise DomainError("Cursore scaduto o censimento modificato")
            upper, after = decoded["upper"], decoded["after"]
        events = sorted(
            self.all_events(canonical, upper), key=lambda e: (e["recorded_at"], e["event_id"])
        )
        events = [
            e for e in events if not after or (e["recorded_at"] + "#" + e["event_id"]) > after
        ]
        page = events[:limit]
        items = [
            {
                **public_event(e),
                "reference": self._encode(
                    {
                        "kind": "event",
                        "escalator_id": e["escalator_id"],
                        "recorded_at": e["recorded_at"],
                        "event_id": e["event_id"],
                    }
                ),
            }
            for e in page
        ]
        next_cursor = (
            self._encode(
                {
                    "kind": "history",
                    "escalator_id": canonical,
                    "catalog_version": int(meta.get("version", 1)),
                    "upper": upper,
                    "after": page[-1]["recorded_at"] + "#" + page[-1]["event_id"],
                    "expires_at": int(time.time()) + 3600,
                }
            )
            if len(events) > limit
            else None
        )
        return {
            "items": items,
            "next_cursor": next_cursor,
            "order": "recorded_at_ascending",
            "upper_bound": upper,
            "snapshot": False,
            "device_id": canonical,
            "aliases": self.aliases(canonical),
        }

    def _target(self, identifier, reference):
        decoded = self._decode(reference)
        if (
            decoded.get("kind") != "event"
            or self.resolve_device(decoded["escalator_id"])["escalator_id"]
            != self.resolve_device(identifier)["escalator_id"]
        ):
            raise DomainError("Il riferimento appartiene a un altro impianto")
        event = self.store.get_event(
            decoded["escalator_id"], decoded["recorded_at"], decoded["event_id"]
        )
        if not event or event["kind"] != "report":
            raise DomainError("Segnalazione originale non trovata", 404)
        return event

    def move_device(self, identifier, payload, actor, request_key):
        from scale_mobili.platform import entity, event_record

        self.moderator(actor)

        def factory(event_id, when):
            item = self.resolve_device(identifier)
            if item["escalator_id"] != identifier or int(item.get("version", 1)) != payload.version:
                raise DomainError("Impianto modificato: ricarica il censimento", 409)
            station = self.station(payload.station_id)
            if bool(station.get("synthetic")) != bool(item.get("synthetic")):
                raise DomainError("Non mescolare censimenti reali e sintetici")
            updated = {
                **item,
                **entity("ESC", identifier),
                "station_id": payload.station_id,
                "station_pk": "STATION#" + payload.station_id,
                "station_sk": "ESC#" + identifier,
                "version": payload.version + 1,
            }
            event = event_record(
                "ESC#" + identifier,
                "station_corrected",
                actor,
                event_id,
                when,
                escalator_id=identifier,
                previous_station_id=item["station_id"],
                station_id=payload.station_id,
                reason=payload.reason,
                synthetic=item["synthetic"],
            )
            return (
                [(updated, payload.version)],
                [event],
                [(station, int(station.get("version", 1)))],
                {
                    "device_id": identifier,
                    "station_id": payload.station_id,
                    "version": updated["version"],
                },
            )

        return self._write(
            actor,
            request_key,
            "move_device:" + identifier,
            payload.model_dump(mode="json"),
            factory,
        )

    def merge_device(self, identifier, payload, actor, request_key):
        from scale_mobili.platform import entity, event_record

        self.moderator(actor)

        def factory(event_id, when):
            duplicate = self.resolve_device(identifier)
            canonical = self.resolve_device(payload.canonical_device_id)
            if (
                duplicate["escalator_id"] != identifier
                or canonical["escalator_id"] != payload.canonical_device_id
                or identifier == payload.canonical_device_id
            ):
                raise DomainError("Identità canoniche non valide per la fusione", 409)
            if (
                int(duplicate.get("version", 1)) != payload.version
                or int(canonical.get("version", 1)) != payload.canonical_version
            ):
                raise DomainError("Censimento già modificato", 409)
            for field in ("station_id", "kind", "synthetic"):
                if duplicate.get(field) != canonical.get(field):
                    raise DomainError("La fusione richiede stessa stazione, tipo e natura dei dati")
            if (
                duplicate.get("official_id")
                and canonical.get("official_id")
                and duplicate["official_id"] != canonical["official_id"]
            ):
                raise DomainError(
                    "Identificativi ufficiali discordanti: verificare prima la fusione"
                )
            moved = [identifier, *self.aliases(identifier)]
            if len(moved) + len(self.aliases(payload.canonical_device_id)) > 20:
                raise DomainError("Oltre il limite di 20 alias del prototipo")
            puts = []
            for alias in moved:
                old = self.store.get_escalator(alias)
                puts.append(
                    (
                        {
                            **old,
                            **entity("ESC", alias),
                            "confirmed": False,
                            "alias_of": payload.canonical_device_id,
                            "version": int(old.get("version", 1)) + 1,
                        },
                        int(old.get("version", 1)),
                    )
                )
                puts.append(
                    (
                        record(
                            {"PK": "ALIAS#" + payload.canonical_device_id, "SK": "DEVICE#" + alias},
                            alias_id=alias,
                            canonical_id=payload.canonical_device_id,
                            version=1,
                        ),
                        0,
                    )
                )
            events = self.all_events(identifier) + self.all_events(payload.canonical_device_id)
            if len(events) >= self.settings.max_device_events:
                raise DomainError(
                    "La fusione supererebbe il limite dello storico del prototipo", 409
                )
            state = self.store.get_state(payload.canonical_device_id)
            updated_state = {
                **state,
                "PK": "ESC#" + payload.canonical_device_id,
                "SK": "STATE",
                "schema_version": 1,
                "version": int(state["version"]) + 1,
                "community": self._project(events),
            }
            official = [
                self.store.get_state(i).get("official")
                for i in [identifier, payload.canonical_device_id]
            ]
            official = [o for o in official if o]
            if official:
                updated_state["official"] = max(
                    official,
                    key=lambda o: (o.get("published_at") or o["acquired_at"], o["interpreted_at"]),
                )
            updated = {
                **canonical,
                **entity("ESC", payload.canonical_device_id),
                "version": payload.canonical_version + 1,
            }
            event = event_record(
                "ESC#" + payload.canonical_device_id,
                "devices_merged",
                actor,
                event_id,
                when,
                escalator_id=payload.canonical_device_id,
                alias_id=identifier,
                reason=payload.reason,
                synthetic=canonical["synthetic"],
            )
            duplicate_state = self.store.get_state(identifier)
            check = ({"PK": "ESC#" + identifier, "SK": "STATE"}, int(duplicate_state["version"]))
            return (
                [
                    *puts,
                    (updated, payload.canonical_version),
                    (updated_state, int(state["version"])),
                ],
                [event],
                [check],
                {
                    "device_id": payload.canonical_device_id,
                    "aliases": moved,
                    "version": updated["version"],
                },
            )

        return self._write(
            actor,
            request_key,
            "merge_device:" + identifier,
            payload.model_dump(mode="json"),
            factory,
        )
