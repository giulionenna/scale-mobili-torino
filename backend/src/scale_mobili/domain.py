from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def timestamp(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def percentage(count, total):
    """Arrotondamento all'intero con mezzo punto verso l'alto, come nel frontend."""
    return (200 * count + total) // (2 * total) if total else None


class Status(StrEnum):
    WORKING = "funzionante"
    BROKEN = "guasta"
    MAINTENANCE = "manutenzione"
    UNVERIFIABLE = "non_verificabile"


class ReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status
    observed_at: datetime | None = None
    station_id: str | None = Field(default=None, min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    photo_id: str | None = Field(default=None, min_length=1, max_length=100)

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


class DeviceReportInput(ReportInput):
    station_id: str = Field(min_length=1, max_length=100)


class FavoriteStationsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    station_ids: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(max_length=50)
    version: int = Field(ge=0)


class ProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    station_id: str = Field(min_length=1, max_length=100)
    kind: Literal["scala_mobile", "ascensore"]
    name: str = Field(min_length=3, max_length=120)
    location: str = Field(min_length=3, max_length=500)
    description: str = Field(default="", max_length=2000)


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    decision: Literal["approved", "rejected"]
    version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=1000)


class StationMoveInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    station_id: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=1000)


class MergeDeviceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    canonical_device_id: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=1)
    canonical_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=1000)


class PhotoUploadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str | None = Field(default=None, min_length=1, max_length=100)
    proposal_id: str | None = Field(default=None, min_length=1, max_length=100)
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    size_bytes: int = Field(ge=1, le=5 * 1024 * 1024)

    @model_validator(mode="after")
    def exclusive_parent(self):
        if bool(self.proposal_id) == bool(self.device_id):
            raise ValueError("Specificare un solo impianto oppure una proposta")
        return self


class SourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=3, max_length=120)
    url: str = Field(min_length=8, max_length=1000)
    meaning: str = Field(min_length=10, max_length=1000)
    synthetic: bool = False


class SourceFixtureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=16000)


class InterpretationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(min_length=1, max_length=100)
    acquisition_reference: str = Field(min_length=10, max_length=2048)
    status: Status
    published_at: datetime | None = None
    reason: str = Field(min_length=3, max_length=1000)

    _published = field_validator("published_at")(ReportInput.validate_observation.__func__)


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
        "device_id",
        "station_id",
        "description",
        "evidence",
    }
    return {key: value for key, value in event.items() if key in allowed}


class EmptyEvidence(BaseModel):
    status: Literal[None] = None
    reason: str = "Nessuna informazione disponibile"
