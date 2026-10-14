"""Accessi aggiuntivi senza Scan; ogni GSI viene verificato sul record corrente."""

import hashlib
import time
from copy import deepcopy

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from scale_mobili.domain import DomainError
from scale_mobili.keys import event_key
from scale_mobili.store import ConcurrentWrite, DynamoStore, MemoryStore

WORK = {"PK": "WORK#AGGREGATES", "SK": "GLOBAL"}


def rate_key(actor_id):
    return {
        "PK": "RATE#" + hashlib.sha256(actor_id.encode()).hexdigest(),
        "SK": str(int(time.time()) // 60),
    }


def record(key, **attributes):
    kind = "state" if key["SK"] == "STATE" else key["PK"].split("#", 1)[0].lower()
    return {**key, "schema_version": 1, "entity_type": kind, **attributes}


class MemoryRepository(MemoryStore):
    def __init__(self, write_limit=20):
        super().__init__()
        self.documents = {}
        self.write_limit = write_limit
        for number, item in enumerate(self.escalators.values()):
            item.update(
                kind="scala_mobile" if number == 0 else "ascensore",
                location="Percorso fittizio di prova",
                version=1,
            )

    def get_core(self, key):
        with self.lock:
            if key in (
                {"PK": "CATALOG#STATIONS", "SK": s.get("SK", "STATION#" + s["station_id"])}
                for s in self.stations
            ):
                item = next(s for s in self.stations if "STATION#" + s["station_id"] == key["SK"])
                return record(
                    key, version=1, **{k: v for k, v in item.items() if k not in {*key, "version"}}
                )
            if key["PK"].startswith("ESC#"):
                device_id = key["PK"][4:]
                item = (
                    self.escalators.get(device_id)
                    if key["SK"] == "META"
                    else self.states.get(device_id)
                    if key["SK"] == "STATE"
                    else None
                )
                if item:
                    return {**deepcopy(item), **key}
            if key["PK"].startswith("IDEMP#") and key["PK"] in self.idempotency:
                return {**deepcopy(self.idempotency[key["PK"]]), **key}
            return deepcopy(self.documents.get((key["PK"], key["SK"])))

    def _put(self, item):
        self.documents[(item["PK"], item["SK"])] = deepcopy(item)
        if item["PK"].startswith("IDEMP#"):
            self.idempotency[item["PK"]] = deepcopy(item)
        if item["PK"].startswith("ESC#"):
            if item["SK"] == "META":
                self.escalators[item["PK"][4:]] = deepcopy(item)
            elif item["SK"] == "STATE":
                self.states[item["PK"][4:]] = deepcopy(item)
        elif item["PK"] == "CATALOG#STATIONS":
            self.stations = [s for s in self.stations if s["station_id"] != item["station_id"]] + [
                deepcopy(item)
            ]

    def _rate(self, actor):
        key = rate_key(actor.id)
        current = self.get_core(key) or record(key, count=0)
        if current["count"] >= self.write_limit:
            raise DomainError("Limite di scritture raggiunto: riprova tra un minuto", 429)
        self._put({**current, "count": current["count"] + 1, "expires_at": int(time.time()) + 120})
        return key

    def _invalidate(self):
        old = self.get_core(WORK) or record(WORK, version=0)
        self._put({**old, "version": old["version"] + 1})

    def transact(self, puts, events=(), checks=(), actor=None, invalidate=True):
        with self.lock:
            for item, expected in [*puts, *checks]:
                current = self.get_core({"PK": item["PK"], "SK": item["SK"]})
                if (
                    current is not None
                    if expected == 0
                    else not current or int(current.get("version", 0)) != expected
                ):
                    raise ConcurrentWrite()
            if any(e["event_id"] in self.events for e in events):
                raise ConcurrentWrite()
            if actor:
                self._rate(actor)
            for item, _ in puts:
                self._put(item)
            for event in events:
                self.events[event["event_id"]] = deepcopy(event)
            if invalidate:
                self._invalidate()

    def page_core(self, pk, prefix="", limit=100, after=None, index=None, descending=False):
        pk_name, sk_name = ("review_pk", "review_sk") if index == "review_queue" else ("PK", "SK")
        with self.lock:
            rows = sorted(
                [
                    deepcopy(r)
                    for r in self.documents.values()
                    if r.get(pk_name) == pk
                    and r.get(sk_name, "").startswith(prefix)
                    and (
                        not after
                        or (
                            r[sk_name] < after[sk_name]
                            if descending
                            else r[sk_name] > after[sk_name]
                        )
                    )
                ],
                key=lambda r: r[sk_name],
                reverse=descending,
            )
        page = rows[:limit]
        last = (
            {k: page[-1][k] for k in {"PK", "SK", pk_name, sk_name}} if len(rows) > limit else None
        )
        return page, last

    def page_actor(self, actor_id, upper, limit, after=None):
        rows = sorted(
            [
                deepcopy(e)
                for e in self.events.values()
                if e.get("actor_id") == actor_id
                and e["recorded_at"] <= upper
                and (not after or e["SK"] > after["SK"])
            ],
            key=lambda e: e["SK"],
        )
        page = rows[:limit]
        return page, {"SK": page[-1]["SK"]} if len(rows) > limit else None

    def get_source_event(self, source_id, recorded_at, event_id):
        event = self.events.get(event_id)
        return (
            deepcopy(event)
            if event
            and event.get("PK") == "SOURCE#" + source_id
            and event["recorded_at"] == recorded_at
            else None
        )

    def commit(self, event, state, expected_version, actor_id, request_key, receipt, now):
        from scale_mobili.domain import Actor

        with self.lock:
            photo = (
                self.get_core({"PK": "PHOTO#" + event["photo_id"], "SK": "META"})
                if event.get("photo_id")
                else None
            )
            if event.get("photo_id") and not photo:
                raise DomainError("Foto non trovata", 404)
            if photo and (
                photo["status"] != "prepared"
                or photo["actor_id"] != actor_id
                or (
                    photo.get("device_id") != event["escalator_id"]
                    and self.escalators.get(photo.get("device_id"), {}).get("alias_of")
                    != event["escalator_id"]
                )
            ):
                raise DomainError("Foto non disponibile per questa segnalazione", 409)
            quota_key = self._rate(Actor(id=actor_id))
            try:
                super().commit(event, state, expected_version, actor_id, request_key, receipt, now)
            except Exception:
                key = quota_key
                old = self.get_core(key)
                self._put({**old, "count": old["count"] - 1})
                raise
            self.events[event["event_id"]].update(**event_key(event))
            if event["kind"] == "report":
                self._put(record({"PK": "FEED#REPORTS", "SK": event_key(event)["SK"]}, **event))
            if photo:
                self._put(
                    {
                        **photo,
                        "device_id": event["escalator_id"],
                        "status": "pending",
                        "version": photo["version"] + 1,
                        "report_id": event["event_id"],
                        "review_pk": "REVIEW#photo#PENDING",
                        "review_sk": photo["created_at"] + "#" + photo["photo_id"],
                    }
                )
            self._invalidate()


class DynamoRepository(DynamoStore):
    def __init__(self, *args, write_limit=20, client=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.write_limit = write_limit
        self.transaction_client = client or boto3.client(
            "dynamodb", region_name=self.resource.meta.client.meta.region_name
        )

    def get_core(self, key):
        return self.core.get_item(Key=key, ConsistentRead=True).get("Item")

    def get_source_event(self, source_id, recorded_at, event_id):
        return self.events.get_item(
            Key={"PK": "SOURCE#" + source_id, "SK": f"EVENT#{recorded_at}#{event_id}"},
            ConsistentRead=True,
        ).get("Item")

    def _condition(self, expected):
        if expected == 0:
            return {"ConditionExpression": "attribute_not_exists(PK)"}
        return {
            "ConditionExpression": "#v = :expected",
            "ExpressionAttributeNames": {"#v": "version"},
            "ExpressionAttributeValues": self._serialize({":expected": expected}),
        }

    def _rate_ops(self, actor):
        return [
            {
                "Update": {
                    "TableName": self.core.name,
                    "Key": self._serialize(rate_key(actor.id)),
                    "UpdateExpression": "SET expires_at = :ttl ADD #count :one",
                    "ConditionExpression": "attribute_not_exists(#count) OR #count < :limit",
                    "ExpressionAttributeNames": {"#count": "count"},
                    "ExpressionAttributeValues": self._serialize(
                        {":ttl": int(time.time()) + 120, ":one": 1, ":limit": self.write_limit}
                    ),
                }
            }
        ]

    def _work_ops(self):
        return [
            {
                "Update": {
                    "TableName": self.core.name,
                    "Key": self._serialize(WORK),
                    "UpdateExpression": "SET schema_version = :one ADD #v :one",
                    "ExpressionAttributeNames": {"#v": "version"},
                    "ExpressionAttributeValues": self._serialize({":one": 1}),
                }
            }
        ]

    def _send(self, ops, actor=None):
        try:
            self.transaction_client.transact_write_items(TransactItems=ops)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "TransactionCanceledException":
                quota = self.get_core(rate_key(actor.id)) if actor else None
                if quota and quota["count"] >= self.write_limit:
                    raise DomainError(
                        "Limite di scritture raggiunto: riprova tra un minuto", 429
                    ) from exc
                raise ConcurrentWrite() from exc
            raise

    def transact(self, puts, events=(), checks=(), actor=None, invalidate=True):
        ops = [
            {
                "Put": {
                    "TableName": self.core.name,
                    "Item": self._serialize(item),
                    **self._condition(expected),
                }
            }
            for item, expected in puts
        ]
        ops.extend(
            {
                "ConditionCheck": {
                    "TableName": self.core.name,
                    "Key": self._serialize({"PK": item["PK"], "SK": item["SK"]}),
                    **self._condition(expected),
                }
            }
            for item, expected in checks
        )
        for event in events:
            item = {**event, "schema_version": 1}
            if event.get("actor_id"):
                item.update(actor_pk="USER#" + event["actor_id"], actor_sk=event["SK"])
            ops.append(
                {
                    "Put": {
                        "TableName": self.events.name,
                        "Item": self._serialize(item),
                        "ConditionExpression": "attribute_not_exists(PK)",
                    }
                }
            )
        if actor:
            ops.extend(self._rate_ops(actor))
        if invalidate:
            ops.extend(self._work_ops())
        self._send(ops, actor)

    def page_core(self, pk, prefix="", limit=100, after=None, index=None, descending=False):
        pk_name, sk_name = ("review_pk", "review_sk") if index == "review_queue" else ("PK", "SK")
        condition = Key(pk_name).eq(pk)
        if prefix:
            condition &= Key(sk_name).begins_with(prefix)
        args = {
            "KeyConditionExpression": condition,
            "Limit": limit,
            "ScanIndexForward": not descending,
        }
        if index:
            args["IndexName"] = index
        else:
            args["ConsistentRead"] = True
        if after:
            args["ExclusiveStartKey"] = after
        response = self.core.query(**args)
        items = response.get("Items", [])
        if index:
            items = [self.get_core({"PK": row["PK"], "SK": row["SK"]}) for row in items]
            items = [
                r
                for r in items
                if r and r.get(pk_name) == pk and r.get(sk_name, "").startswith(prefix)
            ]
        return items, response.get("LastEvaluatedKey")

    def page_actor(self, actor_id, upper, limit, after=None):
        args = {
            "IndexName": "by_actor",
            "KeyConditionExpression": Key("actor_pk").eq("USER#" + actor_id)
            & Key("actor_sk").between("EVENT#", "EVENT#" + upper + "#\uffff"),
            "Limit": limit,
        }
        if after:
            args["ExclusiveStartKey"] = after
        response = self.events.query(**args)
        rows = [
            self.events.get_item(Key={"PK": r["PK"], "SK": r["SK"]}, ConsistentRead=True).get(
                "Item"
            )
            for r in response.get("Items", [])
        ]
        return [r for r in rows if r and r.get("actor_id") == actor_id], response.get(
            "LastEvaluatedKey"
        )

    def report_extras(self, event, actor_id):
        from scale_mobili.domain import Actor

        actor = Actor(id=actor_id)
        quota = self.get_core(rate_key(actor_id))
        if quota and quota["count"] >= self.write_limit:
            raise DomainError("Limite di scritture raggiunto: riprova tra un minuto", 429)
        ops = self._rate_ops(actor) + self._work_ops()
        if event["kind"] == "report":
            item = record({"PK": "FEED#REPORTS", "SK": event_key(event)["SK"]}, **event)
            ops.append(
                {
                    "Put": {
                        "TableName": self.core.name,
                        "Item": self._serialize(item),
                        "ConditionExpression": "attribute_not_exists(PK)",
                    }
                }
            )
        if event.get("photo_id"):
            photo = self.get_core({"PK": "PHOTO#" + event["photo_id"], "SK": "META"})
            parent = (
                self.get_escalator(photo["device_id"]) if photo and photo.get("device_id") else None
            )
            if (
                not photo
                or photo["status"] != "prepared"
                or photo["actor_id"] != actor_id
                or (
                    photo.get("device_id") != event["escalator_id"]
                    and (not parent or parent.get("alias_of") != event["escalator_id"])
                )
            ):
                raise DomainError("Foto non disponibile per questa segnalazione", 409)
            item = {
                **photo,
                "device_id": event["escalator_id"],
                "status": "pending",
                "version": int(photo["version"]) + 1,
                "report_id": event["event_id"],
                "review_pk": "REVIEW#photo#PENDING",
                "review_sk": photo["created_at"] + "#" + photo["photo_id"],
            }
            ops.append(
                {
                    "Put": {
                        "TableName": self.core.name,
                        "Item": self._serialize(item),
                        **self._condition(int(photo["version"])),
                    }
                }
            )
            if photo["device_id"] != event["escalator_id"]:
                ops.append(
                    {
                        "ConditionCheck": {
                            "TableName": self.core.name,
                            "Key": self._serialize(
                                {"PK": "ESC#" + photo["device_id"], "SK": "META"}
                            ),
                            **self._condition(int(parent["version"])),
                        }
                    }
                )
        return ops
