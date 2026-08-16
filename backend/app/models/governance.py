from __future__ import annotations

import enum
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CompanyScopeMixin, TimestampMixin


def enum_column(enum_cls: type[enum.Enum], name: str):
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda values: [member.value for member in values],
    )


class ClosingStatus(str, enum.Enum):
    OPEN = "open"
    SUBMITTED = "submitted"
    CLOSED = "closed"
    REOPENED = "reopened"


class PurgeStatus(str, enum.Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class ReversalType(str, enum.Enum):
    VOID = "void"
    REFUND = "refund"
    STOCK_COMPENSATION = "stock_compensation"
    LEDGER_COMPENSATION = "ledger_compensation"


class BusinessDayClosure(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "business_day_closures"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    opening_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    cash_collections: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    cash_refunds: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    cash_expenses: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    expected_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    counted_cash: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    variance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    non_cash_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    status: Mapped[ClosingStatus] = mapped_column(enum_column(ClosingStatus, "closing_status"), nullable=False, default=ClosingStatus.OPEN)
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reopened_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reopened_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "branch_id", "business_date", name="uq_business_day_closure_scope_date"),
        Index("ix_business_day_closures_company_branch_date", "company_id", "branch_id", "business_date"),
        Index("ix_business_day_closures_status", "status"),
    )


class FinancialReversal(TimestampMixin, Base):
    __tablename__ = "financial_reversals"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    reversal_type: Mapped[ReversalType] = mapped_column(enum_column(ReversalType, "reversal_type"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    compensation_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    __table_args__ = (
        Index("ix_financial_reversals_invoice_id", "invoice_id"),
        Index("ix_financial_reversals_company_branch", "company_id", "branch_id"),
    )


class PurgeRequest(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "record_purge_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[PurgeStatus] = mapped_column(enum_column(PurgeStatus, "purge_status"), nullable=False, default=PurgeStatus.REQUESTED)
    dependency_report: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    backup_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    second_approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    step_up_granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    typed_confirmation: Mapped[str | None] = mapped_column(String(160), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        Index("ix_record_purge_requests_scope_status", "company_id", "branch_id", "status"),
        Index("ix_record_purge_requests_entity", "entity_type", "entity_id"),
    )


class RecordTombstone(Base):
    __tablename__ = "record_tombstones"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[int] = mapped_column(nullable=False)
    before_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    purged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    __table_args__ = (
        Index("ix_record_tombstones_scope_entity", "company_id", "entity_type", "entity_id"),
    )
