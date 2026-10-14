from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def timestamp(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class Status(StrEnum):
    WORKING = "funzionante"
    BROKEN = "guasta"
    MAINTENANCE = "manutenzione"
    UNVERIFIABLE = "non_verificabile"


class ReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status
    observed_at: datetime | None = None

    @field_validator("observed_at")
    @classmethod
    def validate_observation(cls, value):
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("L'osservazione richiede un fuso orario")
            if value > datetime.now(UTC) + timedelta(minutes=2):
                raise ValueError("L'osservazione non può essere futura")
            return value.astimezone(UTC)
        return value


class CorrectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status
    reason: str = Field(min_length=3, max_length=500)


class Actor(BaseModel):
    id: str
    moderator: bool = False
    scopes: frozenset[str] = frozenset()


class DomainError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def public_event(event: dict) -> dict:
    # Autore interno e motivazioni libere restano privati in questa prova.
    allowed = {
        "event_id",
        "escalator_id",
        "kind",
        "status",
        "observed_at",
        "recorded_at",
        "target_event_id",
        "synthetic",
    }
    return {key: value for key, value in event.items() if key in allowed}


class EmptyEvidence(BaseModel):
    status: Literal[None] = None
    reason: str = "Nessuna informazione disponibile"
