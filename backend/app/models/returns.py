from __future__ import annotations

import enum
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CompanyScopeMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.customer import Customer
    from app.models.invoice import Invoice, InvoiceItem
    from app.models.user import User


class SalesReturnStatus(str, enum.Enum):
    ISSUED = "issued"
    VOIDED = "voided"


class ReturnCondition(str, enum.Enum):
    SALEABLE = "saleable"
    DAMAGED = "damaged"


class RefundMode(str, enum.Enum):
    CUSTOMER_CREDIT = "customer_credit"
    CASH = "cash"
    ORIGINAL_PAYMENT = "original_payment"


class CreditNoteStatus(str, enum.Enum):
    ISSUED = "issued"
    VOIDED = "voided"


def _enum_column(enum_cls: type[enum.Enum], name: str):
    return Enum(enum_cls, name=name, native_enum=False, create_constraint=True, validate_strings=True,
                values_callable=lambda values: [member.value for member in values])


class SalesReturn(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "sales_returns"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    return_number: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[SalesReturnStatus] = mapped_column(_enum_column(SalesReturnStatus, "sales_return_status"), nullable=False, default=SalesReturnStatus.ISSUED)
    refund_mode: Mapped[RefundMode] = mapped_column(_enum_column(RefundMode, "refund_mode"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    returned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)

    branch: Mapped[Branch] = relationship()
    invoice: Mapped[Invoice] = relationship()
    customer: Mapped[Customer | None] = relationship()
    creator: Mapped[User] = relationship()
    items: Mapped[list[SalesReturnItem]] = relationship(back_populates="sales_return", cascade="all, delete-orphan")
    credit_note: Mapped[CreditNote | None] = relationship(back_populates="sales_return", uselist=False)

    __table_args__ = (
        UniqueConstraint("company_id", "return_number", name="uq_sales_returns_company_number"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_sales_returns_company_idempotency"),
        Index("ix_sales_returns_company_id", "company_id"),
        Index("ix_sales_returns_invoice_id", "invoice_id"),
        Index("ix_sales_returns_branch_id", "branch_id"),
        CheckConstraint("total_amount >= 0", name="sales_returns_total_non_negative"),
    )


class SalesReturnItem(Base):
    __tablename__ = "sales_return_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    return_id: Mapped[int] = mapped_column(ForeignKey("sales_returns.id", ondelete="CASCADE"), nullable=False)
    invoice_item_id: Mapped[int] = mapped_column(ForeignKey("invoice_items.id"), nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    taxable_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    condition: Mapped[ReturnCondition] = mapped_column(_enum_column(ReturnCondition, "return_condition"), nullable=False)
    restocked: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")

    sales_return: Mapped[SalesReturn] = relationship(back_populates="items")
    invoice_item: Mapped[InvoiceItem] = relationship()

    __table_args__ = (
        Index("ix_sales_return_items_return_id", "return_id"),
        Index("ix_sales_return_items_invoice_item_id", "invoice_item_id"),
        CheckConstraint("quantity > 0", name="sales_return_items_quantity_positive"),
    )


class CreditNote(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "credit_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    sales_return_id: Mapped[int] = mapped_column(ForeignKey("sales_returns.id"), nullable=False, unique=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    credit_note_number: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[CreditNoteStatus] = mapped_column(_enum_column(CreditNoteStatus, "credit_note_status"), nullable=False, default=CreditNoteStatus.ISSUED)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    refund_mode: Mapped[RefundMode] = mapped_column(_enum_column(RefundMode, "credit_note_refund_mode"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    issued_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)

    sales_return: Mapped[SalesReturn] = relationship(back_populates="credit_note")

    __table_args__ = (
        UniqueConstraint("company_id", "credit_note_number", name="uq_credit_notes_company_number"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_credit_notes_company_idempotency"),
        Index("ix_credit_notes_company_id", "company_id"),
        Index("ix_credit_notes_invoice_id", "invoice_id"),
        CheckConstraint("amount >= 0", name="credit_notes_amount_non_negative"),
    )
