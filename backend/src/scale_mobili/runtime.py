import boto3
from botocore.config import Config

from scale_mobili.blobs import MemoryBlobs, S3Blobs
from scale_mobili.repository import DynamoRepository, MemoryRepository


def build_runtime(settings):
    if settings.mode == "demo":
        store = MemoryRepository(settings.write_limit_per_minute)
        from scale_mobili.seed import seed_synthetic

        seed_synthetic(store)
        return store, MemoryBlobs()
    session = boto3.Session(
        region_name=settings.region,
        **(
            {"aws_access_key_id": "local-only", "aws_secret_access_key": "local-only"}
            if settings.mode == "local"
            else {}
        ),
    )
    ddb_args = {"endpoint_url": settings.dynamodb_endpoint} if settings.dynamodb_endpoint else {}
    s3_args = {"endpoint_url": settings.s3_endpoint} if settings.s3_endpoint else {}
    resource = session.resource("dynamodb", **ddb_args)
    store = DynamoRepository(
        settings.core_table,
        settings.events_table,
        resource=resource,
        client=session.client("dynamodb", **ddb_args),
        write_limit=settings.write_limit_per_minute,
    )
    return store, S3Blobs(
        session.client(
            "s3",
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            **s3_args,
        ),
        server_encryption=settings.mode == "aws",
    )
