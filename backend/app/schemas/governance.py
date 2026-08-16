from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ClosingCreate(BaseModel):
    branch_id: int
    business_date: date
    opening_cash: Decimal = Decimal("0.00")


class ClosingSubmit(BaseModel):
    counted_cash: Decimal


class ClosingReopen(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class VoidInvoiceRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=128)


class StepUpRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class PurgeCreate(BaseModel):
    entity_type: str
    entity_id: int
    reason: str = Field(min_length=3, max_length=500)
    backup_reference: str = Field(min_length=3, max_length=255)


class PurgeApprove(BaseModel):
    second_approval: bool = False


class PurgeExecute(BaseModel):
    typed_confirmation: str = Field(min_length=1, max_length=160)


class ClosingRead(BaseModel):
    id: int
    company_id: int
    branch_id: int
    business_date: date
    opening_cash: Decimal
    cash_collections: Decimal
    cash_refunds: Decimal
    cash_expenses: Decimal
    expected_cash: Decimal
    counted_cash: Decimal | None
    variance: Decimal | None
    non_cash_total: Decimal
    status: str
    submitted_by: int | None
    closed_by: int | None
    reopened_by: int | None
    reason: str | None
    reopened_reason: str | None
    created_at: datetime
    updated_at: datetime


class ReversalRead(BaseModel):
    id: int
    invoice_id: int
    reversal_type: str
    amount: Decimal
    reason: str
    idempotency_key: str
    actor_id: int


class PurgeRead(BaseModel):
    id: int
    company_id: int
    branch_id: int | None
    entity_type: str
    entity_id: int
    reason: str
    status: str
    dependency_report: dict
    backup_reference: str | None
    requested_by: int
    approved_by: int | None
    second_approved_by: int | None
    executed_at: datetime | None
    failure_reason: str | None
