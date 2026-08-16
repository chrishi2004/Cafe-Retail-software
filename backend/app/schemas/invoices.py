from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import InvoicePaymentStatus, InvoiceStatus, InvoiceTaxType, InvoiceType


def normalize_blank(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def normalize_upper(value: str | None) -> str | None:
    normalized = normalize_blank(value)
    return normalized.upper() if normalized else None


class InvoiceItemCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    discount: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)


class InvoicePaymentCreate(BaseModel):
    payment_mode_id: int | None = None
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    payment_datetime: datetime | None = None
    reference_number: str | None = Field(default=None, max_length=120)
    notes: str | None = None

    @field_validator("reference_number", "notes")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return normalize_blank(value)


class InvoiceCreate(BaseModel):
    branch_id: int
    customer_id: int | None = None
    invoice_type: InvoiceType = InvoiceType.NON_GST
    place_of_supply_state: str | None = Field(default=None, max_length=100)
    place_of_supply_state_code: str | None = Field(default=None, min_length=2, max_length=2)
    invoice_date: datetime | None = None
    items: list[InvoiceItemCreate] = Field(min_length=1)

    @field_validator("place_of_supply_state")
    @classmethod
    def normalize_state(cls, value: str | None) -> str | None:
        return normalize_blank(value)

    @field_validator("place_of_supply_state_code")
    @classmethod
    def normalize_state_code(cls, value: str | None) -> str | None:
        return normalize_upper(value)

    @field_validator("items")
    @classmethod
    def validate_items(cls, value: list[InvoiceItemCreate]) -> list[InvoiceItemCreate]:
        if not value:
            raise ValueError("At least one invoice item is required.")
        return value


class InvoiceIssueRequest(BaseModel):
    payments: list[InvoicePaymentCreate] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        return normalize_blank(value)


class InvoiceCancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return value.strip()


class POSCheckoutRequest(InvoiceCreate):
    payments: list[InvoicePaymentCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_customer_or_payment(self) -> "POSCheckoutRequest":
        if not self.payments and self.customer_id is None:
            raise ValueError("Anonymous POS checkout requires at least one payment.")
        return self


class InvoiceTaxRead(BaseModel):
    id: int
    invoice_id: int
    invoice_item_id: int | None
    tax_type: InvoiceTaxType
    tax_rate: Decimal
    taxable_value: Decimal
    tax_amount: Decimal

    model_config = ConfigDict(from_attributes=True)


class InvoiceItemRead(BaseModel):
    id: int
    product_id: int | None
    product_name_snapshot: str
    sku_snapshot: str
    hsn_sac_code: str | None
    quantity: Decimal
    unit_price: Decimal
    mrp: Decimal | None
    discount: Decimal
    taxable_value: Decimal
    gst_rate: Decimal
    cgst_total: Decimal
    sgst_total: Decimal
    igst_total: Decimal
    cess_total: Decimal
    line_total: Decimal
    gross_profit: Decimal
    taxes: list[InvoiceTaxRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class InvoicePaymentRead(BaseModel):
    id: int
    invoice_id: int
    payment_mode_id: int | None
    payment_mode_name: str | None = None
    amount: Decimal
    payment_datetime: datetime
    reference_number: str | None
    notes: str | None
    received_by: int | None
    received_by_name: str | None = None
    is_credit_marker: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceStatusHistoryRead(BaseModel):
    id: int
    invoice_id: int
    from_status: InvoiceStatus | None
    to_status: InvoiceStatus
    changed_by: int | None
    changed_by_name: str | None = None
    notes: str | None
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceListItemRead(BaseModel):
    id: int
    invoice_number: str
    branch_id: int
    branch_name: str
    customer_id: int | None
    customer_name: str | None = None
    sale_id: int | None
    invoice_type: InvoiceType
    source_type: str | None = None
    source_id: str | None = None
    place_of_supply_state: str | None
    place_of_supply_state_code: str | None
    invoice_date: datetime
    status: InvoiceStatus
    payment_status: InvoicePaymentStatus
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
    created_by: int
    created_by_name: str
    created_at: datetime
    issued_at: datetime | None


class InvoiceRead(InvoiceListItemRead):
    items: list[InvoiceItemRead] = Field(default_factory=list)
    taxes: list[InvoiceTaxRead] = Field(default_factory=list)
    payments: list[InvoicePaymentRead] = Field(default_factory=list)
    status_history: list[InvoiceStatusHistoryRead] = Field(default_factory=list)


class POSProductSearchRead(BaseModel):
    product_id: int
    sku: str
    name: str
    primary_barcode: str | None
    hsn_sac_code: str | None
    gst_rate: Decimal
    cess_rate_percent: Decimal
    unit_of_measure: str
    mrp: Decimal | None
    selling_price: Decimal
    unit_cost: Decimal
    branch_id: int | None = None
    branch_name: str | None = None
    quantity_on_hand: Decimal
    is_active: bool


class InvoiceQuoteItemRead(BaseModel):
    product_id: int
    product_name: str
    sku: str
    barcode: str | None
    hsn_sac_code: str | None
    quantity: Decimal
    unit_price: Decimal
    mrp: Decimal | None
    discount: Decimal
    taxable_value: Decimal
    gst_rate: Decimal
    cgst_total: Decimal
    sgst_total: Decimal
    igst_total: Decimal
    cess_total: Decimal
    line_total: Decimal
    gross_profit: Decimal
    quantity_on_hand: Decimal


class InvoiceQuoteRead(BaseModel):
    branch_id: int
    customer_id: int | None
    invoice_type: InvoiceType
    place_of_supply_state: str | None
    place_of_supply_state_code: str | None
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
    items: list[InvoiceQuoteItemRead]
