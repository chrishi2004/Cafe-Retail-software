from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models import ForecastType


class ForecastTrend(str, enum.Enum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"


class ForecastRunCreate(BaseModel):
    forecast_type: ForecastType = ForecastType.REVENUE
    horizon_days: int = Field(default=30)
    branch_id: int | None = None
    category_id: int | None = None
    product_id: int | None = None
    as_of_date: date | None = None

    @field_validator("horizon_days")
    @classmethod
    def validate_horizon(cls, value: int) -> int:
        if value not in {7, 30, 90}:
            raise ValueError("Forecast horizon must be 7, 30, or 90 days.")
        return value


class ForecastPointRead(BaseModel):
    date: date
    value: Decimal


class ForecastRead(BaseModel):
    id: int
    product_id: int | None
    product_name: str | None
    category_id: int | None
    category_name: str | None
    branch_id: int | None
    branch_name: str | None
    forecast_type: ForecastType
    forecast_start_date: date
    forecast_end_date: date
    forecast_value: Decimal
    confidence_low: Decimal | None
    confidence_high: Decimal | None
    model_name: str
    created_at: datetime


class ForecastRunRead(BaseModel):
    forecast: ForecastRead | None
    forecast_type: ForecastType
    horizon_days: int
    branch_id: int | None
    branch_name: str | None
    category_id: int | None
    category_name: str | None
    product_id: int | None
    product_name: str | None
    history_start_date: date | None
    history_end_date: date | None
    forecast_start_date: date | None
    forecast_end_date: date | None
    forecast_value: Decimal
    confidence_low: Decimal | None
    confidence_high: Decimal | None
    average_daily_value: Decimal
    trend_label: ForecastTrend
    trend_percent: Decimal | None
    model_name: str
    insufficient_data: bool
    message: str
    historical_points: list[ForecastPointRead]
    forecast_points: list[ForecastPointRead]
