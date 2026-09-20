from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CompanyScopeMixin, TimestampMixin


class ExpenseCategory(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "expense_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")

    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_expense_categories_company_name"), Index("ix_expense_categories_company_id", "company_id"))


class ExpenseEntry(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "expense_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("expense_categories.id"), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_mode: Mapped[str] = mapped_column(String(40), nullable=False, default="cash")
    vendor_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "idempotency_key", name="uq_expense_entries_company_idempotency"),
        Index("ix_expense_entries_company_branch_date", "company_id", "branch_id", "expense_date"),
        Index("ix_expense_entries_category_id", "category_id"),
    )
