from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class RegisterSessionCreate(BaseModel):
    branch_id: int
    opening_float: Decimal = Field(default=Decimal("0.00"), ge=0)
    notes: str | None = Field(default=None, max_length=500)


class RegisterCount(BaseModel):
    counted_cash: Decimal = Field(ge=0)


class RegisterMovementCreate(BaseModel):
    movement_type: str = Field(pattern="^(cash_in|cash_out|expense|adjustment)$")
    amount: Decimal = Field(gt=0)
    reason: str = Field(min_length=2, max_length=255)
    reference: str | None = Field(default=None, max_length=120)
    idempotency_key: str = Field(min_length=8, max_length=128)


class RegisterMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    movement_type: str
    amount: Decimal
    reason: str
    reference: str | None
    recorded_by: int
    occurred_at: datetime


class RegisterModeSummary(BaseModel):
    mode: str
    amount: Decimal


class RegisterSummary(BaseModel):
    id: int
    company_id: int
    branch_id: int
    status: str
    opening_float: Decimal
    opened_at: datetime
    closed_at: datetime | None
    expected_cash: Decimal
    counted_cash: Decimal | None
    variance: Decimal | None
    cash_collections: Decimal
    cash_refunds: Decimal
    cash_in: Decimal
    cash_out: Decimal
    expenses: Decimal
    non_cash_total: Decimal
    credit_total: Decimal
    mode_totals: list[RegisterModeSummary]
    movements: list[RegisterMovementRead]
