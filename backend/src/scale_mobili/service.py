import base64
import hashlib
import hmac
import json
import secrets
import time
from uuid import uuid4

from scale_mobili.domain import Actor, DomainError, public_event, timestamp
from scale_mobili.store import ConcurrentWrite


class Service:
    def __init__(self, store, cursor_secret=""):
        self.store = store
        self.secret = (cursor_secret or secrets.token_hex(32)).encode()

    def _encode(self, value):
        payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
        signature = hmac.new(self.secret, payload, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(payload + signature).decode().rstrip("=")

    def _decode(self, token):
        try:
            if len(token) > 2048:
                raise ValueError()
            raw = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True)
            payload, signature = raw[:-32], raw[-32:]
            if not hmac.compare_digest(
                signature, hmac.new(self.secret, payload, hashlib.sha256).digest()
            ):
                raise ValueError()
            return json.loads(payload)
        except (ValueError, TypeError) as exc:
            raise DomainError("Riferimento o cursore non valido") from exc

    def require_escalator(self, escalator_id):
        e = self.store.get_escalator(escalator_id)
        if not e or not e.get("confirmed"):
            raise DomainError("Impianto confermato non trovato", 404)
        return e

    def stations(self):
        return [
            {k: s.get(k) for k in ("station_id", "name", "synthetic")}
            for s in self.store.list_stations()
        ]

    def escalators(self, station_id):
        return [
            {
                k: e.get(k)
                for k in (
                    "escalator_id",
                    "station_id",
                    "name",
                    "synthetic",
                    "official_id",
                    "operator",
                )
            }
            for e in self.store.list_escalators(station_id)
        ]

    def status(self, escalator_id):
        e = self.require_escalator(escalator_id)
        state = self.store.get_state(escalator_id)
        community = state.get("community")
        if community:
            community = {
                **community,
                "report_count": int(community["report_count"]),
                "account_count": int(community["account_count"]),
            }
        return {
            "escalator_id": escalator_id,
            "synthetic": e.get("synthetic", False),
            "official": None,
            "community": community,
            "estimate": None,
            "missing_reason": "Nessuna informazione disponibile"
            if not state.get("community")
            else None,
            "generated_at": timestamp(),
            "url": f"/impianto?id={escalator_id}",
        }

    def history(self, escalator_id, cursor=None, limit=20):
        self.require_escalator(escalator_id)
        if not 1 <= limit <= 100:
            raise DomainError("Il limite deve essere tra 1 e 100")
        upper, after = timestamp(), None
        if cursor:
            data = self._decode(cursor)
            if data.get("kind") != "history" or data.get("escalator_id") != escalator_id:
                raise DomainError("Il cursore appartiene a un'altra richiesta")
            if data.get("expires_at", 0) <= int(time.time()):
                raise DomainError("Cursore scaduto")
            upper, after = data["upper"], data["after"]
        events, after = self.store.history(escalator_id, upper, after, limit)
        items = [
            {
                **public_event(e),
                "reference": self._encode(
                    {
                        "kind": "event",
                        "escalator_id": escalator_id,
                        "recorded_at": e["recorded_at"],
                        "event_id": e["event_id"],
                    }
                ),
            }
            for e in events
        ]
        return {
            "items": items,
            "next_cursor": self._encode(
                {
                    "kind": "history",
                    "escalator_id": escalator_id,
                    "upper": upper,
                    "after": after,
                    "expires_at": int(time.time()) + 3600,
                }
            )
            if after
            else None,
            "order": "recorded_at_ascending",
            "upper_bound": upper,
            "snapshot": False,
        }

    def _target(self, escalator_id, reference):
        data = self._decode(reference)
        if data.get("kind") != "event" or data.get("escalator_id") != escalator_id:
            raise DomainError("Il riferimento appartiene a un altro impianto")
        target = self.store.get_event(escalator_id, data["recorded_at"], data["event_id"])
        if not target or target["kind"] != "report":
            raise DomainError("Segnalazione originale non trovata", 404)
        return target

    def submit(
        self, escalator_id, payload, actor: Actor, request_key, kind="report", target_reference=None
    ):
        if "reports:write" not in actor.scopes:
            raise DomainError("Scope reports:write richiesto", 403)
        if not request_key or not 8 <= len(request_key) <= 128:
            raise DomainError("Idempotency-Key richiede da 8 a 128 caratteri")
        body = payload.model_dump(mode="json") if payload else {}
        digest = hashlib.sha256(
            json.dumps(
                {"escalator": escalator_id, "kind": kind, "target": target_reference, "body": body},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        now = int(time.time())
        previous = self.store.get_idempotency(actor.id, request_key)
        if previous and previous["expires_at"] > now:
            if previous["digest"] != digest:
                raise DomainError("Chiave di idempotenza già usata con contenuto diverso", 409)
            return previous["result"]
        meta = self.require_escalator(escalator_id)
        if kind == "report" and payload.station_id and payload.station_id != meta["station_id"]:
            raise DomainError("L'impianto non appartiene alla stazione indicata")
        target = self._target(escalator_id, target_reference) if target_reference else None
        if (
            kind == "correction"
            and target
            and target["actor_id"] != actor.id
            and not actor.moderator
        ):
            raise DomainError("Puoi rettificare solo le tue segnalazioni", 403)
        escalator_id = meta["escalator_id"]
        event = {
            "event_id": str(uuid4()),
            "escalator_id": escalator_id,
            "kind": kind,
            "actor_id": actor.id,
            "recorded_at": timestamp(),
            "observed_at": timestamp(payload.observed_at)
            if kind == "report"
            else target["observed_at"],
            "synthetic": meta.get("synthetic", False),
            "station_id": meta["station_id"],
            "device_id": escalator_id,
        }
        if kind != "confirmation":
            event["status"] = body["status"]
        if kind == "report":
            event["description"] = body.get("description", "")
            if body.get("photo_id"):
                event["photo_id"] = body["photo_id"]
        if target:
            event["target_event_id"] = target["event_id"]
            event["target_pk"], event["target_sk"] = (
                f"ESC#{target['escalator_id']}",
                f"EVENT#{target['recorded_at']}#{target['event_id']}",
            )
        if kind == "correction":
            event["reason"] = body["reason"]
        for _attempt in range(4):
            previous = self.store.get_idempotency(actor.id, request_key)
            if previous and previous["expires_at"] > now:
                if previous["digest"] != digest:
                    raise DomainError("Chiave di idempotenza già usata con contenuto diverso", 409)
                return previous["result"]
            state = self.store.get_state(escalator_id)
            events = self.all_events(escalator_id)
            if len(events) >= getattr(getattr(self, "settings", None), "max_device_events", 1000):
                raise DomainError(
                    "Storico al limite del prototipo: serve elaborazione asincrona", 409
                )
            current = self._project([*events, event])
            new_state = {**state, "version": int(state["version"]) + 1, "community": current}
            result = {
                **public_event(event),
                "reference": self._encode(
                    {
                        "kind": "event",
                        "escalator_id": escalator_id,
                        "recorded_at": event["recorded_at"],
                        "event_id": event["event_id"],
                    }
                ),
            }
            receipt = {
                "version": int(previous.get("version", 0)) + 1 if previous else 1,
                "digest": digest,
                "result": result,
                "expires_at": now + 86400,
            }
            try:
                self.store.commit(
                    event, new_state, int(state["version"]), actor.id, request_key, receipt, now
                )
                return result
            except ConcurrentWrite:
                continue
        raise DomainError("Scrittura concorrente: ritenta con la stessa chiave", 409)

    def all_events(self, escalator_id, upper=None):
        upper = upper or timestamp()
        events, after = self.store.history(escalator_id, upper, None, 100)
        while after and len(events) < 1000:
            page, after = self.store.history(escalator_id, upper, after, 100)
            events.extend(page)
        if after:
            raise DomainError("Serve un ricalcolo asincrono oltre il limite della prova", 409)
        return events

    @staticmethod
    def _project(events):
        reports = {e["event_id"]: dict(e) for e in events if e["kind"] == "report"}
        for e in sorted(events, key=lambda e: (e["recorded_at"], e["event_id"])):
            if e["kind"] == "correction" and e["target_event_id"] in reports:
                reports[e["target_event_id"]]["status"] = e["status"]
                reports[e["target_event_id"]]["corrected_at"] = e["recorded_at"]
        if not reports:
            return None
        latest = max(reports.values(), key=lambda e: (e["observed_at"], e["recorded_at"]))
        return {
            "status": latest["status"],
            "observed_at": latest["observed_at"],
            "recorded_at": latest["recorded_at"],
            "event_id": latest["event_id"],
            "corrected_at": latest.get("corrected_at"),
            "source": "community",
            "report_count": len(reports),
            "account_count": len({e["actor_id"] for e in reports.values()}),
        }
