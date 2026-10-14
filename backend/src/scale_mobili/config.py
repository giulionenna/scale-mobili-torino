import os
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SMT_", extra="ignore", hide_input_in_errors=True)

    mode: str = "demo"
    region: str = "eu-south-1"
    core_table: str = ""
    events_table: str = ""
    public_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"
    cognito_issuer: str = ""
    cognito_client_id: str = ""
    cursor_secret: str = Field(default="", repr=False)
    cursor_secret_parameter: str = ""
    cognito_domain: str = ""
    additional_client_ids: list[str] = []
    photos_bucket: str = ""
    sources_bucket: str = ""
    dynamodb_endpoint: str = ""
    s3_endpoint: str = ""
    source_allowed_hosts: list[str] = ["www.gtt.to.it"]
    write_limit_per_minute: int = 20
    max_catalog_devices: int = 2000
    max_device_events: int = 1000
    snapshot_max_age_seconds: int = 600

    @model_validator(mode="after")
    def validate_runtime(self):
        if self.mode not in {"demo", "local", "aws"}:
            raise ValueError("SMT_MODE deve essere demo, local oppure aws")
        if self.mode != "aws" and os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            raise ValueError("La modalità demo non può essere distribuita su Lambda")
        if self.mode == "local":
            if not all(
                [
                    self.core_table,
                    self.events_table,
                    self.photos_bucket,
                    self.sources_bucket,
                    self.dynamodb_endpoint,
                    self.s3_endpoint,
                    self.cursor_secret,
                ]
            ):
                raise ValueError("Configurazione degli emulatori locali incompleta")
            for endpoint in (self.dynamodb_endpoint, self.s3_endpoint):
                if urlparse(endpoint).hostname not in {"localhost", "127.0.0.1", "dynamodb", "s3"}:
                    raise ValueError("La modalità local usa soltanto emulatori locali")
        if self.mode == "aws":
            if self.dynamodb_endpoint or self.s3_endpoint:
                raise ValueError("Endpoint emulatori vietati in modalità AWS")
            if not self.cursor_secret and self.cursor_secret_parameter:
                import boto3

                self.cursor_secret = boto3.client("ssm", region_name=self.region).get_parameter(
                    Name=self.cursor_secret_parameter, WithDecryption=True
                )["Parameter"]["Value"]
            if not all(
                [
                    self.core_table,
                    self.events_table,
                    self.cognito_issuer,
                    self.cognito_client_id,
                    self.cursor_secret,
                    self.photos_bucket,
                    self.sources_bucket,
                ]
            ):
                raise ValueError("Configurazione AWS incompleta")
            if not self.public_url.startswith("https://") or len(self.cursor_secret) < 32:
                raise ValueError("In AWS servono HTTPS e un segreto cursori di almeno 32 caratteri")
            if not self.frontend_url.startswith("https://"):
                raise ValueError("Il frontend AWS deve usare HTTPS")
        if not 1 <= self.write_limit_per_minute <= 100 or not 1 <= self.max_catalog_devices <= 2000:
            raise ValueError("Limiti del prototipo non validi")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
