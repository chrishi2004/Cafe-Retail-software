from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CompanyScopeMixin

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.product import Product
    from app.models.user import User


class StockMovementType(str, enum.Enum):
    SALE = "sale"
    PURCHASE_RECEIVED = "purchase_received"
    MANUAL_ADJUSTMENT = "manual_adjustment"
    RETURN = "return"
    TRANSFER = "transfer"


class Inventory(CompanyScopeMixin, Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    quantity_on_hand: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    quantity_reserved: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    quantity_on_order: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    product: Mapped[Product] = relationship(back_populates="inventory_items")
    branch: Mapped[Branch] = relationship(back_populates="inventory_items")

    __table_args__ = (
        UniqueConstraint("product_id", "branch_id", name="uq_inventory_product_branch"),
        Index("ix_inventory_company_id", "company_id"),
        Index("ix_inventory_product_id", "product_id"),
        Index("ix_inventory_branch_id", "branch_id"),
    )


class StockMovement(CompanyScopeMixin, Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    movement_type: Mapped[StockMovementType] = mapped_column(
        Enum(
            StockMovementType,
            name="stock_movement_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    quantity_change: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    product: Mapped[Product] = relationship(back_populates="stock_movements")
    branch: Mapped[Branch] = relationship(back_populates="stock_movements")
    creator: Mapped[User | None] = relationship(back_populates="stock_movements")

    __table_args__ = (
        Index("ix_stock_movements_company_id", "company_id"),
        Index("ix_stock_movements_product_id", "product_id"),
        Index("ix_stock_movements_branch_id", "branch_id"),
        Index("ix_stock_movements_created_at", "created_at"),
        Index("ix_stock_movements_reference", "reference_type", "reference_id"),
    )
