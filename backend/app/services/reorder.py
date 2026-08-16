from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import BranchScope
from app.api.errors import raise_forbidden
from app.models import Branch, Category, Inventory, Product, Sale, SaleItem, Supplier
from app.schemas.reorder import ReorderPriority, ReorderRecommendationRead

MONEY = Decimal("0.01")
QUANTITY = Decimal("0.01")
PRIORITY_ORDER = {
    ReorderPriority.CRITICAL: 0,
    ReorderPriority.HIGH: 1,
    ReorderPriority.MEDIUM: 2,
    ReorderPriority.LOW: 3,
}


@dataclass(frozen=True)
class ReorderFilters:
    branch_id: int | None = None
    category_id: int | None = None
    supplier_id: int | None = None
    priority: ReorderPriority | None = None
    lookback_days: int = 30
    as_of_date: date | None = None


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def quantity(value: Decimal) -> Decimal:
    return value.quantize(QUANTITY, rounding=ROUND_HALF_UP)


def validate_branch_filter(branch_scope: BranchScope, branch_id: int | None) -> None:
    if branch_scope.all_branches or branch_id is None:
        return
    if branch_id not in branch_scope.branch_ids:
        raise_forbidden("You can only access reorder recommendations for your assigned branch.")


def apply_branch_scope(statement, branch_scope: BranchScope, branch_id: int | None, branch_column):
    validate_branch_filter(branch_scope, branch_id)
    if branch_scope.all_branches:
        if branch_id is not None:
            statement = statement.where(branch_column == branch_id)
    else:
        statement = statement.where(branch_column.in_(branch_scope.branch_ids))
    return statement


def date_bounds(as_of_date: date, lookback_days: int) -> tuple[datetime, datetime]:
    start_date = as_of_date - timedelta(days=max(lookback_days, 1) - 1)
    return (
        datetime.combine(start_date, time.min, tzinfo=UTC),
        datetime.combine(as_of_date + timedelta(days=1), time.min, tzinfo=UTC),
    )


def load_inventory_rows(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: ReorderFilters,
) -> list[tuple[Inventory, Product, Category, Supplier, Branch]]:
    statement = (
        select(Inventory, Product, Category, Supplier, Branch)
        .join(Inventory.product)
        .join(Product.category)
        .join(Product.supplier)
        .join(Inventory.branch)
        .where(Product.is_active.is_(True))
    )
    statement = apply_branch_scope(statement, branch_scope, filters.branch_id, Inventory.branch_id)
    if filters.category_id is not None:
        statement = statement.where(Product.category_id == filters.category_id)
    if filters.supplier_id is not None:
        statement = statement.where(Product.supplier_id == filters.supplier_id)

    return list(db.execute(statement).all())


def load_sales_velocity(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: ReorderFilters,
    as_of_date: date,
    lookback_days: int,
) -> dict[tuple[int, int], Decimal]:
    start, end = date_bounds(as_of_date, lookback_days)
    statement = (
        select(SaleItem.product_id, Sale.branch_id, SaleItem.quantity)
        .join(SaleItem.sale)
        .join(SaleItem.product)
        .where(Sale.sale_datetime >= start, Sale.sale_datetime < end)
    )
    statement = apply_branch_scope(statement, branch_scope, filters.branch_id, Sale.branch_id)
    if filters.category_id is not None:
        statement = statement.where(Product.category_id == filters.category_id)
    if filters.supplier_id is not None:
        statement = statement.where(Product.supplier_id == filters.supplier_id)

    totals: dict[tuple[int, int], Decimal] = {}
    for product_id, branch_id, sold_quantity in db.execute(statement).all():
        key = (product_id, branch_id)
        totals[key] = totals.get(key, Decimal("0.00")) + sold_quantity

    divisor = Decimal(max(lookback_days, 1))
    return {key: quantity(total / divisor) for key, total in totals.items()}


def calculate_days_until_stockout(current_stock: Decimal, average_daily_sales: Decimal) -> Decimal | None:
    if current_stock <= 0:
        return Decimal("0.00")
    if average_daily_sales <= 0:
        return None
    return quantity(current_stock / average_daily_sales)


def assign_priority(
    *,
    current_stock: Decimal,
    reorder_threshold: Decimal,
    supplier_lead_time_days: int,
    days_until_stockout: Decimal | None,
) -> ReorderPriority:
    if current_stock <= 0:
        return ReorderPriority.CRITICAL
    if days_until_stockout is not None and days_until_stockout <= Decimal(supplier_lead_time_days):
        return ReorderPriority.CRITICAL
    if current_stock <= reorder_threshold:
        return ReorderPriority.HIGH
    near_threshold = reorder_threshold * Decimal("1.25")
    if reorder_threshold > 0 and current_stock <= near_threshold:
        return ReorderPriority.MEDIUM
    return ReorderPriority.LOW


def recommendation_from_row(
    *,
    inventory: Inventory,
    product: Product,
    category: Category,
    supplier: Supplier,
    branch: Branch,
    average_daily_sales: Decimal,
) -> ReorderRecommendationRead:
    expected_demand = quantity(average_daily_sales * Decimal(supplier.lead_time_days))
    gross_suggested_quantity = product.target_stock_level - inventory.quantity_on_hand + expected_demand
    suggested_quantity = quantity(max(gross_suggested_quantity, Decimal("0.00")))
    days_until_stockout = calculate_days_until_stockout(inventory.quantity_on_hand, average_daily_sales)
    priority = assign_priority(
        current_stock=inventory.quantity_on_hand,
        reorder_threshold=product.reorder_threshold,
        supplier_lead_time_days=supplier.lead_time_days,
        days_until_stockout=days_until_stockout,
    )
    return ReorderRecommendationRead(
        product_id=product.id,
        product_sku=product.sku,
        product_name=product.name,
        category_id=category.id,
        category_name=category.name,
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        branch_id=branch.id,
        branch_name=branch.name,
        current_stock=quantity(inventory.quantity_on_hand),
        quantity_on_order=quantity(inventory.quantity_on_order),
        reorder_threshold=quantity(product.reorder_threshold),
        target_stock_level=quantity(product.target_stock_level),
        average_daily_sales=average_daily_sales,
        supplier_lead_time_days=supplier.lead_time_days,
        expected_demand_during_lead_time=expected_demand,
        days_until_stockout=days_until_stockout,
        suggested_reorder_quantity=suggested_quantity,
        priority=priority,
        unit_cost=money(product.unit_cost),
        estimated_cost=money(suggested_quantity * product.unit_cost),
    )


def query_reorder_recommendations(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: ReorderFilters,
) -> list[ReorderRecommendationRead]:
    lookback_days = max(1, min(filters.lookback_days, 365))
    as_of_date = filters.as_of_date or datetime.now(UTC).date()
    inventory_rows = load_inventory_rows(db, branch_scope=branch_scope, filters=filters)
    average_daily_sales_by_key = load_sales_velocity(
        db,
        branch_scope=branch_scope,
        filters=filters,
        as_of_date=as_of_date,
        lookback_days=lookback_days,
    )

    recommendations: list[ReorderRecommendationRead] = []
    for inventory, product, category, supplier, branch in inventory_rows:
        recommendation = recommendation_from_row(
            inventory=inventory,
            product=product,
            category=category,
            supplier=supplier,
            branch=branch,
            average_daily_sales=average_daily_sales_by_key.get((product.id, branch.id), Decimal("0.00")),
        )
        if filters.priority is None or recommendation.priority == filters.priority:
            recommendations.append(recommendation)

    return sorted(
        recommendations,
        key=lambda recommendation: (
            PRIORITY_ORDER[recommendation.priority],
            -recommendation.suggested_reorder_quantity,
            recommendation.product_name,
            recommendation.branch_name,
        ),
    )
