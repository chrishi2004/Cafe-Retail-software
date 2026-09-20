from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.purchase_accounting import PurchaseBillStatus, SupplierLedgerEntryType


class PurchaseBillItemCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0, decimal_places=2)
    unit_cost: Decimal = Field(ge=0, decimal_places=2)


class PurchaseBillCreate(BaseModel):
    branch_id: int
    supplier_id: int
    bill_date: date
    supplier_invoice_number: str | None = Field(default=None, max_length=120)
    idempotency_key: str = Field(min_length=8, max_length=128)
    items: list[PurchaseBillItemCreate] = Field(min_length=1, max_length=200)


class PurchasePaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, decimal_places=2)
    reason: str = Field(min_length=3, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=128)


class PurchaseDebitNoteCreate(BaseModel):
    amount: Decimal = Field(gt=0, decimal_places=2)
    reason: str = Field(min_length=3, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=128)


class PurchaseBillItemRead(BaseModel):
    id: int
    product_id: int
    quantity: Decimal
    unit_cost: Decimal
    line_total: Decimal


class PurchaseBillRead(BaseModel):
    id: int
    company_id: int
    branch_id: int
    supplier_id: int
    bill_number: str
    supplier_invoice_number: str | None
    bill_date: date
    status: PurchaseBillStatus
    total_amount: Decimal
    paid_amount: Decimal
    balance_due: Decimal
    items: list[PurchaseBillItemRead]


class SupplierLedgerEntryRead(BaseModel):
    id: int
    supplier_id: int
    entry_type: SupplierLedgerEntryType
    debit: Decimal
    credit: Decimal
    reference_type: str | None
    reference_id: int | None
    reason: str
    entry_datetime: datetime
