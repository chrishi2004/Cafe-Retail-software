from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models import CafeOrderSource, CafeOrderStatus, InvoicePaymentStatus, InvoiceStatus, TableSessionStatus
from app.schemas.invoices import InvoicePaymentCreate


class CafeBillingPaymentInput(InvoicePaymentCreate):
    pass


class CafeBillRequest(BaseModel):
    expected_version: int | None = Field(default=None, ge=1)
    customer_id: int | None = Field(default=None, ge=1)
    payments: list[CafeBillingPaymentInput] = Field(default_factory=list, max_length=8)


class CafeBillingItemRead(BaseModel):
    order_public_id: str
    order_number: str
    source_channel: CafeOrderSource
    order_status: CafeOrderStatus
    order_item_id: int
    menu_item_name: str
    product_id: int | None
    sku: str | None
    quantity: int
    unit_price: Decimal
    discount: Decimal
    line_total: Decimal
    billed: bool
    excluded_reason: str | None = None


class CafeBillQuoteRead(BaseModel):
    source_type: str
    source_id: str
    branch_id: int
    table_session_public_id: str | None = None
    table_session_status: TableSessionStatus | None = None
    source_version: int
    subtotal: Decimal
    discount_total: Decimal
    taxable_total: Decimal
    cgst_total: Decimal
    sgst_total: Decimal
    igst_total: Decimal
    cess_total: Decimal
    round_off: Decimal
    grand_total: Decimal
    eligible_items: list[CafeBillingItemRead]
    excluded_items: list[CafeBillingItemRead]


class CafeBillPaymentRead(BaseModel):
    mode_name: str | None
    amount: Decimal
    reference_number: str | None
    is_credit_marker: bool


class CafeReceiptItemRead(BaseModel):
    name: str
    sku: str
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    line_total: Decimal


class CafeReceiptRead(BaseModel):
    invoice_id: int
    invoice_number: str
    source_type: str
    source_id: str
    cafe_name: str
    branch_name: str
    invoice_type: str
    invoice_status: InvoiceStatus
    payment_status: InvoicePaymentStatus
    issued_at: datetime | None
    subtotal: Decimal
    discount_total: Decimal
    taxable_total: Decimal
    cgst_total: Decimal
    sgst_total: Decimal
    igst_total: Decimal
    cess_total: Decimal
    round_off: Decimal
    grand_total: Decimal
    paid_amount: Decimal
    balance_due: Decimal
    gstin: None = None
    items: list[CafeReceiptItemRead]
    payments: list[CafeBillPaymentRead]


class CafeBillResultRead(BaseModel):
    receipt: CafeReceiptRead
    table_session_status: TableSessionStatus | None = None
    order_status: CafeOrderStatus | None = None
    closed: bool
    idempotent_replay: bool = False


class CafePaymentCollectRequest(BaseModel):
    payment: CafeBillingPaymentInput


class CafeCloseRequest(BaseModel):
    expected_version: int = Field(ge=1)


class CafeBillingSourceRead(BaseModel):
    source_type: str
    source_id: str
    label: str
    branch_id: int
    status: str
    source_version: int
    order_count: int
    grand_total_hint: Decimal

    @field_validator("source_type")
    @classmethod
    def validate_source(cls, value: str) -> str:
        if value not in {"cafe_table_session", "cafe_takeaway"}:
            raise ValueError("Unsupported Cafe billing source.")
        return value
