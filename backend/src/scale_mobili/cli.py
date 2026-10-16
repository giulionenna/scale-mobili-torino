import argparse
import json
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from scale_mobili.aggregates import rebuild_snapshot
from scale_mobili.config import get_settings
from scale_mobili.domain import Actor, DomainError, SourceInput
from scale_mobili.inventory import import_inventory
from scale_mobili.platform import PlatformService
from scale_mobili.runtime import build_runtime
from scale_mobili.seed import seed_synthetic


def bootstrap_local(settings):
    if settings.mode != "local":
        raise DomainError("Il bootstrap di sviluppo crea risorse soltanto negli emulatori locali")
    session = boto3.Session(
        aws_access_key_id="local-only",
        aws_secret_access_key="local-only",
        region_name=settings.region,
    )
    resource = session.resource("dynamodb", endpoint_url=settings.dynamodb_endpoint)
    for name, indexes in [
        (
            settings.core_table,
            [
                ("by_station", "station_pk", "station_sk"),
                ("review_queue", "review_pk", "review_sk"),
            ],
        ),
        (settings.events_table, [("by_actor", "actor_pk", "actor_sk")]),
    ]:
        try:
            resource.create_table(
                TableName=name,
                KeySchema=[
                    {"AttributeName": "PK", "KeyType": "HASH"},
                    {"AttributeName": "SK", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": a, "AttributeType": "S"}
                    for a in ["PK", "SK", *[a for _, pk, sk in indexes for a in (pk, sk)]]
                ],
                ProvisionedThroughput={"ReadCapacityUnits": 2, "WriteCapacityUnits": 2},
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
                    for n, pk, sk in indexes
                ],
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ResourceInUseException":
                raise
    s3 = session.client("s3", endpoint_url=settings.s3_endpoint)
    for bucket in [settings.photos_bucket, settings.sources_bucket]:
        try:
            s3.create_bucket(
                Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": settings.region}
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in {
                "BucketAlreadyOwnedByYou",
                "BucketAlreadyExists",
            }:
                raise


def main():
    parser = argparse.ArgumentParser(description="Operazioni del prototipo Scale Mobili Torino")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap-local")
    seed = commands.add_parser("seed")
    seed.add_argument("--synthetic", action="store_true", required=True)
    commands.add_parser("rebuild")
    inventory = commands.add_parser("import-inventory")
    inventory.add_argument("file", type=Path)
    inventory.add_argument("--apply", action="store_true")
    inventory.add_argument("--write-delay", type=float, default=0.75)
    register = commands.add_parser("register-gtt")
    register.add_argument("--request-key", required=True)
    arguments = parser.parse_args()
    settings = get_settings()
    if arguments.command == "bootstrap-local":
        bootstrap_local(settings)
        print("Emulatori locali inizializzati; nessuna risorsa AWS creata.")
        return
    store, blobs = build_runtime(settings)
    svc = PlatformService(store, settings, blobs)
    if settings.mode == "demo":
        raise DomainError("Per operazioni persistenti usare local o aws; la demo HTTP è volatile")
    if arguments.command == "seed":
        result = seed_synthetic(store)
    elif arguments.command == "rebuild":
        result = rebuild_snapshot(svc)
    elif arguments.command == "import-inventory":
        result = import_inventory(
            store,
            json.loads(arguments.file.read_text()),
            apply=arguments.apply,
            write_delay=max(0, arguments.write_delay),
        )
    else:
        result = svc.register_source(
            SourceInput(
                name="Aggiornamenti GTT metropolitana",
                url=(
                    "https://www.gtt.to.it/cms/en/19-linee-e-orari/urbana/"
                    "12186-metropolitana-aggiornamento-ascensori-e-scale-mobili"
                ),
                meaning=(
                    "Comunicazioni su manutenzioni straordinarie: "
                    "assenza dal report non significa funzionante."
                ),
            ),
            Actor(
                id="system:source-registration", moderator=True, scopes=frozenset({"reports:write"})
            ),
            arguments.request_key,
        )
    print(json.dumps(result, default=str))
