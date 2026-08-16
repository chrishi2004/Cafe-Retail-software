from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import BranchScope
from app.api.errors import raise_forbidden, raise_not_found
from app.models import Branch, Category, Forecast, ForecastType, Product, Sale, SaleItem
from app.schemas.forecasts import (
    ForecastPointRead,
    ForecastRead,
    ForecastRunCreate,
    ForecastRunRead,
    ForecastTrend,
)

MONEY = Decimal("0.01")
QUANTITY = Decimal("0.01")
PERCENT = Decimal("0.01")
MODEL_NAME = "moving_average_trend_v1"
MIN_ACTIVE_DAYS = 5
MIN_HISTORY_DAYS = 14


@dataclass(frozen=True)
class ForecastFilters:
    forecast_type: ForecastType | None = None
    branch_id: int | None = None
    category_id: int | None = None
    product_id: int | None = None
    limit: int = 50


@dataclass(frozen=True)
class ForecastScope:
    branch_id: int | None
    branch_name: str | None
    category_id: int | None
    category_name: str | None
    product_id: int | None
    product_name: str | None


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def quantity(value: Decimal) -> Decimal:
    return value.quantize(QUANTITY, rounding=ROUND_HALF_UP)


def metric_value(value: Decimal, forecast_type: ForecastType) -> Decimal:
    return money(value) if forecast_type == ForecastType.REVENUE else quantity(value)


def percent(value: Decimal) -> Decimal:
    return value.quantize(PERCENT, rounding=ROUND_HALF_UP)


def date_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(start_date, time.min, tzinfo=UTC),
        datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC),
    )


def validate_forecast_branch_scope(branch_scope: BranchScope, branch_id: int | None) -> int | None:
    if branch_scope.all_branches:
        return branch_id
    if branch_id is not None and branch_id not in branch_scope.branch_ids:
        raise_forbidden("You can only access forecasts for your assigned branch.")
    return branch_id or branch_scope.branch_ids[0]


def resolve_scope(db: Session, *, payload: ForecastRunCreate, branch_scope: BranchScope) -> ForecastScope:
    branch_id = validate_forecast_branch_scope(branch_scope, payload.branch_id)
    branch_name = None
    if branch_id is not None:
        branch = db.get(Branch, branch_id)
        if branch is None:
            raise_not_found("Branch not found.")
        branch_name = branch.name

    category_name = None
    if payload.category_id is not None:
        category = db.get(Category, payload.category_id)
        if category is None:
            raise_not_found("Category not found.")
        category_name = category.name

    product_name = None
    if payload.product_id is not None:
        product = db.get(Product, payload.product_id)
        if product is None:
            raise_not_found("Product not found.")
        product_name = product.name
        if payload.category_id is not None and product.category_id != payload.category_id:
            raise_forbidden("Selected product does not belong to the selected category.")

    return ForecastScope(
        branch_id=branch_id,
        branch_name=branch_name,
        category_id=payload.category_id,
        category_name=category_name,
        product_id=payload.product_id,
        product_name=product_name,
    )


def latest_sale_date(
    db: Session,
    *,
    branch_scope: BranchScope,
    scope: ForecastScope,
) -> date | None:
    statement = select(Sale.sale_datetime).join(Sale.items).join(SaleItem.product)
    if scope.branch_id is not None:
        statement = statement.where(Sale.branch_id == scope.branch_id)
    elif not branch_scope.all_branches:
        statement = statement.where(Sale.branch_id.in_(branch_scope.branch_ids))
    if scope.category_id is not None:
        statement = statement.where(Product.category_id == scope.category_id)
    if scope.product_id is not None:
        statement = statement.where(SaleItem.product_id == scope.product_id)
    statement = statement.order_by(Sale.sale_datetime.desc()).limit(1)
    value = db.scalar(statement)
    return value.date() if value else None


def load_daily_history(
    db: Session,
    *,
    branch_scope: BranchScope,
    scope: ForecastScope,
    forecast_type: ForecastType,
    start_date: date,
    end_date: date,
) -> list[ForecastPointRead]:
    start, end = date_bounds(start_date, end_date)
    statement = (
        select(SaleItem, Sale, Product)
        .join(SaleItem.sale)
        .join(SaleItem.product)
        .where(Sale.sale_datetime >= start, Sale.sale_datetime < end)
    )
    if scope.branch_id is not None:
        statement = statement.where(Sale.branch_id == scope.branch_id)
    elif not branch_scope.all_branches:
        statement = statement.where(Sale.branch_id.in_(branch_scope.branch_ids))
    if scope.category_id is not None:
        statement = statement.where(Product.category_id == scope.category_id)
    if scope.product_id is not None:
        statement = statement.where(SaleItem.product_id == scope.product_id)

    grouped: dict[date, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for item, sale, _product in db.execute(statement).all():
        sale_date = sale.sale_datetime.date()
        grouped[sale_date] += item.line_total if forecast_type == ForecastType.REVENUE else item.quantity

    points: list[ForecastPointRead] = []
    current = start_date
    while current <= end_date:
        points.append(ForecastPointRead(date=current, value=metric_value(grouped[current], forecast_type)))
        current += timedelta(days=1)
    return points


def trend_from_windows(recent_average: Decimal, previous_average: Decimal) -> tuple[ForecastTrend, Decimal | None]:
    if previous_average == 0:
        if recent_average == 0:
            return ForecastTrend.STABLE, None
        return ForecastTrend.INCREASING, None

    trend_percent = percent((recent_average - previous_average) / previous_average * Decimal("100"))
    if abs(trend_percent) < Decimal("5.00"):
        return ForecastTrend.STABLE, trend_percent
    if trend_percent > 0:
        return ForecastTrend.INCREASING, trend_percent
    return ForecastTrend.DECREASING, trend_percent


def build_forecast_points(
    *,
    historical_points: list[ForecastPointRead],
    forecast_type: ForecastType,
    horizon_days: int,
    forecast_start_date: date,
) -> tuple[list[ForecastPointRead], Decimal, Decimal, ForecastTrend, Decimal | None]:
    values = [point.value for point in historical_points]
    window = min(28, max(7, len(values) // 3))
    recent_values = values[-window:]
    previous_values = values[-(window * 2) : -window] if len(values) >= window * 2 else values[:-window]
    recent_average = sum(recent_values, Decimal("0.00")) / Decimal(len(recent_values))
    previous_average = (
        sum(previous_values, Decimal("0.00")) / Decimal(len(previous_values))
        if previous_values
        else recent_average
    )
    trend_label, trend_percent = trend_from_windows(recent_average, previous_average)

    daily_adjustment = Decimal("0.00")
    if previous_values:
        daily_adjustment = (recent_average - previous_average) / Decimal(max(len(previous_values), 1)) / Decimal("2")

    forecast_points: list[ForecastPointRead] = []
    for offset in range(horizon_days):
        raw_value = recent_average + daily_adjustment * Decimal(offset + 1)
        forecast_points.append(
            ForecastPointRead(
                date=forecast_start_date + timedelta(days=offset),
                value=metric_value(max(raw_value, Decimal("0.00")), forecast_type),
            )
        )

    forecast_value = metric_value(sum((point.value for point in forecast_points), Decimal("0.00")), forecast_type)
    return forecast_points, forecast_value, metric_value(recent_average, forecast_type), trend_label, trend_percent


def forecast_read(forecast: Forecast) -> ForecastRead:
    return ForecastRead(
        id=forecast.id,
        product_id=forecast.product_id,
        product_name=forecast.product.name if forecast.product else None,
        category_id=forecast.category_id,
        category_name=forecast.category.name if forecast.category else None,
        branch_id=forecast.branch_id,
        branch_name=forecast.branch.name if forecast.branch else None,
        forecast_type=forecast.forecast_type,
        forecast_start_date=forecast.forecast_start_date,
        forecast_end_date=forecast.forecast_end_date,
        forecast_value=forecast.forecast_value,
        confidence_low=forecast.confidence_low,
        confidence_high=forecast.confidence_high,
        model_name=forecast.model_name,
        created_at=forecast.created_at,
    )


def insufficient_response(
    *,
    payload: ForecastRunCreate,
    scope: ForecastScope,
    historical_points: list[ForecastPointRead],
    message: str,
) -> ForecastRunRead:
    history_start = historical_points[0].date if historical_points else None
    history_end = historical_points[-1].date if historical_points else None
    return ForecastRunRead(
        forecast=None,
        forecast_type=payload.forecast_type,
        horizon_days=payload.horizon_days,
        branch_id=scope.branch_id,
        branch_name=scope.branch_name,
        category_id=scope.category_id,
        category_name=scope.category_name,
        product_id=scope.product_id,
        product_name=scope.product_name,
        history_start_date=history_start,
        history_end_date=history_end,
        forecast_start_date=None,
        forecast_end_date=None,
        forecast_value=Decimal("0.00"),
        confidence_low=None,
        confidence_high=None,
        average_daily_value=Decimal("0.00"),
        trend_label=ForecastTrend.STABLE,
        trend_percent=None,
        model_name=MODEL_NAME,
        insufficient_data=True,
        message=message,
        historical_points=historical_points,
        forecast_points=[],
    )


def run_forecast(
    db: Session,
    *,
    payload: ForecastRunCreate,
    branch_scope: BranchScope,
) -> ForecastRunRead:
    scope = resolve_scope(db, payload=payload, branch_scope=branch_scope)
    as_of_date = payload.as_of_date or latest_sale_date(db, branch_scope=branch_scope, scope=scope) or datetime.now(UTC).date()
    history_days = max(90, payload.horizon_days * 2)
    history_start_date = as_of_date - timedelta(days=history_days - 1)
    historical_points = load_daily_history(
        db,
        branch_scope=branch_scope,
        scope=scope,
        forecast_type=payload.forecast_type,
        start_date=history_start_date,
        end_date=as_of_date,
    )

    active_days = sum(1 for point in historical_points if point.value > 0)
    total_history_value = sum((point.value for point in historical_points), Decimal("0.00"))
    if len(historical_points) < MIN_HISTORY_DAYS or active_days < MIN_ACTIVE_DAYS or total_history_value <= 0:
        return insufficient_response(
            payload=payload,
            scope=scope,
            historical_points=historical_points,
            message=(
                "Not enough historical sales data for this forecast. "
                "Need at least 5 active sales days in the selected scope."
            ),
        )

    forecast_start_date = as_of_date + timedelta(days=1)
    forecast_end_date = forecast_start_date + timedelta(days=payload.horizon_days - 1)
    forecast_points, forecast_value, average_daily_value, trend_label, trend_percent = build_forecast_points(
        historical_points=historical_points,
        forecast_type=payload.forecast_type,
        horizon_days=payload.horizon_days,
        forecast_start_date=forecast_start_date,
    )
    confidence_low = metric_value(forecast_value * Decimal("0.85"), payload.forecast_type)
    confidence_high = metric_value(forecast_value * Decimal("1.15"), payload.forecast_type)

    forecast = Forecast(
        product_id=scope.product_id,
        category_id=scope.category_id,
        branch_id=scope.branch_id,
        forecast_type=payload.forecast_type,
        forecast_start_date=forecast_start_date,
        forecast_end_date=forecast_end_date,
        forecast_value=forecast_value,
        confidence_low=confidence_low,
        confidence_high=confidence_high,
        model_name=MODEL_NAME,
    )
    db.add(forecast)
    db.commit()
    db.refresh(forecast)
    forecast = db.scalar(
        select(Forecast)
        .options(joinedload(Forecast.product), joinedload(Forecast.category), joinedload(Forecast.branch))
        .where(Forecast.id == forecast.id)
    )
    if forecast is None:
        raise_not_found("Forecast could not be loaded after save.")

    scope_label = scope.product_name or scope.category_name or scope.branch_name or "the selected business"
    if trend_label == ForecastTrend.STABLE:
        trend_text = "Sales are broadly stable"
    elif trend_label == ForecastTrend.INCREASING:
        trend_text = "Sales are trending upward"
    else:
        trend_text = "Sales are trending downward"

    metric_label = "revenue" if payload.forecast_type == ForecastType.REVENUE else "units"
    message = (
        f"{trend_text} for {scope_label}. The {payload.horizon_days}-day forecast is "
        f"{forecast_value} {metric_label}, based on a recent moving average with a simple trend adjustment."
    )

    return ForecastRunRead(
        forecast=forecast_read(forecast),
        forecast_type=payload.forecast_type,
        horizon_days=payload.horizon_days,
        branch_id=scope.branch_id,
        branch_name=scope.branch_name,
        category_id=scope.category_id,
        category_name=scope.category_name,
        product_id=scope.product_id,
        product_name=scope.product_name,
        history_start_date=history_start_date,
        history_end_date=as_of_date,
        forecast_start_date=forecast_start_date,
        forecast_end_date=forecast_end_date,
        forecast_value=forecast_value,
        confidence_low=confidence_low,
        confidence_high=confidence_high,
        average_daily_value=average_daily_value,
        trend_label=trend_label,
        trend_percent=trend_percent,
        model_name=MODEL_NAME,
        insufficient_data=False,
        message=message,
        historical_points=historical_points,
        forecast_points=forecast_points,
    )


def apply_forecast_scope(statement, branch_scope: BranchScope, branch_id: int | None):
    if branch_scope.all_branches:
        if branch_id is not None:
            return statement.where(Forecast.branch_id == branch_id)
        return statement

    if branch_id is not None and branch_id not in branch_scope.branch_ids:
        raise_forbidden("You can only access forecasts for your assigned branch.")
    return statement.where(Forecast.branch_id.in_(branch_scope.branch_ids))


def query_forecasts(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: ForecastFilters,
) -> list[ForecastRead]:
    statement = (
        select(Forecast)
        .options(joinedload(Forecast.product), joinedload(Forecast.category), joinedload(Forecast.branch))
        .order_by(Forecast.created_at.desc(), Forecast.id.desc())
        .limit(max(1, min(filters.limit, 200)))
    )
    statement = apply_forecast_scope(statement, branch_scope, filters.branch_id)
    if filters.forecast_type is not None:
        statement = statement.where(Forecast.forecast_type == filters.forecast_type)
    if filters.category_id is not None:
        statement = statement.where(Forecast.category_id == filters.category_id)
    if filters.product_id is not None:
        statement = statement.where(Forecast.product_id == filters.product_id)

    return [forecast_read(row) for row in db.scalars(statement).unique().all()]


def query_product_forecasts(
    db: Session,
    *,
    product_id: int,
    branch_scope: BranchScope,
    branch_id: int | None = None,
    limit: int = 50,
) -> list[ForecastRead]:
    if db.get(Product, product_id) is None:
        raise_not_found("Product not found.")
    return query_forecasts(
        db,
        branch_scope=branch_scope,
        filters=ForecastFilters(
            product_id=product_id,
            branch_id=branch_id,
            limit=limit,
        ),
    )
