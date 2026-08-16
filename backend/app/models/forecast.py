from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CompanyScopeMixin

if TYPE_CHECKING:
    from app.models.branch import Branch
    from app.models.category import Category
    from app.models.product import Product


class ForecastType(str, enum.Enum):
    REVENUE = "revenue"
    UNITS = "units"
    DEMAND = "demand"


class Forecast(CompanyScopeMixin, Base):
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    forecast_type: Mapped[ForecastType] = mapped_column(
        Enum(
            ForecastType,
            name="forecast_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    forecast_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    forecast_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    forecast_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    confidence_low: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    confidence_high: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    product: Mapped[Product | None] = relationship(back_populates="forecasts")
    category: Mapped[Category | None] = relationship(back_populates="forecasts")
    branch: Mapped[Branch | None] = relationship(back_populates="forecasts")

    __table_args__ = (
        Index("ix_forecasts_company_id", "company_id"),
        Index("ix_forecasts_product_id", "product_id"),
        Index("ix_forecasts_category_id", "category_id"),
        Index("ix_forecasts_branch_id", "branch_id"),
        Index("ix_forecasts_type_dates", "forecast_type", "forecast_start_date", "forecast_end_date"),
    )
