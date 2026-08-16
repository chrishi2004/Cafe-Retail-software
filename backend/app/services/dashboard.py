from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import BranchScope
from app.api.errors import raise_forbidden
from app.models import (
    Branch,
    Category,
    Inventory,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    Sale,
    SaleItem,
    Supplier,
)
from app.schemas.dashboard import (
    BranchPerformancePointRead,
    DashboardKpiRead,
    InventoryDashboardRead,
    InventoryHealthPointRead,
    InventoryKpiRead,
    LowStockRowRead,
    OverviewDashboardRead,
    PurchaseOrderBranchPointRead,
    PurchaseOrderKpiRead,
    PurchaseOrdersDashboardRead,
    PurchaseOrderStatusPointRead,
    PurchaseOrderSupplierPointRead,
    RecentPurchaseOrderRead,
    RevenueByCategoryPointRead,
    SalesDashboardRead,
    SalesKpiRead,
    SalesTrendPointRead,
    SlowMovingStockRowRead,
    StockValueByCategoryPointRead,
    TopProductPointRead,
)

MONEY = Decimal("0.01")
QUANTITY = Decimal("0.01")
PERCENT = Decimal("0.01")
OPEN_PURCHASE_ORDER_STATUSES = {
    PurchaseOrderStatus.DRAFT,
    PurchaseOrderStatus.PENDING_APPROVAL,
    PurchaseOrderStatus.APPROVED,
    PurchaseOrderStatus.ORDERED,
    PurchaseOrderStatus.PARTIALLY_RECEIVED,
}


@dataclass(frozen=True)
class DashboardFilters:
    branch_id: int | None = None
    category_id: int | None = None
    product_id: int | None = None
    supplier_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None


@dataclass(frozen=True)
class DashboardPeriod:
    start_date: date
    end_date: date
    previous_start_date: date
    previous_end_date: date


@dataclass(frozen=True)
class SalesAnalytics:
    period: DashboardPeriod
    summary: SalesKpiRead
    trend: list[SalesTrendPointRead]
    revenue_by_category: list[RevenueByCategoryPointRead]
    top_products: list[TopProductPointRead]
    branch_performance: list[BranchPerformancePointRead]


@dataclass(frozen=True)
class InventoryAnalytics:
    summary: InventoryKpiRead
    health: list[InventoryHealthPointRead]
    stock_value_by_category: list[StockValueByCategoryPointRead]
    low_stock_items: list[LowStockRowRead]
    slow_moving_stock: list[SlowMovingStockRowRead]


@dataclass(frozen=True)
class PurchaseOrderAnalytics:
    summary: PurchaseOrderKpiRead
    by_status: list[PurchaseOrderStatusPointRead]
    by_supplier: list[PurchaseOrderSupplierPointRead]
    branch_performance: list[PurchaseOrderBranchPointRead]
    recent_orders: list[RecentPurchaseOrderRead]


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def quantity(value: Decimal) -> Decimal:
    return value.quantize(QUANTITY, rounding=ROUND_HALF_UP)


def percent(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == 0:
        return None
    return (numerator / denominator * Decimal("100")).quantize(PERCENT, rounding=ROUND_HALF_UP)


def resolve_period(filters: DashboardFilters) -> DashboardPeriod:
    end_date = filters.end_date or datetime.now(UTC).date()
    start_date = filters.start_date or (end_date - timedelta(days=29))
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    day_count = (end_date - start_date).days + 1
    previous_end_date = start_date - timedelta(days=1)
    previous_start_date = previous_end_date - timedelta(days=day_count - 1)
    return DashboardPeriod(
        start_date=start_date,
        end_date=end_date,
        previous_start_date=previous_start_date,
        previous_end_date=previous_end_date,
    )


def date_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(start_date, time.min, tzinfo=UTC),
        datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC),
    )


def validate_branch_filter(branch_scope: BranchScope, branch_id: int | None) -> None:
    if branch_scope.all_branches or branch_id is None:
        return
    if branch_id not in branch_scope.branch_ids:
        raise_forbidden("You can only access dashboard data for your assigned branch.")


def apply_branch_scope(statement, branch_scope: BranchScope, branch_id: int | None, branch_column):
    validate_branch_filter(branch_scope, branch_id)
    if branch_scope.all_branches:
        if branch_id is not None:
            statement = statement.where(branch_column == branch_id)
    else:
        statement = statement.where(branch_column.in_(branch_scope.branch_ids))
    return statement


def load_sale_rows(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: DashboardFilters,
    start_date: date,
    end_date: date,
) -> list[tuple[SaleItem, Sale, Product, Category, Branch]]:
    start, end = date_bounds(start_date, end_date)
    statement = (
        select(SaleItem, Sale, Product, Category, Branch)
        .join(SaleItem.sale)
        .join(SaleItem.product)
        .join(Product.category)
        .join(Sale.branch)
        .where(Sale.sale_datetime >= start, Sale.sale_datetime < end)
    )
    statement = apply_branch_scope(statement, branch_scope, filters.branch_id, Sale.branch_id)
    if filters.product_id is not None:
        statement = statement.where(SaleItem.product_id == filters.product_id)
    if filters.category_id is not None:
        statement = statement.where(Product.category_id == filters.category_id)
    if filters.supplier_id is not None:
        statement = statement.where(Product.supplier_id == filters.supplier_id)

    return list(db.execute(statement).all())


def summarize_sales(
    rows: list[tuple[SaleItem, Sale, Product, Category, Branch]],
    *,
    previous_revenue: Decimal = Decimal("0.00"),
) -> SalesKpiRead:
    revenue = Decimal("0.00")
    gross_profit = Decimal("0.00")
    units_sold = Decimal("0.00")
    transaction_ids: set[int] = set()

    for item, sale, product, _category, _branch in rows:
        revenue += item.line_total
        gross_profit += (item.unit_price - product.unit_cost) * item.quantity - item.discount_amount
        units_sold += item.quantity
        transaction_ids.add(sale.id)

    transaction_count = len(transaction_ids)
    average_order_value = revenue / transaction_count if transaction_count else Decimal("0.00")
    return SalesKpiRead(
        revenue=money(revenue),
        gross_profit=money(gross_profit),
        gross_margin_percent=percent(gross_profit, revenue),
        units_sold=quantity(units_sold),
        transaction_count=transaction_count,
        average_order_value=money(average_order_value),
        sales_growth_percent=percent(revenue - previous_revenue, previous_revenue),
        previous_period_revenue=money(previous_revenue),
    )


def build_sales_trend(rows: list[tuple[SaleItem, Sale, Product, Category, Branch]]) -> list[SalesTrendPointRead]:
    grouped: dict[date, dict[str, Decimal | set[int]]] = defaultdict(
        lambda: {
            "revenue": Decimal("0.00"),
            "gross_profit": Decimal("0.00"),
            "units_sold": Decimal("0.00"),
            "transaction_ids": set(),
        }
    )
    for item, sale, product, _category, _branch in rows:
        sale_date = sale.sale_datetime.date()
        grouped[sale_date]["revenue"] += item.line_total
        grouped[sale_date]["gross_profit"] += (item.unit_price - product.unit_cost) * item.quantity - item.discount_amount
        grouped[sale_date]["units_sold"] += item.quantity
        transaction_ids = grouped[sale_date]["transaction_ids"]
        if isinstance(transaction_ids, set):
            transaction_ids.add(sale.id)

    points: list[SalesTrendPointRead] = []
    for sale_date in sorted(grouped):
        transaction_ids = grouped[sale_date]["transaction_ids"]
        points.append(
            SalesTrendPointRead(
                date=sale_date,
                revenue=money(grouped[sale_date]["revenue"]),
                gross_profit=money(grouped[sale_date]["gross_profit"]),
                units_sold=quantity(grouped[sale_date]["units_sold"]),
                transaction_count=len(transaction_ids) if isinstance(transaction_ids, set) else 0,
            )
        )
    return points


def build_revenue_by_category(
    rows: list[tuple[SaleItem, Sale, Product, Category, Branch]],
) -> list[RevenueByCategoryPointRead]:
    grouped: dict[int, dict[str, object]] = {}
    for item, _sale, product, category, _branch in rows:
        bucket = grouped.setdefault(
            category.id,
            {
                "category_name": category.name,
                "revenue": Decimal("0.00"),
                "gross_profit": Decimal("0.00"),
                "units_sold": Decimal("0.00"),
            },
        )
        bucket["revenue"] += item.line_total
        bucket["gross_profit"] += (item.unit_price - product.unit_cost) * item.quantity - item.discount_amount
        bucket["units_sold"] += item.quantity

    return [
        RevenueByCategoryPointRead(
            category_id=category_id,
            category_name=str(bucket["category_name"]),
            revenue=money(bucket["revenue"]),
            gross_profit=money(bucket["gross_profit"]),
            units_sold=quantity(bucket["units_sold"]),
        )
        for category_id, bucket in sorted(grouped.items(), key=lambda row: row[1]["revenue"], reverse=True)
    ]


def build_top_products(rows: list[tuple[SaleItem, Sale, Product, Category, Branch]], limit: int = 10) -> list[TopProductPointRead]:
    grouped: dict[int, dict[str, object]] = {}
    for item, _sale, product, category, _branch in rows:
        bucket = grouped.setdefault(
            product.id,
            {
                "product_sku": product.sku,
                "product_name": product.name,
                "category_name": category.name,
                "revenue": Decimal("0.00"),
                "gross_profit": Decimal("0.00"),
                "units_sold": Decimal("0.00"),
            },
        )
        bucket["revenue"] += item.line_total
        bucket["gross_profit"] += (item.unit_price - product.unit_cost) * item.quantity - item.discount_amount
        bucket["units_sold"] += item.quantity

    rows_sorted = sorted(
        grouped.items(),
        key=lambda row: (row[1]["units_sold"], row[1]["revenue"]),
        reverse=True,
    )[:limit]
    return [
        TopProductPointRead(
            product_id=product_id,
            product_sku=str(bucket["product_sku"]),
            product_name=str(bucket["product_name"]),
            category_name=str(bucket["category_name"]),
            units_sold=quantity(bucket["units_sold"]),
            revenue=money(bucket["revenue"]),
            gross_profit=money(bucket["gross_profit"]),
        )
        for product_id, bucket in rows_sorted
    ]


def build_branch_performance(
    rows: list[tuple[SaleItem, Sale, Product, Category, Branch]],
) -> list[BranchPerformancePointRead]:
    grouped: dict[int, dict[str, object]] = {}
    for item, sale, product, _category, branch in rows:
        bucket = grouped.setdefault(
            branch.id,
            {
                "branch_name": branch.name,
                "revenue": Decimal("0.00"),
                "gross_profit": Decimal("0.00"),
                "units_sold": Decimal("0.00"),
                "transaction_ids": set(),
            },
        )
        bucket["revenue"] += item.line_total
        bucket["gross_profit"] += (item.unit_price - product.unit_cost) * item.quantity - item.discount_amount
        bucket["units_sold"] += item.quantity
        transaction_ids = bucket["transaction_ids"]
        if isinstance(transaction_ids, set):
            transaction_ids.add(sale.id)

    return [
        BranchPerformancePointRead(
            branch_id=branch_id,
            branch_name=str(bucket["branch_name"]),
            revenue=money(bucket["revenue"]),
            gross_profit=money(bucket["gross_profit"]),
            units_sold=quantity(bucket["units_sold"]),
            transaction_count=len(bucket["transaction_ids"]) if isinstance(bucket["transaction_ids"], set) else 0,
        )
        for branch_id, bucket in sorted(grouped.items(), key=lambda row: row[1]["revenue"], reverse=True)
    ]


def get_sales_analytics(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: DashboardFilters,
) -> SalesAnalytics:
    period = resolve_period(filters)
    current_rows = load_sale_rows(
        db,
        branch_scope=branch_scope,
        filters=filters,
        start_date=period.start_date,
        end_date=period.end_date,
    )
    previous_rows = load_sale_rows(
        db,
        branch_scope=branch_scope,
        filters=filters,
        start_date=period.previous_start_date,
        end_date=period.previous_end_date,
    )
    previous_summary = summarize_sales(previous_rows)
    summary = summarize_sales(current_rows, previous_revenue=previous_summary.revenue)
    return SalesAnalytics(
        period=period,
        summary=summary,
        trend=build_sales_trend(current_rows),
        revenue_by_category=build_revenue_by_category(current_rows),
        top_products=build_top_products(current_rows),
        branch_performance=build_branch_performance(current_rows),
    )


def load_inventory_rows(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: DashboardFilters,
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
    if filters.product_id is not None:
        statement = statement.where(Inventory.product_id == filters.product_id)
    if filters.category_id is not None:
        statement = statement.where(Product.category_id == filters.category_id)
    if filters.supplier_id is not None:
        statement = statement.where(Product.supplier_id == filters.supplier_id)

    return list(db.execute(statement).all())


def load_last_sale_dates(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: DashboardFilters,
    end_date: date,
) -> dict[tuple[int, int], date]:
    _start, end = date_bounds(date(1970, 1, 1), end_date)
    statement = (
        select(SaleItem.product_id, Sale.branch_id, Sale.sale_datetime)
        .join(SaleItem.sale)
        .join(SaleItem.product)
        .where(Sale.sale_datetime < end)
    )
    statement = apply_branch_scope(statement, branch_scope, filters.branch_id, Sale.branch_id)
    if filters.product_id is not None:
        statement = statement.where(SaleItem.product_id == filters.product_id)
    if filters.category_id is not None:
        statement = statement.where(Product.category_id == filters.category_id)
    if filters.supplier_id is not None:
        statement = statement.where(Product.supplier_id == filters.supplier_id)

    last_seen: dict[tuple[int, int], date] = {}
    for product_id, branch_id, sale_datetime in db.execute(statement).all():
        key = (product_id, branch_id)
        sale_date = sale_datetime.date()
        if key not in last_seen or sale_date > last_seen[key]:
            last_seen[key] = sale_date
    return last_seen


def inventory_stock_value(inventory: Inventory, product: Product) -> Decimal:
    return money(inventory.quantity_on_hand * product.unit_cost)


def inventory_status(inventory: Inventory, product: Product) -> str:
    if inventory.quantity_on_hand <= 0:
        return "Out of stock"
    if inventory.quantity_on_hand <= product.reorder_threshold:
        return "Low stock"
    if product.target_stock_level > 0 and inventory.quantity_on_hand > product.target_stock_level * Decimal("1.25"):
        return "Overstocked"
    return "Healthy"


def low_stock_row(inventory: Inventory, product: Product, category: Category, supplier: Supplier, branch: Branch) -> LowStockRowRead:
    return LowStockRowRead(
        product_id=product.id,
        product_sku=product.sku,
        product_name=product.name,
        branch_id=branch.id,
        branch_name=branch.name,
        category_name=category.name,
        supplier_name=supplier.name,
        quantity_on_hand=quantity(inventory.quantity_on_hand),
        reorder_threshold=quantity(product.reorder_threshold),
        target_stock_level=quantity(product.target_stock_level),
        quantity_on_order=quantity(inventory.quantity_on_order),
        stock_value=inventory_stock_value(inventory, product),
    )


def get_inventory_analytics(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: DashboardFilters,
) -> InventoryAnalytics:
    period = resolve_period(filters)
    inventory_rows = load_inventory_rows(db, branch_scope=branch_scope, filters=filters)
    current_sale_rows = load_sale_rows(
        db,
        branch_scope=branch_scope,
        filters=filters,
        start_date=period.start_date,
        end_date=period.end_date,
    )
    sold_keys = {(item.product_id, sale.branch_id) for item, sale, _product, _category, _branch in current_sale_rows}
    last_sale_dates = load_last_sale_dates(db, branch_scope=branch_scope, filters=filters, end_date=period.end_date)

    stock_value = Decimal("0.00")
    total_quantity = Decimal("0.00")
    low_stock_items: list[LowStockRowRead] = []
    slow_moving: list[SlowMovingStockRowRead] = []
    health: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {
            "product_count": 0,
            "quantity_on_hand": Decimal("0.00"),
            "stock_value": Decimal("0.00"),
        }
    )
    by_category: dict[int, dict[str, Decimal | int | str]] = {}

    for inventory, product, category, supplier, branch in inventory_rows:
        row_stock_value = inventory_stock_value(inventory, product)
        stock_value += row_stock_value
        total_quantity += inventory.quantity_on_hand

        status = inventory_status(inventory, product)
        health[status]["product_count"] += 1
        health[status]["quantity_on_hand"] += inventory.quantity_on_hand
        health[status]["stock_value"] += row_stock_value

        category_bucket = by_category.setdefault(
            category.id,
            {
                "category_name": category.name,
                "quantity_on_hand": Decimal("0.00"),
                "stock_value": Decimal("0.00"),
                "low_stock_count": 0,
            },
        )
        category_bucket["quantity_on_hand"] += inventory.quantity_on_hand
        category_bucket["stock_value"] += row_stock_value
        if inventory.quantity_on_hand <= product.reorder_threshold:
            category_bucket["low_stock_count"] += 1
            low_stock_items.append(low_stock_row(inventory, product, category, supplier, branch))

        key = (product.id, branch.id)
        if inventory.quantity_on_hand > 0 and key not in sold_keys:
            slow_moving.append(
                SlowMovingStockRowRead(
                    product_id=product.id,
                    product_sku=product.sku,
                    product_name=product.name,
                    branch_id=branch.id,
                    branch_name=branch.name,
                    category_name=category.name,
                    supplier_name=supplier.name,
                    quantity_on_hand=quantity(inventory.quantity_on_hand),
                    stock_value=row_stock_value,
                    last_sale_date=last_sale_dates.get(key),
                )
            )

    health_rows = [
        InventoryHealthPointRead(
            status=status,
            product_count=int(bucket["product_count"]),
            quantity_on_hand=quantity(bucket["quantity_on_hand"]),
            stock_value=money(bucket["stock_value"]),
        )
        for status, bucket in sorted(health.items())
    ]
    category_rows = [
        StockValueByCategoryPointRead(
            category_id=category_id,
            category_name=str(bucket["category_name"]),
            quantity_on_hand=quantity(bucket["quantity_on_hand"]),
            stock_value=money(bucket["stock_value"]),
            low_stock_count=int(bucket["low_stock_count"]),
        )
        for category_id, bucket in sorted(by_category.items(), key=lambda row: row[1]["stock_value"], reverse=True)
    ]
    low_stock_items.sort(key=lambda item: (item.quantity_on_hand, item.product_name, item.branch_name))
    slow_moving.sort(key=lambda item: item.stock_value, reverse=True)

    summary = InventoryKpiRead(
        current_stock_value=money(stock_value),
        total_quantity_on_hand=quantity(total_quantity),
        low_stock_product_count=len(low_stock_items),
        slow_moving_stock_count=len(slow_moving),
    )
    return InventoryAnalytics(
        summary=summary,
        health=health_rows,
        stock_value_by_category=category_rows,
        low_stock_items=low_stock_items[:20],
        slow_moving_stock=slow_moving[:20],
    )


def load_purchase_orders(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: DashboardFilters,
) -> list[tuple[PurchaseOrder, Supplier, Branch]]:
    period = resolve_period(filters)
    statement = (
        select(PurchaseOrder, Supplier, Branch)
        .join(PurchaseOrder.supplier)
        .join(PurchaseOrder.branch)
        .where(PurchaseOrder.order_date >= period.start_date, PurchaseOrder.order_date <= period.end_date)
    )
    statement = apply_branch_scope(statement, branch_scope, filters.branch_id, PurchaseOrder.branch_id)
    if filters.product_id is not None:
        statement = statement.where(PurchaseOrder.items.any(PurchaseOrderItem.product_id == filters.product_id))
    if filters.category_id is not None:
        statement = statement.where(
            PurchaseOrder.items.any(PurchaseOrderItem.product.has(Product.category_id == filters.category_id))
        )
    if filters.supplier_id is not None:
        statement = statement.where(PurchaseOrder.supplier_id == filters.supplier_id)
    return list(db.execute(statement).all())


def get_purchase_order_analytics(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: DashboardFilters,
) -> PurchaseOrderAnalytics:
    rows = load_purchase_orders(db, branch_scope=branch_scope, filters=filters)
    today = datetime.now(UTC).date()
    status_rows: dict[str, dict[str, Decimal | int]] = defaultdict(lambda: {"count": 0, "total_amount": Decimal("0.00")})
    supplier_rows: dict[int, dict[str, Decimal | int | str]] = {}
    branch_rows: dict[int, dict[str, Decimal | int | str]] = {}
    pending_purchase_orders = 0
    pending_approval_count = 0
    approved_count = 0
    ordered_count = 0
    overdue_count = 0
    total_open_order_value = Decimal("0.00")

    sorted_rows = sorted(rows, key=lambda row: (row[0].order_date, row[0].id), reverse=True)
    for purchase_order, supplier, branch in sorted_rows:
        status_value = purchase_order.status.value
        status_rows[status_value]["count"] += 1
        status_rows[status_value]["total_amount"] += purchase_order.total_amount

        supplier_bucket = supplier_rows.setdefault(
            supplier.id,
            {"supplier_name": supplier.name, "count": 0, "total_amount": Decimal("0.00")},
        )
        supplier_bucket["count"] += 1
        supplier_bucket["total_amount"] += purchase_order.total_amount

        branch_bucket = branch_rows.setdefault(
            branch.id,
            {"branch_name": branch.name, "count": 0, "total_amount": Decimal("0.00")},
        )
        branch_bucket["count"] += 1
        branch_bucket["total_amount"] += purchase_order.total_amount

        if purchase_order.status in OPEN_PURCHASE_ORDER_STATUSES:
            pending_purchase_orders += 1
            total_open_order_value += purchase_order.total_amount
        if purchase_order.status == PurchaseOrderStatus.PENDING_APPROVAL:
            pending_approval_count += 1
        if purchase_order.status == PurchaseOrderStatus.APPROVED:
            approved_count += 1
        if purchase_order.status in {PurchaseOrderStatus.ORDERED, PurchaseOrderStatus.PARTIALLY_RECEIVED}:
            ordered_count += 1
        if (
            purchase_order.status in {PurchaseOrderStatus.APPROVED, PurchaseOrderStatus.ORDERED, PurchaseOrderStatus.PARTIALLY_RECEIVED}
            and purchase_order.expected_delivery_date is not None
            and purchase_order.expected_delivery_date < today
        ):
            overdue_count += 1

    return PurchaseOrderAnalytics(
        summary=PurchaseOrderKpiRead(
            pending_purchase_orders=pending_purchase_orders,
            pending_approval_count=pending_approval_count,
            approved_count=approved_count,
            ordered_count=ordered_count,
            overdue_count=overdue_count,
            total_open_order_value=money(total_open_order_value),
        ),
        by_status=[
            PurchaseOrderStatusPointRead(
                status=status,
                count=int(bucket["count"]),
                total_amount=money(bucket["total_amount"]),
            )
            for status, bucket in sorted(status_rows.items())
        ],
        by_supplier=[
            PurchaseOrderSupplierPointRead(
                supplier_id=supplier_id,
                supplier_name=str(bucket["supplier_name"]),
                count=int(bucket["count"]),
                total_amount=money(bucket["total_amount"]),
            )
            for supplier_id, bucket in sorted(supplier_rows.items(), key=lambda row: row[1]["total_amount"], reverse=True)
        ],
        branch_performance=[
            PurchaseOrderBranchPointRead(
                branch_id=branch_id,
                branch_name=str(bucket["branch_name"]),
                count=int(bucket["count"]),
                total_amount=money(bucket["total_amount"]),
            )
            for branch_id, bucket in sorted(branch_rows.items(), key=lambda row: row[1]["total_amount"], reverse=True)
        ],
        recent_orders=[
            RecentPurchaseOrderRead(
                id=purchase_order.id,
                po_number=purchase_order.po_number,
                supplier_name=supplier.name,
                branch_name=branch.name,
                status=purchase_order.status.value,
                order_date=purchase_order.order_date,
                expected_delivery_date=purchase_order.expected_delivery_date,
                total_amount=money(purchase_order.total_amount),
            )
            for purchase_order, supplier, branch in sorted_rows[:10]
        ],
    )


def get_overview_dashboard(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: DashboardFilters,
) -> OverviewDashboardRead:
    sales = get_sales_analytics(db, branch_scope=branch_scope, filters=filters)
    inventory = get_inventory_analytics(db, branch_scope=branch_scope, filters=filters)
    purchase_orders = get_purchase_order_analytics(db, branch_scope=branch_scope, filters=filters)
    return OverviewDashboardRead(
        period_start=sales.period.start_date,
        period_end=sales.period.end_date,
        previous_period_start=sales.period.previous_start_date,
        previous_period_end=sales.period.previous_end_date,
        kpis=DashboardKpiRead(
            sales=sales.summary,
            inventory=inventory.summary,
            purchase_orders=purchase_orders.summary,
            top_selling_product=sales.top_products[0] if sales.top_products else None,
        ),
        sales_trend=sales.trend,
        revenue_by_category=sales.revenue_by_category,
        top_products=sales.top_products,
        branch_performance=sales.branch_performance,
        inventory_health=inventory.health,
        low_stock_items=inventory.low_stock_items,
    )


def get_sales_dashboard(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: DashboardFilters,
) -> SalesDashboardRead:
    sales = get_sales_analytics(db, branch_scope=branch_scope, filters=filters)
    return SalesDashboardRead(
        period_start=sales.period.start_date,
        period_end=sales.period.end_date,
        previous_period_start=sales.period.previous_start_date,
        previous_period_end=sales.period.previous_end_date,
        summary=sales.summary,
        sales_trend=sales.trend,
        revenue_by_category=sales.revenue_by_category,
        top_products=sales.top_products,
        branch_performance=sales.branch_performance,
    )


def get_inventory_dashboard(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: DashboardFilters,
) -> InventoryDashboardRead:
    period = resolve_period(filters)
    inventory = get_inventory_analytics(db, branch_scope=branch_scope, filters=filters)
    return InventoryDashboardRead(
        period_start=period.start_date,
        period_end=period.end_date,
        summary=inventory.summary,
        inventory_health=inventory.health,
        stock_value_by_category=inventory.stock_value_by_category,
        low_stock_items=inventory.low_stock_items,
        slow_moving_stock=inventory.slow_moving_stock,
    )


def get_purchase_orders_dashboard(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: DashboardFilters,
) -> PurchaseOrdersDashboardRead:
    period = resolve_period(filters)
    purchase_orders = get_purchase_order_analytics(db, branch_scope=branch_scope, filters=filters)
    return PurchaseOrdersDashboardRead(
        period_start=period.start_date,
        period_end=period.end_date,
        summary=purchase_orders.summary,
        by_status=purchase_orders.by_status,
        by_supplier=purchase_orders.by_supplier,
        branch_performance=purchase_orders.branch_performance,
        recent_orders=purchase_orders.recent_orders,
    )
