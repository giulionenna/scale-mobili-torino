import boto3
import pytest
from moto import mock_aws

from scale_mobili.config import Settings
from scale_mobili.domain import Actor
from scale_mobili.repository import DynamoRepository as DynamoStore
from scale_mobili.repository import MemoryRepository as MemoryStore


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch):
    # I test non usano mai le credenziali AWS dell'ambiente.
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.setenv(key, "testing")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")


@pytest.fixture
def settings():
    return Settings(mode="demo", cursor_secret="test-cursors-only-" * 3)


@pytest.fixture
def actor():
    return Actor(id="demo-user-1", scopes=frozenset({"reports:write", "stats:read"}))


@pytest.fixture(params=["memory", "dynamodb-emulated"])
def store(request):
    memory = MemoryStore()
    if request.param == "memory":
        yield memory
        return
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="eu-south-1")
        for name, gsis in [
            (
                "test-core",
                [
                    ("by_station", "station_pk", "station_sk"),
                    ("review_queue", "review_pk", "review_sk"),
                ],
            ),
            ("test-events", [("by_actor", "actor_pk", "actor_sk")]),
        ]:
            attrs = ["PK", "SK", *[a for _, pk, sk in gsis for a in (pk, sk)]]
            resource.create_table(
                TableName=name,
                KeySchema=[
                    {"AttributeName": "PK", "KeyType": "HASH"},
                    {"AttributeName": "SK", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[{"AttributeName": a, "AttributeType": "S"} for a in attrs],
                ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": n,
                        "KeySchema": [
                            {"AttributeName": pk, "KeyType": "HASH"},
                            {"AttributeName": sk, "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "KEYS_ONLY"},
                        "ProvisionedThroughput": {"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
                    }
                    for n, pk, sk in gsis
                ],
            )
        core = resource.Table("test-core")
        for station in memory.stations:
            core.put_item(
                Item={
                    **station,
                    "PK": "CATALOG#STATIONS",
                    "SK": f"STATION#{station['station_id']}",
                    "schema_version": 1,
                    "version": 1,
                }
            )
        for item in memory.escalators.values():
            core.put_item(
                Item={
                    **item,
                    "PK": f"ESC#{item['escalator_id']}",
                    "SK": "META",
                    "station_pk": f"STATION#{item['station_id']}",
                    "station_sk": f"ESC#{item['escalator_id']}",
                    "schema_version": 1,
                }
            )
        yield DynamoStore("test-core", "test-events", resource=resource)
