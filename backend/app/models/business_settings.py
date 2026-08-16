from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class TaxMode(str, enum.Enum):
    GST = "gst"
    NON_GST = "non_gst"


class TaxRegistrationStatus(str, enum.Enum):
    UNREGISTERED = "unregistered"
    REGISTERED = "registered"


class CustomerDetailsOnBill(str, enum.Enum):
    HIDDEN = "hidden"
    BASIC = "basic"
    FULL = "full"


class BusinessType(str, enum.Enum):
    RETAIL = "retail"
    CAFE = "cafe"


class InvoiceSequenceResetRule(str, enum.Enum):
    NEVER = "never"
    FISCAL_YEAR = "fiscal_year"
    CALENDAR_YEAR = "calendar_year"
    MONTHLY = "monthly"


class InvoiceSequenceType(str, enum.Enum):
    GST_INVOICE = "gst_invoice"
    NON_GST_INVOICE = "non_gst_invoice"
    CREDIT_NOTE = "credit_note"
    PURCHASE_BILL = "purchase_bill"


class PaymentModeType(str, enum.Enum):
    CASH = "cash"
    UPI = "upi"
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    WALLET = "wallet"
    CHEQUE = "cheque"
    CREDIT = "credit"
    OTHER = "other"


class PrintTemplateType(str, enum.Enum):
    A4_GST_INVOICE = "a4_gst_invoice"
    A5_INVOICE = "a5_invoice"
    POS_58MM = "pos_58mm"
    POS_80MM = "pos_80mm"
    NON_GST_INVOICE = "non_gst_invoice"
    CREDIT_NOTE = "credit_note"
    PURCHASE_BILL = "purchase_bill"


def enum_column(enum_cls: type[enum.Enum], name: str):
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda enum_values: [member.value for member in enum_values],
    )


class BusinessGroup(TimestampMixin, Base):
    __tablename__ = "business_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    legal_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR", server_default="INR")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_group_id: Mapped[int] = mapped_column(
        ForeignKey("business_groups.id"),
        nullable=False,
        server_default="1",
    )
    business_type: Mapped[BusinessType] = mapped_column(
        enum_column(BusinessType, "business_type"),
        nullable=False,
        default=BusinessType.RETAIL,
        server_default=BusinessType.RETAIL.value,
    )
    slug: Mapped[str] = mapped_column(String(120), nullable=False, default="retail", server_default="retail")
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    legal_name: Mapped[str] = mapped_column(String(240), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    __table_args__ = (
        UniqueConstraint("business_group_id", "slug", name="uq_companies_group_slug"),
        Index("ix_companies_business_group_id", "business_group_id"),
        Index("ix_companies_business_type", "business_type"),
    )


class BusinessProfile(TimestampMixin, Base):
    __tablename__ = "business_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, unique=True)
    legal_name: Mapped[str] = mapped_column(String(240), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(12), nullable=True)
    tax_registration_status: Mapped[TaxRegistrationStatus] = mapped_column(
        enum_column(TaxRegistrationStatus, "tax_registration_status"),
        nullable=False,
        default=TaxRegistrationStatus.UNREGISTERED,
        server_default=TaxRegistrationStatus.UNREGISTERED.value,
    )
    default_tax_mode: Mapped[TaxMode] = mapped_column(
        enum_column(TaxMode, "tax_mode"),
        nullable=False,
        default=TaxMode.NON_GST,
        server_default=TaxMode.NON_GST.value,
    )
    gst_effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    customer_details_on_bill: Mapped[CustomerDetailsOnBill] = mapped_column(
        enum_column(CustomerDetailsOnBill, "customer_details_on_bill"),
        nullable=False,
        default=CustomerDetailsOnBill.BASIC,
        server_default=CustomerDetailsOnBill.BASIC.value,
    )
    b2b_gst_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    include_customer_in_gst_reports: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    terms_and_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_business_profiles_company_id", "company_id"),)


class GSTRegistration(TimestampMixin, Base):
    __tablename__ = "gst_registrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True, unique=True)
    legal_name: Mapped[str] = mapped_column(String(240), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(12), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    reference_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    __table_args__ = (
        Index("ix_gst_registrations_company_id", "company_id"),
        Index("ix_gst_registrations_branch_id", "branch_id"),
    )


class TaxRate(TimestampMixin, Base):
    __tablename__ = "tax_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    rate_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    cess_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class InvoiceSequence(TimestampMixin, Base):
    __tablename__ = "invoice_sequences"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    invoice_type: Mapped[InvoiceSequenceType] = mapped_column(
        enum_column(InvoiceSequenceType, "invoice_sequence_type"),
        nullable=False,
    )
    fiscal_year: Mapped[str] = mapped_column(String(20), nullable=False)
    prefix: Mapped[str] = mapped_column(String(30), nullable=False)
    suffix: Mapped[str | None] = mapped_column(String(30), nullable=True)
    next_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    padding: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    reset_rule: Mapped[InvoiceSequenceResetRule] = mapped_column(
        enum_column(InvoiceSequenceResetRule, "invoice_sequence_reset_rule"),
        nullable=False,
        default=InvoiceSequenceResetRule.FISCAL_YEAR,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "branch_id",
            "invoice_type",
            "fiscal_year",
            name="uq_invoice_sequences_scope_type_year",
        ),
        Index("ix_invoice_sequences_company_id", "company_id"),
        Index("ix_invoice_sequences_branch_id", "branch_id"),
        Index("ix_invoice_sequences_invoice_type", "invoice_type"),
    )


class PaymentMode(TimestampMixin, Base):
    __tablename__ = "payment_modes"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    mode_type: Mapped[PaymentModeType] = mapped_column(
        enum_column(PaymentModeType, "payment_mode_type"),
        nullable=False,
    )
    requires_reference: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_payment_modes_company_name"),
        Index("ix_payment_modes_company_id", "company_id"),
        Index("ix_payment_modes_mode_type", "mode_type"),
    )


class PrintTemplate(TimestampMixin, Base):
    __tablename__ = "print_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    template_type: Mapped[PrintTemplateType] = mapped_column(
        enum_column(PrintTemplateType, "print_template_type"),
        nullable=False,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    settings_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "template_type", "name", name="uq_print_templates_company_type_name"),
        Index("ix_print_templates_company_id", "company_id"),
    )


class FiscalPeriod(TimestampMixin, Base):
    __tablename__ = "fiscal_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_fiscal_periods_company_name"),
        Index("ix_fiscal_periods_company_id", "company_id"),
        Index("ix_fiscal_periods_dates", "start_date", "end_date"),
    )
