from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import (
    InvoiceSequenceResetRule,
    InvoiceSequenceType,
    PaymentModeType,
    TaxMode,
)


def normalize_blank(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def normalize_upper(value: str | None) -> str | None:
    normalized = normalize_blank(value)
    return normalized.upper() if normalized else None


class BusinessProfilePayload(BaseModel):
    company_code: str = Field(default="HYBRID_RETAIL", min_length=1, max_length=40)
    legal_name: str = Field(min_length=1, max_length=240)
    trade_name: str | None = Field(default=None, max_length=200)
    pan: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = None
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    state_code: str | None = Field(default=None, min_length=2, max_length=2)
    pincode: str | None = Field(default=None, max_length=12)
    gstin: str | None = Field(default=None, min_length=15, max_length=15)
    default_tax_mode: TaxMode = TaxMode.NON_GST
    default_currency: str = Field(default="INR", min_length=3, max_length=3)
    terms_and_conditions: str | None = None

    @field_validator("company_code")
    @classmethod
    def normalize_company_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("legal_name")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("trade_name", "pan", "email", "phone", "address", "city", "state", "pincode", "terms_and_conditions")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return normalize_blank(value)

    @field_validator("pan", "gstin", "state_code", "default_currency")
    @classmethod
    def normalize_codes(cls, value: str | None) -> str | None:
        return normalize_upper(value)

    @model_validator(mode="after")
    def gst_requires_state(self) -> BusinessProfilePayload:
        if self.gstin and not self.state_code:
            raise ValueError("State code is required when GSTIN is configured.")
        return self


class BusinessProfileRead(BusinessProfilePayload):
    company_id: int
    business_profile_id: int
    gst_registration_id: int | None = None
    created_at: datetime
    updated_at: datetime


class TaxRateBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    rate_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    cess_percent: Decimal = Field(default=0, ge=0, le=100, max_digits=5, decimal_places=2)
    description: str | None = None
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return normalize_blank(value)


class TaxRateCreate(TaxRateBase):
    pass


class TaxRateUpdate(TaxRateBase):
    pass


class TaxRateRead(TaxRateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentModeBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    mode_type: PaymentModeType
    requires_reference: bool = False
    display_order: int = Field(default=0, ge=0, le=999)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class PaymentModeCreate(PaymentModeBase):
    company_id: int | None = None


class PaymentModeUpdate(PaymentModeBase):
    pass


class PaymentModeRead(PaymentModeBase):
    id: int
    company_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceSequenceBase(BaseModel):
    company_id: int | None = None
    branch_id: int | None = None
    invoice_type: InvoiceSequenceType = InvoiceSequenceType.NON_GST_INVOICE
    fiscal_year: str = Field(min_length=1, max_length=20)
    prefix: str = Field(min_length=1, max_length=30)
    suffix: str | None = Field(default=None, max_length=30)
    next_number: int = Field(default=1, ge=1)
    padding: int = Field(default=5, ge=1, le=12)
    reset_rule: InvoiceSequenceResetRule = InvoiceSequenceResetRule.FISCAL_YEAR
    is_active: bool = True

    @field_validator("fiscal_year", "prefix")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("suffix")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return normalize_blank(value)


class InvoiceSequenceCreate(InvoiceSequenceBase):
    pass


class InvoiceSequenceUpdate(InvoiceSequenceBase):
    pass


class InvoiceSequenceRead(InvoiceSequenceBase):
    id: int
    company_id: int
    last_generated_at: datetime | None = None
    preview_next_number: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
