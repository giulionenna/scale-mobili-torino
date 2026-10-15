import hashlib
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from scale_mobili.domain import DomainError, timestamp
from scale_mobili.repository import record


def fetch_source(source):
    """Un solo URL verificato; redirect vietati e lettura limitata a 10 MB."""
    headers = {"User-Agent": "ScaleMobiliTorino/0.2 civic-prototype"}
    if source.get("etag"):
        headers["If-None-Match"] = source["etag"]
    if source.get("last_modified"):
        headers["If-Modified-Since"] = source["last_modified"]
    with httpx.Client(timeout=10, follow_redirects=False) as client:
        with client.stream("GET", source["url"], headers=headers) as response:
            if response.status_code == 304:
                return {"not_modified": True}
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > 10 * 1024 * 1024:
                    raise DomainError("Fonte oltre il limite di 10 MB", 413)
            return {
                "body": bytes(body),
                "content_type": response.headers.get("Content-Type", "application/octet-stream")[
                    :120
                ],
                "etag": response.headers.get("ETag", "")[:200],
                "last_modified": response.headers.get("Last-Modified", "")[:200],
            }


class SourcesMixin:
    def register_source(self, payload, actor, request_key):
        from scale_mobili.platform import entity

        self.moderator(actor)
        try:
            parsed = urlparse(payload.url)
            port = parsed.port
        except ValueError as exc:
            raise DomainError("URL della fonte non valido") from exc
        allowed = (
            {"example.invalid"} if payload.synthetic else set(self.settings.source_allowed_hosts)
        )
        if (
            parsed.scheme != "https"
            or parsed.hostname not in allowed
            or port not in {None, 443}
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise DomainError("Fonte non consentita: usare un URL HTTPS del dominio verificato")
        source_id = str(uuid4())

        def factory(event_id, when):
            item = record(
                entity("SOURCE", source_id),
                **payload.model_dump(),
                source_id=source_id,
                created_at=when,
                version=1,
            )
            directory = record(
                {"PK": "CATALOG#SOURCES", "SK": "SOURCE#" + source_id},
                source_id=source_id,
                version=1,
            )
            return [(item, 0), (directory, 0)], [], [], self.source_metadata(item)

        return self._write(
            actor, request_key, "register_source", payload.model_dump(mode="json"), factory
        )

    @staticmethod
    def source_metadata(source):
        return {
            k: source.get(k)
            for k in (
                "source_id",
                "name",
                "url",
                "meaning",
                "synthetic",
                "created_at",
                "version",
                "last_acquired_at",
                "last_hash",
            )
        }

    def sources(self):
        from scale_mobili.platform import entity

        rows, cursor = self.store.page_core("CATALOG#SOURCES", limit=100)
        if cursor:
            raise DomainError("Oltre il limite di 100 fonti del prototipo", 503)
        items = [self.store.get_core(entity("SOURCE", r["source_id"])) for r in rows]
        return [self.source_metadata(s) for s in items if s]

    def collect_source(self, source_id, actor, request_key, fetcher=None, *, fixture_digest=None):
        from scale_mobili.platform import entity, event_record

        self.moderator(actor)
        cached = None
        acquired_at = timestamp()

        def factory(event_id, when):
            nonlocal cached
            source = self.store.get_core(entity("SOURCE", source_id))
            if not source:
                raise DomainError("Fonte non trovata", 404)
            if cached is None:
                if source["synthetic"] and fetcher is None:
                    raise DomainError("Una fonte sintetica richiede una fixture esplicita")
                # Verifica ripetuta del record prima di qualunque accesso di rete.
                parsed = urlparse(source["url"])
                if not source["synthetic"] and (
                    parsed.hostname not in self.settings.source_allowed_hosts
                    or parsed.scheme != "https"
                ):
                    raise DomainError("Dominio della fonte non consentito")
                try:
                    cached = (fetcher or fetch_source)(source)
                    if cached.get("not_modified"):
                        if not source.get("last_hash"):
                            raise DomainError("304 senza un originale precedente")
                        cached = {"content_hash": source["last_hash"], "outcome": "not_modified"}
                    else:
                        body = cached["body"]
                        if len(body) > 10 * 1024 * 1024:
                            raise DomainError("Fonte oltre il limite di 10 MB")
                        cached = {
                            **cached,
                            "content_hash": hashlib.sha256(body).hexdigest(),
                            "outcome": "succeeded",
                        }
                except (httpx.HTTPError, DomainError, OSError, KeyError) as exc:
                    cached = {"outcome": "failed", "failure_type": type(exc).__name__}
                cached["completed_at"] = timestamp()
                cached["recorded_at"] = timestamp()
            when = cached["recorded_at"]
            event = event_record(
                source["PK"],
                "acquisition",
                actor,
                event_id,
                when,
                source_id=source_id,
                url=source["url"],
                acquisition_started_at=acquired_at,
                acquired_at=cached["completed_at"],
                published_at=None,
                outcome=cached["outcome"],
                synthetic=source["synthetic"],
            )
            puts = []
            updated = {
                **source,
                "version": int(source["version"]) + 1,
                "last_acquired_at": cached["completed_at"],
            }
            if cached.get("content_hash"):
                digest = cached["content_hash"]
                event["content_hash"] = digest
                updated["last_hash"] = digest
                if cached.get("body") is not None:
                    self.blobs.put(
                        self.sources_bucket,
                        "originals/" + digest,
                        cached["body"],
                        cached["content_type"],
                    )
                    blob_key = entity("BLOB", digest)
                    if not self.store.get_core(blob_key):
                        puts.append(
                            (
                                record(
                                    blob_key,
                                    version=1,
                                    content_hash=digest,
                                    size_bytes=len(cached["body"]),
                                    content_type=cached["content_type"],
                                    object_key="originals/" + digest,
                                ),
                                0,
                            )
                        )
                    updated.update(
                        etag=cached.get("etag", ""), last_modified=cached.get("last_modified", "")
                    )
            else:
                event["failure_type"] = cached["failure_type"]
            reference = self._encode(
                {
                    "kind": "source_acquisition",
                    "source_id": source_id,
                    "recorded_at": when,
                    "event_id": event_id,
                }
            )
            result = {k: v for k, v in event.items() if k not in {"PK", "SK", "actor_id"}}
            result["reference"] = reference
            return [*puts, (updated, int(source["version"]))], [event], [], result

        return self._write(
            actor,
            request_key,
            "collect_source:" + source_id,
            {"fixture_digest": fixture_digest} if fixture_digest else {},
            factory,
        )

    def interpret_source(self, payload, actor, request_key):
        from scale_mobili.platform import entity, event_record

        self.moderator(actor)
        reference = self._decode(payload.acquisition_reference)
        if reference.get("kind") != "source_acquisition":
            raise DomainError("Riferimento di acquisizione non valido")

        def factory(event_id, when):
            source = self.store.get_core(entity("SOURCE", reference["source_id"]))
            acquisition = self.store.get_source_event(
                reference["source_id"], reference["recorded_at"], reference["event_id"]
            )
            device = self.require_escalator(payload.device_id)
            device_id = device["escalator_id"]
            if not acquisition or acquisition.get("outcome") not in {"succeeded", "not_modified"}:
                raise DomainError("L'acquisizione non contiene un originale verificabile")
            if bool(acquisition["synthetic"]) != bool(device.get("synthetic")):
                raise DomainError("Non associare una fonte reale a un impianto sintetico")
            state = self.store.get_state(device_id)
            evidence = {
                "status": payload.status.value,
                "source": "official",
                "source_id": source["source_id"],
                "source_url": source["url"],
                "meaning": source["meaning"],
                "content_hash": acquisition["content_hash"],
                "published_at": timestamp(payload.published_at) if payload.published_at else None,
                "acquired_at": acquisition["acquired_at"],
                "interpreted_at": when,
                "acquisition_reference": payload.acquisition_reference,
                "synthetic": acquisition["synthetic"],
            }
            event = event_record(
                "ESC#" + device_id,
                "official_interpretation",
                actor,
                event_id,
                when,
                escalator_id=device_id,
                evidence=evidence,
                reason=payload.reason,
                synthetic=device.get("synthetic", False),
            )
            previous = state.get("official")

            def order(e):
                return e.get("published_at") or e["acquired_at"], e["interpreted_at"]

            official = evidence if not previous or order(evidence) >= order(previous) else previous
            updated = {
                **state,
                **entity("ESC", device_id),
                "SK": "STATE",
                "schema_version": 1,
                "version": int(state["version"]) + 1,
                "official": official,
            }
            # Il controllo di META evita associazioni cambiate durante la revisione.
            check = (
                record(
                    entity("ESC", device_id),
                    **{k: v for k, v in device.items() if k not in {"PK", "SK"}},
                ),
                int(device.get("version", 1)),
            )
            return [(updated, int(state["version"]))], [event], [check], evidence

        return self._write(
            actor, request_key, "interpret_source", payload.model_dump(mode="json"), factory
        )

    def source_fixture(self, source_id, payload, actor, request_key):
        from scale_mobili.platform import entity

        self.moderator(actor)
        source = self.store.get_core(entity("SOURCE", source_id))
        if self.settings.mode == "aws" or not source or not source["synthetic"]:
            raise DomainError(
                "Le fixture sono disponibili solo per fonti sintetiche fuori da AWS", 403
            )
        return self.collect_source(
            source_id,
            actor,
            request_key,
            lambda _: {"body": payload.content.encode(), "content_type": "text/plain"},
            fixture_digest=hashlib.sha256(payload.content.encode()).hexdigest(),
        )

    def original_source(self, reference, actor):
        from scale_mobili.platform import entity

        self.moderator(actor)
        decoded = self._decode(reference)
        if decoded.get("kind") != "source_acquisition":
            raise DomainError("Riferimento di acquisizione non valido")
        event = self.store.get_source_event(
            decoded["source_id"], decoded["recorded_at"], decoded["event_id"]
        )
        if not event or not event.get("content_hash"):
            raise DomainError("Originale non disponibile", 404)
        blob = self.store.get_core(entity("BLOB", event["content_hash"]))
        if not blob:
            raise DomainError("Originale non trovato", 404)
        return blob
