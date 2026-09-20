from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.returns import CreditNoteStatus, RefundMode, ReturnCondition, SalesReturnStatus


class ReturnItemCreate(BaseModel):
    invoice_item_id: int
    quantity: Decimal = Field(gt=0, decimal_places=2)
    condition: ReturnCondition = ReturnCondition.SALEABLE
    restock: bool = True


class SalesReturnCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    refund_mode: RefundMode = RefundMode.CUSTOMER_CREDIT
    idempotency_key: str = Field(min_length=8, max_length=128)
    items: list[ReturnItemCreate] = Field(min_length=1, max_length=100)


class ReturnItemRead(BaseModel):
    id: int
    invoice_item_id: int
    product_id: int | None
    quantity: Decimal
    unit_price: Decimal
    taxable_value: Decimal
    tax_total: Decimal
    line_total: Decimal
    condition: ReturnCondition
    restocked: bool


class CreditNoteRead(BaseModel):
    id: int
    credit_note_number: str
    status: CreditNoteStatus
    amount: Decimal
    refund_mode: RefundMode
    reason: str
    issued_at: datetime


class SalesReturnRead(BaseModel):
    id: int
    company_id: int
    branch_id: int
    invoice_id: int
    customer_id: int | None
    return_number: str
    status: SalesReturnStatus
    refund_mode: RefundMode
    reason: str
    total_amount: Decimal
    returned_at: datetime
    items: list[ReturnItemRead]
    credit_note: CreditNoteRead
