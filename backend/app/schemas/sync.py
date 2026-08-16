from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


CURRENT_EVENT_SCHEMA_VERSION = 1


class EventSource(str, enum.Enum):
    LOCAL_HUB = "local_hub"
    CLOUD_GATEWAY = "cloud_gateway"


class EventEnvelope(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str = Field(min_length=3, max_length=120, pattern=r"^[a-z][a-z0-9_.-]+$")
    schema_version: int = Field(default=CURRENT_EVENT_SCHEMA_VERSION, ge=1)
    source: EventSource
    source_device_id: str | None = Field(default=None, max_length=64)
    business_group_id: str | int | None = None
    company_id: str | int | None = None
    branch_id: str | int | None = None
    aggregate_type: str = Field(min_length=1, max_length=100)
    aggregate_id: str = Field(min_length=1, max_length=100)
    aggregate_version: int = Field(ge=1)
    idempotency_key_hash: str | None = Field(default=None, min_length=64, max_length=64)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID = Field(default_factory=uuid4)
    causation_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("occurred_at", "recorded_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        # PostgreSQL preserves timezone information. SQLite test fixtures do not, so a
        # persisted naive value is interpreted as UTC before the envelope is rebuilt.
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @field_validator("business_group_id", "company_id", "branch_id", mode="before")
    @classmethod
    def normalize_scope_ids(cls, value: object) -> object:
        if value is None:
            return None
        return str(value)

    def storage_payload(self) -> dict[str, Any]:
        """Return a JSON-safe representation suitable for durable queue storage."""
        return self.model_dump(mode="json")
