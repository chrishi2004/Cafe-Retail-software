from __future__ import annotations

import enum
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CompanyScopeMixin, TimestampMixin
from app.models.cafe import TableSessionType, enum_column


class CafeOrderSource(str, enum.Enum):
    QR_CUSTOMER = "qr_customer"
    ORDER_TAKER = "order_taker"
    BILLING_COUNTER = "billing_counter"
    MANAGER = "manager"


class CafeOrderStatus(str, enum.Enum):
    PLACED = "placed"
    ACCEPTED = "accepted"
    PREPARING = "preparing"
    READY = "ready"
    SERVED = "served"
    BILL_REQUESTED = "bill_requested"
    BILLED = "billed"
    CLOSED = "closed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class CafeOrderItemStatus(str, enum.Enum):
    PLACED = "placed"
    ACCEPTED = "accepted"
    PREPARING = "preparing"
    READY = "ready"
    SERVED = "served"
    BILLED = "billed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class CafeGuestAccess(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "cafe_guest_access"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_reference: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    table_session_id: Mapped[int] = mapped_column(
        ForeignKey("table_sessions.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_cafe_guest_access_company", "company_id"),
        Index("ix_cafe_guest_access_branch", "branch_id"),
        Index("ix_cafe_guest_access_session", "table_session_id"),
        Index("ix_cafe_guest_access_expires", "expires_at"),
        CheckConstraint("token_version >= 1", name="cafe_guest_access_token_version_positive"),
    )


class CafeOrder(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "cafe_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    table_session_id: Mapped[int | None] = mapped_column(ForeignKey("table_sessions.id"), nullable=True)
    guest_access_id: Mapped[int | None] = mapped_column(ForeignKey("cafe_guest_access.id"), nullable=True)
    order_number: Mapped[str] = mapped_column(String(80), nullable=False)
    order_type: Mapped[TableSessionType] = mapped_column(
        enum_column(TableSessionType, "cafe_order_type"), nullable=False
    )
    source_channel: Mapped[CafeOrderSource] = mapped_column(
        enum_column(CafeOrderSource, "cafe_order_source"), nullable=False
    )
    status: Mapped[CafeOrderStatus] = mapped_column(
        enum_column(CafeOrderStatus, "cafe_order_status"),
        nullable=False,
        default=CafeOrderStatus.PLACED,
        server_default=CafeOrderStatus.PLACED.value,
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    discount_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    estimated_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    customer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    accepted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    billed_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    served_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "order_number", name="uq_cafe_orders_company_number"),
        UniqueConstraint("company_id", "idempotency_key_hash", name="uq_cafe_orders_company_idempotency"),
        Index("ix_cafe_orders_company", "company_id"),
        Index("ix_cafe_orders_branch", "branch_id"),
        Index("ix_cafe_orders_session", "table_session_id"),
        Index("ix_cafe_orders_guest_access", "guest_access_id"),
        Index("ix_cafe_orders_status", "status"),
        Index("ix_cafe_orders_placed_at", "placed_at"),
        Index("ix_cafe_orders_billed_invoice_id", "billed_invoice_id"),
        CheckConstraint("subtotal >= 0", name="cafe_orders_subtotal_non_negative"),
        CheckConstraint("discount_total >= 0", name="cafe_orders_discount_non_negative"),
        CheckConstraint("estimated_total >= 0", name="cafe_orders_total_non_negative"),
        CheckConstraint("version >= 1", name="cafe_orders_version_positive"),
    )


class CafeOrderItem(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "cafe_order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    cafe_order_id: Mapped[int] = mapped_column(ForeignKey("cafe_orders.id", ondelete="CASCADE"), nullable=False)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    menu_item_public_id_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    menu_item_name_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    product_sku_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    item_status: Mapped[CafeOrderItemStatus] = mapped_column(
        enum_column(CafeOrderItemStatus, "cafe_order_item_status"),
        nullable=False,
        default=CafeOrderItemStatus.PLACED,
        server_default=CafeOrderItemStatus.PLACED.value,
    )
    preparation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_channel: Mapped[CafeOrderSource] = mapped_column(
        enum_column(CafeOrderSource, "cafe_order_item_source"), nullable=False
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    billed_invoice_item_id: Mapped[int | None] = mapped_column(ForeignKey("invoice_items.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (
        Index("ix_cafe_order_items_company", "company_id"),
        Index("ix_cafe_order_items_branch", "branch_id"),
        Index("ix_cafe_order_items_order", "cafe_order_id"),
        Index("ix_cafe_order_items_menu_item", "menu_item_id"),
        Index("ix_cafe_order_items_billed_invoice_item_id", "billed_invoice_item_id"),
        CheckConstraint("quantity > 0", name="cafe_order_items_quantity_positive"),
        CheckConstraint("unit_price_snapshot >= 0", name="cafe_order_items_price_non_negative"),
        CheckConstraint("discount_amount >= 0", name="cafe_order_items_discount_non_negative"),
        CheckConstraint("line_total >= 0", name="cafe_order_items_line_total_non_negative"),
        CheckConstraint("version >= 1", name="cafe_order_items_version_positive"),
    )


class CafeOrderStatusHistory(CompanyScopeMixin, Base):
    __tablename__ = "cafe_order_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    cafe_order_id: Mapped[int] = mapped_column(ForeignKey("cafe_orders.id", ondelete="CASCADE"), nullable=False)
    from_status: Mapped[CafeOrderStatus | None] = mapped_column(
        enum_column(CafeOrderStatus, "cafe_order_history_from_status"), nullable=True
    )
    to_status: Mapped[CafeOrderStatus] = mapped_column(
        enum_column(CafeOrderStatus, "cafe_order_history_to_status"), nullable=False
    )
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    guest_action: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_cafe_order_history_company", "company_id"),
        Index("ix_cafe_order_history_branch", "branch_id"),
        Index("ix_cafe_order_history_order", "cafe_order_id"),
        Index("ix_cafe_order_history_created", "created_at"),
    )


class PublicRateLimitBucket(TimestampMixin, Base):
    __tablename__ = "public_rate_limit_buckets"

    id: Mapped[int] = mapped_column(primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        Index("ix_public_rate_limit_window", "window_started_at"),
        CheckConstraint("request_count >= 0", name="public_rate_limit_count_non_negative"),
    )
