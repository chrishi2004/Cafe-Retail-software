from __future__ import annotations

import enum
import secrets
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CompanyScopeMixin, TimestampMixin


class PreparationArea(str, enum.Enum):
    KITCHEN = "kitchen"
    BEVERAGE = "beverage"
    COUNTER = "counter"
    NONE = "none"


class TableSessionType(str, enum.Enum):
    DINE_IN = "dine_in"
    TAKEAWAY = "takeaway"
    COUNTER = "counter"


class TableSessionStatus(str, enum.Enum):
    OPEN = "open"
    BILL_REQUESTED = "bill_requested"
    BILLED = "billed"
    CLOSED = "closed"
    CANCELLED = "cancelled"


ACTIVE_TABLE_SESSION_STATUSES = (
    TableSessionStatus.OPEN.value,
    TableSessionStatus.BILL_REQUESTED.value,
    TableSessionStatus.BILLED.value,
)


def enum_column(enum_cls: type[enum.Enum], name: str):
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda values: [member.value for member in values],
    )


def _public_id() -> str:
    return secrets.token_urlsafe(18)


class MenuCategory(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "menu_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, default=_public_id)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    __table_args__ = (
        UniqueConstraint("company_id", "branch_id", "name", name="uq_menu_categories_company_branch_name"),
        Index("ix_menu_categories_company_id", "company_id"),
        Index("ix_menu_categories_public_id", "public_id"),
        Index("ix_menu_categories_branch_id", "branch_id"),
        CheckConstraint("display_order >= 0", name="menu_categories_display_order_non_negative"),
    )


class MenuItem(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, default=_public_id)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("menu_categories.id"), nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    preparation_area: Mapped[PreparationArea] = mapped_column(
        enum_column(PreparationArea, "cafe_preparation_area"),
        nullable=False,
        default=PreparationArea.NONE,
        server_default=PreparationArea.NONE.value,
    )
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (
        Index("ix_menu_items_company_id", "company_id"),
        Index("ix_menu_items_public_id", "public_id"),
        Index("ix_menu_items_branch_id", "branch_id"),
        Index("ix_menu_items_category_id", "category_id"),
        Index("ix_menu_items_product_id", "product_id"),
        CheckConstraint("selling_price >= 0", name="menu_items_selling_price_non_negative"),
        CheckConstraint("display_order >= 0", name="menu_items_display_order_non_negative"),
        CheckConstraint("version >= 1", name="menu_items_version_positive"),
    )


class CafeTable(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "cafe_tables"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    table_code: Mapped[str] = mapped_column(String(60), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (
        UniqueConstraint("company_id", "branch_id", "table_code", name="uq_cafe_tables_company_branch_code"),
        Index("ix_cafe_tables_company_id", "company_id"),
        Index("ix_cafe_tables_branch_id", "branch_id"),
        CheckConstraint("capacity IS NULL OR capacity > 0", name="cafe_tables_capacity_positive"),
        CheckConstraint("version >= 1", name="cafe_tables_version_positive"),
    )


class TableQRToken(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "table_qr_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    table_id: Mapped[int] = mapped_column(ForeignKey("cafe_tables.id", ondelete="CASCADE"), nullable=False)
    public_reference: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("ix_table_qr_tokens_company_id", "company_id"),
        Index("ix_table_qr_tokens_branch_id", "branch_id"),
        Index("ix_table_qr_tokens_table_id", "table_id"),
        Index("ix_table_qr_tokens_public_reference", "public_reference"),
        Index("ix_table_qr_tokens_revoked_at", "revoked_at"),
    )


class TableSession(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "table_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    table_id: Mapped[int] = mapped_column(ForeignKey("cafe_tables.id", ondelete="CASCADE"), nullable=False)
    session_type: Mapped[TableSessionType] = mapped_column(
        enum_column(TableSessionType, "table_session_type"),
        nullable=False,
        default=TableSessionType.DINE_IN,
        server_default=TableSessionType.DINE_IN.value,
    )
    status: Mapped[TableSessionStatus] = mapped_column(
        enum_column(TableSessionStatus, "table_session_status"),
        nullable=False,
        default=TableSessionStatus.OPEN,
        server_default=TableSessionStatus.OPEN.value,
    )
    opened_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    bill_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    billed_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (
        Index("ix_table_sessions_company_id", "company_id"),
        Index("ix_table_sessions_branch_id", "branch_id"),
        Index("ix_table_sessions_table_id", "table_id"),
        Index("ix_table_sessions_public_id", "public_id"),
        Index("ix_table_sessions_status", "status"),
        Index("ix_table_sessions_billed_invoice_id", "billed_invoice_id"),
        Index(
            "uq_table_sessions_one_active_per_table",
            "table_id",
            unique=True,
            postgresql_where=text("status IN ('open', 'bill_requested', 'billed')"),
            sqlite_where=text("status IN ('open', 'bill_requested', 'billed')"),
        ),
        CheckConstraint("version >= 1", name="table_sessions_version_positive"),
    )
