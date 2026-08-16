from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models import CustomerDetailsOnBill, TaxMode, TaxRegistrationStatus


class TaxOperationRead(BaseModel):
    company_id: int
    company_name: str
    tax_registration_status: TaxRegistrationStatus
    default_tax_mode: TaxMode
    gst_effective_from: date | None
    customer_details_on_bill: CustomerDetailsOnBill
    b2b_gst_enabled: bool
    include_customer_in_gst_reports: bool
    gst_registration_id: int | None
    gst_registration_configured: bool
    gst_registration_active: bool
    gstin_masked: str | None
    can_activate_gst: bool
    missing_activation_prerequisites: list[str]
    compliance_notice: str


class TaxOperationSettingsUpdate(BaseModel):
    tax_registration_status: TaxRegistrationStatus
    customer_details_on_bill: CustomerDetailsOnBill = CustomerDetailsOnBill.BASIC
    b2b_gst_enabled: bool = False
    include_customer_in_gst_reports: bool = False
    registration_id: int | None = None
    registration_active: bool = False


class GSTActivationRequest(BaseModel):
    effective_from: date
    acknowledge_professional_review: bool = False
    confirmation: str = Field(min_length=1, max_length=200)


class VentureTurnoverRead(BaseModel):
    company_id: int
    company_name: str
    business_type: str
    turnover: Decimal


class CombinedTurnoverRead(BaseModel):
    business_group_id: int
    ventures: list[VentureTurnoverRead]
    combined_turnover: Decimal
    review_notice: str
