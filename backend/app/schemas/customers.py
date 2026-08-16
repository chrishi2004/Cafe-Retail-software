from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import CustomerAddressType, CustomerLedgerEntryType


def normalize_blank(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def normalize_upper(value: str | None) -> str | None:
    normalized = normalize_blank(value)
    return normalized.upper() if normalized else None


class CustomerAddressRead(BaseModel):
    id: int
    address_type: CustomerAddressType
    recipient_name: str | None = None
    phone: str | None = None
    address: str
    city: str | None = None
    state: str | None = None
    state_code: str | None = None
    pincode: str | None = None
    gstin: str | None = None
    is_default: bool

    model_config = ConfigDict(from_attributes=True)


class CustomerBase(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    gstin: str | None = Field(default=None, min_length=15, max_length=15)
    billing_address: str | None = None
    shipping_address: str | None = None
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    state_code: str | None = Field(default=None, min_length=2, max_length=2)
    pincode: str | None = Field(default=None, max_length=12)
    branch_id: int | None = None
    company_id: int | None = None
    credit_limit: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    opening_balance: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("phone", "billing_address", "shipping_address", "city", "state", "pincode")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return normalize_blank(value)

    @field_validator("gstin", "state_code")
    @classmethod
    def normalize_codes(cls, value: str | None) -> str | None:
        return normalize_upper(value)

    @model_validator(mode="after")
    def gstin_requires_state_code(self) -> "CustomerBase":
        if self.gstin and not self.state_code:
            raise ValueError("State code is required when customer GSTIN is configured.")
        return self


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(CustomerBase):
    pass


class CustomerRead(CustomerBase):
    id: int
    branch_name: str | None = None
    outstanding_balance: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    available_credit: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    addresses: list[CustomerAddressRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerLedgerEntryRead(BaseModel):
    id: int
    customer_id: int
    branch_id: int | None
    branch_name: str | None = None
    entry_type: CustomerLedgerEntryType
    debit: Decimal
    credit: Decimal
    running_balance: Decimal
    reference_type: str | None = None
    reference_id: int | None = None
    reason: str | None = None
    notes: str | None = None
    created_by: int | None = None
    created_by_name: str | None = None
    entry_datetime: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerPaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    branch_id: int | None = None
    payment_mode_id: int | None = None
    payment_datetime: datetime | None = None
    reference_number: str | None = Field(default=None, max_length=120)
    notes: str | None = None

    @field_validator("reference_number", "notes")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return normalize_blank(value)


class CustomerPaymentRead(BaseModel):
    id: int
    customer_id: int
    branch_id: int | None
    branch_name: str | None = None
    payment_mode_id: int | None
    payment_mode_name: str | None = None
    amount: Decimal
    payment_datetime: datetime
    reference_number: str | None = None
    notes: str | None = None
    received_by: int | None = None
    received_by_name: str | None = None
    ledger_entry_id: int | None = None
    outstanding_balance: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerOutstandingRead(BaseModel):
    customer_id: int
    customer_name: str
    phone: str | None = None
    gstin: str | None = None
    branch_id: int | None = None
    branch_name: str | None = None
    credit_limit: Decimal
    outstanding_balance: Decimal
    available_credit: Decimal
    is_over_credit_limit: bool
    is_active: bool
