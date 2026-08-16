from __future__ import annotations

import enum
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CompanyScopeMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.business_settings import PaymentMode
    from app.models.customer import Customer
    from app.models.product import Product
    from app.models.sale import Sale
    from app.models.user import User


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    PARTIAL_PAID = "partial_paid"
    CREDIT = "credit"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class InvoiceType(str, enum.Enum):
    GST = "gst"
    NON_GST = "non_gst"


class InvoicePaymentStatus(str, enum.Enum):
    UNPAID = "unpaid"
    PAID = "paid"
    PARTIAL_PAID = "partial_paid"
    CREDIT = "credit"


class InvoiceTaxType(str, enum.Enum):
    CGST = "cgst"
    SGST = "sgst"
    IGST = "igst"
    CESS = "cess"


def enum_column(enum_cls: type[enum.Enum], name: str):
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda enum_values: [member.value for member in enum_values],
    )


class Invoice(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(80), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales.id"), nullable=True)
    invoice_type: Mapped[InvoiceType] = mapped_column(enum_column(InvoiceType, "invoice_type"), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    billing_idempotency_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    billing_request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    place_of_supply_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    place_of_supply_state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    invoice_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        enum_column(InvoiceStatus, "invoice_status"), nullable=False, default=InvoiceStatus.DRAFT
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    discount_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    taxable_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    cgst_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    sgst_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    igst_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    cess_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    round_off: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    grand_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    balance_due: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    payment_status: Mapped[InvoicePaymentStatus] = mapped_column(
        enum_column(InvoicePaymentStatus, "invoice_payment_status"),
        nullable=False,
        default=InvoicePaymentStatus.UNPAID,
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    branch: Mapped[Branch] = relationship()
    customer: Mapped[Customer | None] = relationship()
    sale: Mapped[Sale | None] = relationship()
    creator: Mapped[User] = relationship()
    items: Mapped[list[InvoiceItem]] = relationship(back_populates="invoice", cascade="all, delete-orphan")
    taxes: Mapped[list[InvoiceTax]] = relationship(back_populates="invoice", cascade="all, delete-orphan")
    payments: Mapped[list[InvoicePayment]] = relationship(back_populates="invoice", cascade="all, delete-orphan")
    status_history: Mapped[list[InvoiceStatusHistory]] = relationship(back_populates="invoice", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("company_id", "invoice_number", name="uq_invoices_company_invoice_number"),
        UniqueConstraint(
            "company_id", "billing_idempotency_key_hash", name="uq_invoices_company_billing_idempotency"
        ),
        Index("ix_invoices_company_id", "company_id"),
        Index("ix_invoices_branch_id", "branch_id"),
        Index("ix_invoices_customer_id", "customer_id"),
        Index("ix_invoices_invoice_date", "invoice_date"),
        Index("ix_invoices_status", "status"),
        Index("ix_invoices_payment_status", "payment_status"),
        Index("ix_invoices_sale_id", "sale_id"),
        Index("ix_invoices_company_source", "company_id", "source_type", "source_id"),
        Index(
            "uq_invoices_active_cafe_source",
            "company_id",
            "source_type",
            "source_id",
            unique=True,
            postgresql_where=text(
                "source_type IS NOT NULL AND source_id IS NOT NULL AND status NOT IN ('cancelled', 'returned')"
            ),
            sqlite_where=text(
                "source_type IS NOT NULL AND source_id IS NOT NULL AND status NOT IN ('cancelled', 'returned')"
            ),
        ),
        CheckConstraint("subtotal >= 0", name="invoices_subtotal_non_negative"),
        CheckConstraint("discount_total >= 0", name="invoices_discount_total_non_negative"),
        CheckConstraint("taxable_total >= 0", name="invoices_taxable_total_non_negative"),
        CheckConstraint("grand_total >= 0", name="invoices_grand_total_non_negative"),
        CheckConstraint("paid_amount >= 0", name="invoices_paid_amount_non_negative"),
        CheckConstraint("balance_due >= 0", name="invoices_balance_due_non_negative"),
    )


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    # Nullable only for Cafe prepared-food/menu items that intentionally do not
    # represent a sellable inventory product. Retail items stay product-linked.
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    sku_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    hsn_sac_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    taxable_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    cgst_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    sgst_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    igst_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    cess_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    gross_profit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    invoice: Mapped[Invoice] = relationship(back_populates="items")
    product: Mapped[Product | None] = relationship()
    taxes: Mapped[list[InvoiceTax]] = relationship(back_populates="invoice_item", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_invoice_items_invoice_id", "invoice_id"),
        Index("ix_invoice_items_product_id", "product_id"),
        CheckConstraint("quantity > 0", name="invoice_items_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="invoice_items_unit_price_non_negative"),
        CheckConstraint("discount >= 0", name="invoice_items_discount_non_negative"),
        CheckConstraint("taxable_value >= 0", name="invoice_items_taxable_value_non_negative"),
        CheckConstraint("line_total >= 0", name="invoice_items_line_total_non_negative"),
    )


class InvoiceTax(Base):
    __tablename__ = "invoice_taxes"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    invoice_item_id: Mapped[int | None] = mapped_column(ForeignKey("invoice_items.id", ondelete="CASCADE"), nullable=True)
    tax_type: Mapped[InvoiceTaxType] = mapped_column(enum_column(InvoiceTaxType, "invoice_tax_type"), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    taxable_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    invoice: Mapped[Invoice] = relationship(back_populates="taxes")
    invoice_item: Mapped[InvoiceItem | None] = relationship(back_populates="taxes")

    __table_args__ = (
        Index("ix_invoice_taxes_invoice_id", "invoice_id"),
        Index("ix_invoice_taxes_invoice_item_id", "invoice_item_id"),
        Index("ix_invoice_taxes_tax_type", "tax_type"),
        CheckConstraint("tax_rate >= 0", name="invoice_taxes_rate_non_negative"),
        CheckConstraint("taxable_value >= 0", name="invoice_taxes_taxable_non_negative"),
        CheckConstraint("tax_amount >= 0", name="invoice_taxes_amount_non_negative"),
    )


class InvoicePayment(TimestampMixin, Base):
    __tablename__ = "invoice_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    payment_mode_id: Mapped[int | None] = mapped_column(ForeignKey("payment_modes.id"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_credit_marker: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    invoice: Mapped[Invoice] = relationship(back_populates="payments")
    payment_mode: Mapped[PaymentMode | None] = relationship()
    receiver: Mapped[User | None] = relationship()

    __table_args__ = (
        Index("ix_invoice_payments_invoice_id", "invoice_id"),
        Index("ix_invoice_payments_payment_mode_id", "payment_mode_id"),
        Index("ix_invoice_payments_payment_datetime", "payment_datetime"),
        CheckConstraint("amount > 0", name="invoice_payments_amount_positive"),
    )


class InvoiceStatusHistory(Base):
    __tablename__ = "invoice_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    from_status: Mapped[InvoiceStatus | None] = mapped_column(enum_column(InvoiceStatus, "invoice_status_history_from"), nullable=True)
    to_status: Mapped[InvoiceStatus] = mapped_column(enum_column(InvoiceStatus, "invoice_status_history_to"), nullable=False)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="status_history")
    changer: Mapped[User | None] = relationship()

    __table_args__ = (
        Index("ix_invoice_status_history_invoice_id", "invoice_id"),
        Index("ix_invoice_status_history_changed_at", "changed_at"),
    )
