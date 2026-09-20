from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ExpenseCategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class ExpenseCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    is_active: bool


class ExpenseCreate(BaseModel):
    branch_id: int
    category_id: int
    expense_date: date
    amount: Decimal = Field(gt=0, decimal_places=2)
    payment_mode: str = Field(default="cash", min_length=2, max_length=40)
    vendor_name: str | None = Field(default=None, max_length=180)
    reason: str = Field(min_length=3, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=128)


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company_id: int
    branch_id: int
    category_id: int
    expense_date: date
    amount: Decimal
    payment_mode: str
    vendor_name: str | None
    reason: str
    created_at: datetime


class ExpenseSummaryRead(BaseModel):
    start_date: date
    end_date: date
    total_amount: Decimal
    by_category: dict[str, Decimal]
    by_payment_mode: dict[str, Decimal]
