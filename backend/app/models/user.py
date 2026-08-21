from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.branch import Branch
    from app.models.chat import AIChatSession
    from app.models.inventory import StockMovement
    from app.models.purchase_order import PurchaseOrder
    from app.models.sale import Sale


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    STORE_MANAGER = "store_manager"
    STAFF = "staff"
    ORDER_TAKER = "order_taker"
    KITCHEN = "kitchen"
    ANALYST = "analyst"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_group_id: Mapped[int] = mapped_column(
        ForeignKey("business_groups.id"),
        nullable=False,
        server_default="1",
    )
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_step_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # TOTP MFA. Secrets are application-encrypted before persistence; recovery
    # codes are stored only as one-way SHA-256 hashes.
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    mfa_recovery_hashes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    mfa_enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    branch: Mapped[Branch | None] = relationship(back_populates="users")
    sales: Mapped[list[Sale]] = relationship(back_populates="creator")
    stock_movements: Mapped[list[StockMovement]] = relationship(back_populates="creator")
    created_purchase_orders: Mapped[list[PurchaseOrder]] = relationship(
        back_populates="creator",
        foreign_keys="PurchaseOrder.created_by",
    )
    approved_purchase_orders: Mapped[list[PurchaseOrder]] = relationship(
        back_populates="approver",
        foreign_keys="PurchaseOrder.approved_by",
    )
    ai_chat_sessions: Mapped[list[AIChatSession]] = relationship(back_populates="user")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="user")

    __table_args__ = (
        Index("ix_users_business_group_id", "business_group_id"),
        Index("ix_users_company_id", "company_id"),
        Index("ix_users_branch_id", "branch_id"),
        CheckConstraint(
            "(role = 'super_admin' AND company_id IS NULL AND branch_id IS NULL) OR "
            "(role <> 'super_admin' AND company_id IS NOT NULL)",
            name="users_role_scope",
        ),
    )
