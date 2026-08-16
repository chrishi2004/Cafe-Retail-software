from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CompanyScopeMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.forecast import Forecast
    from app.models.product import Product


class Category(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    products: Mapped[list[Product]] = relationship(back_populates="category")
    forecasts: Mapped[list[Forecast]] = relationship(back_populates="category")

    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_categories_company_name"),
        Index("ix_categories_company_id", "company_id"),
    )
