import os
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SMT_", extra="ignore")

    mode: str = "demo"
    region: str = "eu-south-1"
    core_table: str = ""
    events_table: str = ""
    public_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"
    cognito_issuer: str = ""
    cognito_client_id: str = ""
    cursor_secret: str = ""

    @model_validator(mode="after")
    def validate_runtime(self):
        if self.mode not in {"demo", "aws"}:
            raise ValueError("SMT_MODE deve essere demo oppure aws")
        if self.mode == "demo" and os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            raise ValueError("La modalità demo non può essere distribuita su Lambda")
        if self.mode == "aws":
            if not all(
                [
                    self.core_table,
                    self.events_table,
                    self.cognito_issuer,
                    self.cognito_client_id,
                    self.cursor_secret,
                ]
            ):
                raise ValueError("Configurazione AWS incompleta")
            if not self.public_url.startswith("https://") or len(self.cursor_secret) < 32:
                raise ValueError("In AWS servono HTTPS e un segreto cursori di almeno 32 caratteri")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
