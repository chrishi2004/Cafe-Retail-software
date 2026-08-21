from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.sync import EventEnvelope


class CloudOrderItemInput(BaseModel):
    menu_item_public_id: str = Field(min_length=8, max_length=64)
    quantity: int = Field(ge=1, le=20)
    notes: str | None = Field(default=None, max_length=300)

    model_config = ConfigDict(extra="forbid")

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class CloudOrderCreate(BaseModel):
    publication_id: UUID
    opaque_qr: str = Field(min_length=20, max_length=1000)
    items: list[CloudOrderItemInput] = Field(min_length=1, max_length=25)
    customer_notes: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")

    @field_validator("customer_notes")
    @classmethod
    def clean_customer_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class CloudOrderItemRead(BaseModel):
    menu_item_public_id: str
    name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class CloudOrderRead(BaseModel):
    public_id: UUID
    status: str
    estimated_total: Decimal
    created_at: datetime
    items: list[CloudOrderItemRead] = Field(default_factory=list)
    replayed: bool = False


class CloudBillRequestCreate(BaseModel):
    publication_id: UUID
    opaque_qr: str = Field(min_length=20, max_length=1000)

    model_config = ConfigDict(extra="forbid")


class CloudBillRequestRead(BaseModel):
    order_public_id: UUID
    status: Literal["queued"] = "queued"
    bill_requested_at: datetime
    replayed: bool = False


class CloudCommandBatch(BaseModel):
    events: list[EventEnvelope]


class CloudSyncReceiptInput(BaseModel):
    event_id: UUID
    status: Literal["committed", "duplicate", "rejected"]
    result_reference: str | None = Field(default=None, max_length=128)


class CloudSyncPushRead(BaseModel):
    accepted: bool
    event_id: UUID
    duplicate: bool = False


class SyncStatusRead(BaseModel):
    company_id: int | None
    branch_ids: list[int]
    pending_inbox: int
    pending_outbox: int
    dead_letters: int
    oldest_pending_age_seconds: int | None
    last_inbound_sync_at: datetime | None
    last_outbound_sync_at: datetime | None
    local_device_last_seen_at: datetime | None
    continuity_mode: str | None = None
    fencing_epoch: int = 0
    lease_expires_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    last_cloud_contact_at: datetime | None = None
    last_reconciled_at: datetime | None = None
    last_queue_drain_at: datetime | None = None
    reconciliation_status: str | None = None
    attention_message: str | None = None
