from __future__ import annotations

import enum
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CompanyScopeMixin, TimestampMixin


class CashRegisterSessionStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


class CashRegisterMovementType(str, enum.Enum):
    CASH_IN = "cash_in"
    CASH_OUT = "cash_out"
    EXPENSE = "expense"
    ADJUSTMENT = "adjustment"


def enum_column(enum_cls: type[enum.Enum], name: str):
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda values: [member.value for member in values],
    )


class CashRegisterSession(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "cash_register_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    status: Mapped[CashRegisterSessionStatus] = mapped_column(
        enum_column(CashRegisterSessionStatus, "cash_register_session_status"),
        nullable=False,
        default=CashRegisterSessionStatus.OPEN,
        server_default=CashRegisterSessionStatus.OPEN.value,
    )
    opening_float: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    expected_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    counted_cash: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    variance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    opened_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "uq_cash_register_sessions_one_open",
            "company_id",
            "branch_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
            sqlite_where=text("status = 'open'"),
        ),
        Index("ix_cash_register_sessions_scope_status", "company_id", "branch_id", "status"),
        CheckConstraint("opening_float >= 0", name="cash_register_opening_float_non_negative"),
    )


class CashRegisterMovement(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "cash_register_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("cash_register_sessions.id", ondelete="CASCADE"), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    movement_type: Mapped[CashRegisterMovementType] = mapped_column(
        enum_column(CashRegisterMovementType, "cash_register_movement_type"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "idempotency_key", name="uq_cash_register_movements_scope_idempotency"),
        Index("ix_cash_register_movements_session", "session_id", "occurred_at"),
        CheckConstraint("amount > 0", name="cash_register_movement_amount_positive"),
    )
