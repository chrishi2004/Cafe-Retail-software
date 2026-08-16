from __future__ import annotations

import enum
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CompanyScopeMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.business_settings import Company, PaymentMode
    from app.models.user import User


class CustomerAddressType(str, enum.Enum):
    BILLING = "billing"
    SHIPPING = "shipping"


class CustomerLedgerEntryType(str, enum.Enum):
    OPENING_BALANCE = "opening_balance"
    INVOICE = "invoice"
    PAYMENT = "payment"
    CREDIT_NOTE = "credit_note"
    ADJUSTMENT = "adjustment"


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"),
        nullable=False,
        server_default="1",
    )
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    billing_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    shipping_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(12), nullable=True)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    company: Mapped[Company] = relationship()
    branch: Mapped[Branch | None] = relationship()
    addresses: Mapped[list[CustomerAddress]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    ledger_entries: Mapped[list[CustomerLedgerEntry]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    payments: Mapped[list[CustomerPayment]] = relationship(back_populates="customer", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("company_id", "phone", name="uq_customers_company_phone"),
        UniqueConstraint("company_id", "email", name="uq_customers_company_email"),
        UniqueConstraint("company_id", "gstin", name="uq_customers_company_gstin"),
        Index("ix_customers_company_id", "company_id"),
        Index("ix_customers_branch_id", "branch_id"),
        Index("ix_customers_name", "name"),
        Index("ix_customers_phone", "phone"),
        Index("ix_customers_gstin", "gstin"),
        CheckConstraint("credit_limit >= 0", name="customers_credit_limit_non_negative"),
        CheckConstraint("opening_balance >= 0", name="customers_opening_balance_non_negative"),
    )


class CustomerAddress(TimestampMixin, Base):
    __tablename__ = "customer_addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    address_type: Mapped[CustomerAddressType] = mapped_column(
        Enum(
            CustomerAddressType,
            name="customer_address_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    recipient_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(12), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    customer: Mapped[Customer] = relationship(back_populates="addresses")

    __table_args__ = (
        UniqueConstraint("customer_id", "address_type", "is_default", name="uq_customer_addresses_default_type"),
        Index("ix_customer_addresses_customer_id", "customer_id"),
        Index("ix_customer_addresses_type", "address_type"),
    )


class CustomerLedgerEntry(CompanyScopeMixin, Base):
    __tablename__ = "customer_ledger_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    entry_type: Mapped[CustomerLedgerEntryType] = mapped_column(
        Enum(
            CustomerLedgerEntryType,
            name="customer_ledger_entry_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    debit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    credit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    reference_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    entry_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    customer: Mapped[Customer] = relationship(back_populates="ledger_entries")
    branch: Mapped[Branch | None] = relationship()
    creator: Mapped[User | None] = relationship()

    __table_args__ = (
        Index("ix_customer_ledger_entries_company_id", "company_id"),
        Index("ix_customer_ledger_entries_customer_id", "customer_id"),
        Index("ix_customer_ledger_entries_branch_id", "branch_id"),
        Index("ix_customer_ledger_entries_entry_type", "entry_type"),
        Index("ix_customer_ledger_entries_entry_datetime", "entry_datetime"),
        CheckConstraint("debit >= 0", name="customer_ledger_debit_non_negative"),
        CheckConstraint("credit >= 0", name="customer_ledger_credit_non_negative"),
        CheckConstraint("debit > 0 OR credit > 0", name="customer_ledger_has_amount"),
    )


class CustomerPayment(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "customer_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    payment_mode_id: Mapped[int | None] = mapped_column(ForeignKey("payment_modes.id"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    ledger_entry_id: Mapped[int | None] = mapped_column(ForeignKey("customer_ledger_entries.id"), nullable=True)

    customer: Mapped[Customer] = relationship(back_populates="payments")
    branch: Mapped[Branch | None] = relationship()
    payment_mode: Mapped[PaymentMode | None] = relationship()
    receiver: Mapped[User | None] = relationship()
    ledger_entry: Mapped[CustomerLedgerEntry | None] = relationship()

    __table_args__ = (
        Index("ix_customer_payments_company_id", "company_id"),
        Index("ix_customer_payments_customer_id", "customer_id"),
        Index("ix_customer_payments_branch_id", "branch_id"),
        Index("ix_customer_payments_payment_datetime", "payment_datetime"),
        CheckConstraint("amount > 0", name="customer_payments_amount_positive"),
    )
