from copy import deepcopy
from threading import RLock

from botocore.exceptions import ClientError

from scale_mobili.domain import DomainError


class MemoryBlobs:
    def __init__(self):
        self.objects = {}
        self.lock = RLock()

    def put(self, bucket, key, body, content_type):
        with self.lock:
            self.objects[(bucket, key)] = (bytes(body), content_type)

    def get(self, bucket, key, maximum=10 * 1024 * 1024):
        with self.lock:
            value = deepcopy(self.objects.get((bucket, key)))
        if not value:
            raise DomainError("File non trovato", 404)
        if len(value[0]) > maximum:
            raise DomainError("File troppo grande", 413)
        return value

    def delete(self, bucket, key):
        with self.lock:
            self.objects.pop((bucket, key), None)

    def upload_form(self, bucket, key, content_type, size):
        return {"url": None, "fields": {}, "method": "PUT", "storage": "demo_memory"}

    def download_url(self, bucket, key):
        return None


class S3Blobs:
    def __init__(self, client, *, server_encryption=True):
        self.client = client
        self.server_encryption = server_encryption

    def put(self, bucket, key, body, content_type):
        self.client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
            **({"ServerSideEncryption": "AES256"} if self.server_encryption else {}),
        )

    def get(self, bucket, key, maximum=10 * 1024 * 1024):
        try:
            head = self.client.head_object(Bucket=bucket, Key=key)
            if head["ContentLength"] > maximum:
                raise DomainError("File troppo grande", 413)
            response = self.client.get_object(Bucket=bucket, Key=key)
            with response["Body"] as stream:
                body = stream.read(maximum + 1)
            if len(body) > maximum:
                raise DomainError("File troppo grande", 413)
            return body, response.get("ContentType", "application/octet-stream")
        except ClientError as exc:
            if exc.response["Error"]["Code"] in {"NoSuchKey", "404", "NotFound"}:
                raise DomainError("File non trovato", 404) from exc
            raise

    def delete(self, bucket, key):
        self.client.delete_object(Bucket=bucket, Key=key)

    def upload_form(self, bucket, key, content_type, size):
        encryption = {"x-amz-server-side-encryption": "AES256"} if self.server_encryption else {}
        signed = self.client.generate_presigned_post(
            Bucket=bucket,
            Key=key,
            Fields={"Content-Type": content_type, **encryption},
            Conditions=[
                {"Content-Type": content_type},
                *([encryption] if encryption else []),
                ["content-length-range", size, size],
            ],
            ExpiresIn=600,
        )
        return {**signed, "method": "POST", "storage": "private_s3"}

    def download_url(self, bucket, key):
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ResponseContentDisposition": "attachment",
                "ResponseContentType": "application/octet-stream",
            },
            ExpiresIn=60,
        )
