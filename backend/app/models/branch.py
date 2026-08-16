from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CompanyScopeMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.chat import AIChatSession
    from app.models.forecast import Forecast
    from app.models.inventory import Inventory, StockMovement
    from app.models.purchase_order import PurchaseOrder
    from app.models.sale import Sale
    from app.models.user import User


class Branch(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    manager_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    users: Mapped[list[User]] = relationship(back_populates="branch")
    inventory_items: Mapped[list[Inventory]] = relationship(back_populates="branch")
    stock_movements: Mapped[list[StockMovement]] = relationship(back_populates="branch")
    sales: Mapped[list[Sale]] = relationship(back_populates="branch")
    purchase_orders: Mapped[list[PurchaseOrder]] = relationship(back_populates="branch")
    forecasts: Mapped[list[Forecast]] = relationship(back_populates="branch")
    ai_chat_sessions: Mapped[list[AIChatSession]] = relationship(back_populates="branch")

    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_branches_company_name"),
        Index("ix_branches_company_id", "company_id"),
    )
