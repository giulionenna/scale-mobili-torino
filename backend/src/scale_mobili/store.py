from copy import deepcopy
from threading import RLock

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

from scale_mobili.keys import escalator, event_key, idempotency_key


class ConcurrentWrite(Exception):
    pass


class MemoryStore:
    """Archivio volatile esclusivamente sintetico per lo sviluppo cloud."""

    def __init__(self):
        self.lock = RLock()
        self.stations = [
            {"station_id": "demo-station", "name": "Stazione fittizia", "synthetic": True}
        ]
        self.escalators = {
            f"demo-esc-{n}": {
                "escalator_id": f"demo-esc-{n}",
                "station_id": "demo-station",
                "name": f"Scala mobile fittizia {n}",
                "confirmed": True,
                "synthetic": True,
                "official_id": None,
                "operator": None,
            }
            for n in (1, 2)
        }
        self.states = {}
        self.events = {}
        self.idempotency = {}

    def list_stations(self):
        return deepcopy(self.stations)

    def list_escalators(self, station_id):
        return deepcopy(
            [
                e
                for e in self.escalators.values()
                if e["station_id"] == station_id and e["confirmed"]
            ]
        )

    def get_escalator(self, escalator_id):
        return deepcopy(self.escalators.get(escalator_id))

    def get_state(self, escalator_id):
        with self.lock:
            return deepcopy(self.states.get(escalator_id, {"version": 0, "community": None}))

    def history(self, escalator_id, upper, after, limit):
        with self.lock:
            snapshot = deepcopy(list(self.events.values()))
        events = sorted(
            [
                e
                for e in snapshot
                if e["escalator_id"] == escalator_id
                and e["recorded_at"] <= upper
                and (after is None or event_key(e)["SK"] > after)
            ],
            key=lambda e: event_key(e)["SK"],
        )
        page = deepcopy(events[:limit])
        return page, event_key(page[-1])["SK"] if len(events) > limit else None

    def get_event(self, escalator_id, recorded_at, event_id):
        e = self.events.get(event_id)
        return (
            deepcopy(e)
            if e and e["escalator_id"] == escalator_id and e["recorded_at"] == recorded_at
            else None
        )

    def get_idempotency(self, actor_id, request_key):
        with self.lock:
            return deepcopy(self.idempotency.get(idempotency_key(actor_id, request_key)["PK"]))

    def commit(self, event, state, expected_version, actor_id, request_key, receipt, now):
        with self.lock:
            key = idempotency_key(actor_id, request_key)["PK"]
            previous = self.idempotency.get(key)
            current = self.states.get(event["escalator_id"], {"version": 0})
            meta = self.escalators.get(event["escalator_id"])
            if (
                not meta
                or not meta["confirmed"]
                or current["version"] != expected_version
                or event["event_id"] in self.events
                or (previous and previous["expires_at"] > now)
            ):
                raise ConcurrentWrite()
            self.events[event["event_id"]] = deepcopy(event)
            self.states[event["escalator_id"]] = deepcopy(state)
            self.idempotency[key] = deepcopy(receipt)


class DynamoStore:
    def __init__(self, core_table, events_table, region="eu-south-1", resource=None):
        self.resource = resource or boto3.resource("dynamodb", region_name=region)
        self.core = self.resource.Table(core_table)
        self.events = self.resource.Table(events_table)
        self.serializer = TypeSerializer()

    def _query_all(self, table, **kwargs):
        items = []
        while True:
            response = table.query(**kwargs)
            items.extend(response.get("Items", []))
            if not response.get("LastEvaluatedKey"):
                return items
            kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    def list_stations(self):
        return self._query_all(self.core, KeyConditionExpression=Key("PK").eq("CATALOG#STATIONS"))

    def list_escalators(self, station_id):
        keys = self._query_all(
            self.core,
            IndexName="by_station",
            KeyConditionExpression=Key("station_pk").eq(f"STATION#{station_id}"),
        )
        # Il record originale decide conferma e associazione: il GSI può essere arretrato.
        records = [
            self.core.get_item(Key={"PK": k["PK"], "SK": k["SK"]}, ConsistentRead=True).get("Item")
            for k in keys
        ]
        return [
            r for r in records if r and r.get("confirmed") and r.get("station_id") == station_id
        ]

    def get_escalator(self, escalator_id):
        return self.core.get_item(
            Key={"PK": escalator(escalator_id), "SK": "META"}, ConsistentRead=True
        ).get("Item")

    def get_state(self, escalator_id):
        return self.core.get_item(
            Key={"PK": escalator(escalator_id), "SK": "STATE"}, ConsistentRead=True
        ).get("Item", {"version": 0, "community": None})

    def history(self, escalator_id, upper, after, limit):
        # Il suffisso massimo include tutti gli ID registrati all'istante upper.
        condition = Key("PK").eq(escalator(escalator_id)) & Key("SK").between(
            "EVENT#", f"EVENT#{upper}#\uffff"
        )
        kwargs = {"KeyConditionExpression": condition, "Limit": limit, "ConsistentRead": True}
        if after:
            kwargs["ExclusiveStartKey"] = {"PK": escalator(escalator_id), "SK": after}
        response = self.events.query(**kwargs)
        last = response.get("LastEvaluatedKey", {}).get("SK")
        return response.get("Items", []), last

    def get_event(self, escalator_id, recorded_at, event_id):
        return self.events.get_item(
            Key={"PK": escalator(escalator_id), "SK": f"EVENT#{recorded_at}#{event_id}"},
            ConsistentRead=True,
        ).get("Item")

    def get_idempotency(self, actor_id, request_key):
        return self.core.get_item(
            Key=idempotency_key(actor_id, request_key), ConsistentRead=True
        ).get("Item")

    def _serialize(self, item):
        return {k: self.serializer.serialize(v) for k, v in item.items()}

    def commit(self, event, state, expected_version, actor_id, request_key, receipt, now):
        event_item = {
            **event,
            **event_key(event),
            "actor_pk": f"USER#{actor_id}",
            "actor_sk": event_key(event)["SK"],
            "entity_type": "event",
            "schema_version": 1,
        }
        state_item = {
            **state,
            "PK": escalator(event["escalator_id"]),
            "SK": "STATE",
            "entity_type": "state",
            "schema_version": 1,
        }
        receipt_item = {
            **receipt,
            **idempotency_key(actor_id, request_key),
            "entity_type": "idempotency",
            "schema_version": 1,
        }
        ops = [
            {
                "ConditionCheck": {
                    "TableName": self.core.name,
                    "Key": self._serialize({"PK": escalator(event["escalator_id"]), "SK": "META"}),
                    "ConditionExpression": "confirmed = :yes",
                    "ExpressionAttributeValues": self._serialize({":yes": True}),
                }
            },
            {
                "Put": {
                    "TableName": self.events.name,
                    "Item": self._serialize(event_item),
                    "ConditionExpression": "attribute_not_exists(PK)",
                }
            },
            {
                "Put": {
                    "TableName": self.core.name,
                    "Item": self._serialize(state_item),
                    "ConditionExpression": "attribute_not_exists(PK) OR #v = :expected",
                    "ExpressionAttributeNames": {"#v": "version"},
                    "ExpressionAttributeValues": self._serialize({":expected": expected_version}),
                }
            },
            {
                "Put": {
                    "TableName": self.core.name,
                    "Item": self._serialize(receipt_item),
                    "ConditionExpression": "attribute_not_exists(PK) OR expires_at <= :now",
                    "ExpressionAttributeValues": self._serialize({":now": now}),
                }
            },
        ]
        # Client indipendente: quello della resource converte già i valori e non va
        # mescolato alla serializzazione esplicita dell'API low-level.
        client = boto3.client("dynamodb", region_name=self.resource.meta.client.meta.region_name)
        try:
            client.transact_write_items(TransactItems=ops)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "TransactionCanceledException":
                raise ConcurrentWrite() from exc
            raise
