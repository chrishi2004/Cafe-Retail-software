from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.sync import ContinuityMode, ContinuityReconciliationStatus


class SignedHeartbeatInput(BaseModel):
    mode: Literal["local_writer", "recovering", "local_only"] = "local_writer"
    fencing_epoch: int = Field(default=0, ge=0)
    software_version: str | None = Field(default=None, max_length=64)
    event_schema_version: int = Field(default=1, ge=1)
    pending_inbox: int = Field(default=0, ge=0)
    pending_outbox: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")


class WriterLeaseInput(BaseModel):
    scope_key: str = Field(min_length=3, max_length=256)
    business_group_id: str = Field(min_length=1, max_length=64)
    company_id: str | None = Field(default=None, max_length=64)
    branch_id: str | None = Field(default=None, max_length=64)
    requested_mode: Literal["local_writer", "recovering"] = "local_writer"
    fencing_epoch: int | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid")


class WriterLeaseRead(BaseModel):
    scope_key: str
    current_mode: str
    lease_owner_device_id: str | None
    fencing_epoch: int
    lease_expires_at: datetime | None
    last_heartbeat_at: datetime | None
    recovery_state: str


class SignedHeartbeatRead(BaseModel):
    accepted: bool
    device_id: str
    recorded_at: datetime
    business_group_id: str
    company_id: str | None = None
    branch_id: str | None = None
    lease: WriterLeaseRead | None = None


class ContinuityReferenceInput(BaseModel):
    continuity_reference: UUID
    scope_key: str = Field(min_length=3, max_length=256)
    business_group_id: str = Field(min_length=1, max_length=64)
    company_id: str | None = Field(default=None, max_length=64)
    branch_id: str | None = Field(default=None, max_length=64)
    purpose: Literal["payment_capture", "emergency_receipt", "order_note"]
    fencing_epoch: int = Field(ge=0)
    payload: dict[str, object] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ContinuityReferenceRead(BaseModel):
    continuity_reference: UUID
    status: str
    fencing_epoch: int
    replayed: bool = False


class ContinuityStateRead(BaseModel):
    scope_key: str
    company_id: int | None = None
    branch_id: int | None = None
    mode: ContinuityMode
    fencing_epoch: int
    lease_owner_device_id: str | None
    lease_expires_at: datetime | None
    last_heartbeat_at: datetime | None
    last_cloud_contact_at: datetime | None
    last_reconciled_at: datetime | None
    last_queue_drain_at: datetime | None
    snapshot_at: datetime | None
    pending_inbox: int
    pending_outbox: int
    dead_letter_count: int
    attention_message: str | None


class ReconciliationRead(BaseModel):
    reconciliation_reference: str
    scope_key: str
    fencing_epoch: int
    status: ContinuityReconciliationStatus
    pending_inbox_before: int
    pending_outbox_before: int
    pending_inbox_after: int
    pending_outbox_after: int
    order_mismatch_count: int
    invoice_mismatch_count: int
    payment_mismatch_count: int
    stock_mismatch_count: int
    queue_receipt_mismatch_count: int
    closing_mismatch_count: int
    dead_letter_count: int
    details: dict[str, object]
    started_at: datetime
    completed_at: datetime | None


class DeadLetterRead(BaseModel):
    id: int
    direction: str
    event_id: str
    correlation_id: str
    error_code: str
    error_message: str
    retryable: bool
    retry_count: int
    status: str
    first_failed_at: datetime
    last_failed_at: datetime


class DeadLetterRetryRead(BaseModel):
    id: int
    event_id: str
    status: str
    retry_count: int
