from __future__ import annotations

import enum
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CompanyScopeMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.product import Product
    from app.models.supplier import Supplier
    from app.models.user import User


class PurchaseBillStatus(str, enum.Enum):
    ISSUED = "issued"
    PARTIAL_PAID = "partial_paid"
    PAID = "paid"
    VOIDED = "voided"


class SupplierLedgerEntryType(str, enum.Enum):
    BILL = "bill"
    PAYMENT = "payment"
    DEBIT_NOTE = "debit_note"
    ADJUSTMENT = "adjustment"


def _enum_column(enum_cls: type[enum.Enum], name: str):
    return Enum(enum_cls, name=name, native_enum=False, create_constraint=True, validate_strings=True,
                values_callable=lambda values: [member.value for member in values])


class PurchaseBill(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "purchase_bills"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    bill_number: Mapped[str] = mapped_column(String(80), nullable=False)
    supplier_invoice_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PurchaseBillStatus] = mapped_column(_enum_column(PurchaseBillStatus, "purchase_bill_status"), nullable=False, default=PurchaseBillStatus.ISSUED)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    balance_due: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)

    items: Mapped[list[PurchaseBillItem]] = relationship(back_populates="bill", cascade="all, delete-orphan")
    supplier: Mapped[Supplier] = relationship()
    branch: Mapped[Branch] = relationship()

    __table_args__ = (
        UniqueConstraint("company_id", "bill_number", name="uq_purchase_bills_company_number"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_purchase_bills_company_idempotency"),
        Index("ix_purchase_bills_company_id", "company_id"),
        Index("ix_purchase_bills_supplier_id", "supplier_id"),
        Index("ix_purchase_bills_branch_id", "branch_id"),
    )


class PurchaseBillItem(Base):
    __tablename__ = "purchase_bill_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    bill_id: Mapped[int] = mapped_column(ForeignKey("purchase_bills.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    bill: Mapped[PurchaseBill] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()

    __table_args__ = (Index("ix_purchase_bill_items_bill_id", "bill_id"),)


class SupplierLedgerEntry(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "supplier_ledger_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    entry_type: Mapped[SupplierLedgerEntryType] = mapped_column(_enum_column(SupplierLedgerEntryType, "supplier_ledger_entry_type"), nullable=False)
    debit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    credit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    reference_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    entry_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "idempotency_key", name="uq_supplier_ledger_company_idempotency"),
        Index("ix_supplier_ledger_company_supplier", "company_id", "supplier_id"),
    )


class PurchaseDebitNote(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "purchase_debit_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    bill_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_bills.id"), nullable=True)
    debit_note_number: Mapped[str] = mapped_column(String(80), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "debit_note_number", name="uq_purchase_debit_notes_company_number"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_purchase_debit_notes_company_idempotency"),
        Index("ix_purchase_debit_notes_supplier_id", "supplier_id"),
    )
