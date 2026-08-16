from __future__ import annotations

import csv
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from io import StringIO
from typing import Any

from fastapi import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.api.deps import BranchScope
from app.api.errors import raise_forbidden
from app.models import (
    Branch,
    Category,
    Forecast,
    ForecastType,
    Inventory,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    Sale,
    SaleItem,
    Supplier,
    User,
)


def _apply_branch_scope(statement, branch_scope: BranchScope, branch_id: int | None, branch_column):
    if branch_scope.all_branches:
        if branch_id is not None:
            return statement.where(branch_column == branch_id)
        return statement

    if branch_id is not None and branch_id not in branch_scope.branch_ids:
        raise_forbidden("You can only export data for your assigned branch.")
    return statement.where(branch_column.in_(branch_scope.branch_ids))


def _datetime_bounds(start_date: date | None, end_date: date | None) -> tuple[datetime | None, datetime | None]:
    start = datetime.combine(start_date, time.min, tzinfo=UTC) if start_date else None
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC) if end_date else None
    return start, end


def _format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _csv_response(*, filename: str, fieldnames: list[str], rows: list[dict[str, Any]]) -> Response:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _format_cell(row.get(field)) for field in fieldnames})

    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def export_sales_csv(
    db: Session,
    *,
    branch_scope: BranchScope,
    branch_id: int | None = None,
    category_id: int | None = None,
    product_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Response:
    start, end = _datetime_bounds(start_date, end_date)
    statement = (
        select(SaleItem, Sale, Product, Category, Branch, User)
        .join(SaleItem.sale)
        .join(SaleItem.product)
        .join(Product.category)
        .join(Sale.branch)
        .join(User, Sale.created_by == User.id)
        .order_by(Sale.sale_datetime.desc(), Sale.id.desc(), SaleItem.id)
    )
    statement = _apply_branch_scope(statement, branch_scope, branch_id, Sale.branch_id)
    if start is not None:
        statement = statement.where(Sale.sale_datetime >= start)
    if end is not None:
        statement = statement.where(Sale.sale_datetime < end)
    if category_id is not None:
        statement = statement.where(Product.category_id == category_id)
    if product_id is not None:
        statement = statement.where(SaleItem.product_id == product_id)

    rows: list[dict[str, Any]] = []
    for item, sale, product, category, branch, creator in db.execute(statement).all():
        gross_profit = (item.unit_price - product.unit_cost) * item.quantity - item.discount_amount
        rows.append(
            {
                "sale_number": sale.sale_number,
                "sale_datetime": sale.sale_datetime,
                "branch_name": branch.name,
                "product_sku": product.sku,
                "product_name": product.name,
                "category_name": category.name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "discount_amount": item.discount_amount,
                "line_total": item.line_total,
                "gross_profit": gross_profit,
                "created_by_name": creator.name,
            }
        )

    return _csv_response(
        filename="sales_export.csv",
        fieldnames=[
            "sale_number",
            "sale_datetime",
            "branch_name",
            "product_sku",
            "product_name",
            "category_name",
            "quantity",
            "unit_price",
            "discount_amount",
            "line_total",
            "gross_profit",
            "created_by_name",
        ],
        rows=rows,
    )


def export_inventory_csv(
    db: Session,
    *,
    branch_scope: BranchScope,
    branch_id: int | None = None,
    category_id: int | None = None,
    supplier_id: int | None = None,
    low_stock: bool | None = None,
) -> Response:
    statement = (
        select(Inventory, Product, Category, Supplier, Branch)
        .join(Inventory.product)
        .join(Product.category)
        .join(Product.supplier)
        .join(Inventory.branch)
        .order_by(Branch.name, Category.name, Product.name)
    )
    statement = _apply_branch_scope(statement, branch_scope, branch_id, Inventory.branch_id)
    if category_id is not None:
        statement = statement.where(Product.category_id == category_id)
    if supplier_id is not None:
        statement = statement.where(Product.supplier_id == supplier_id)
    if low_stock is True:
        statement = statement.where(Inventory.quantity_on_hand <= Product.reorder_threshold)

    rows: list[dict[str, Any]] = []
    for inventory, product, category, supplier, branch in db.execute(statement).all():
        rows.append(
            {
                "branch_name": branch.name,
                "product_sku": product.sku,
                "product_name": product.name,
                "category_name": category.name,
                "supplier_name": supplier.name,
                "quantity_on_hand": inventory.quantity_on_hand,
                "quantity_reserved": inventory.quantity_reserved,
                "quantity_on_order": inventory.quantity_on_order,
                "reorder_threshold": product.reorder_threshold,
                "target_stock_level": product.target_stock_level,
                "unit_cost": product.unit_cost,
                "stock_value": inventory.quantity_on_hand * product.unit_cost,
                "is_low_stock": inventory.quantity_on_hand <= product.reorder_threshold,
                "product_active": product.is_active,
                "last_updated_at": inventory.last_updated_at,
            }
        )

    return _csv_response(
        filename="inventory_export.csv",
        fieldnames=[
            "branch_name",
            "product_sku",
            "product_name",
            "category_name",
            "supplier_name",
            "quantity_on_hand",
            "quantity_reserved",
            "quantity_on_order",
            "reorder_threshold",
            "target_stock_level",
            "unit_cost",
            "stock_value",
            "is_low_stock",
            "product_active",
            "last_updated_at",
        ],
        rows=rows,
    )


def export_purchase_orders_csv(
    db: Session,
    *,
    branch_scope: BranchScope,
    branch_id: int | None = None,
    supplier_id: int | None = None,
    status: PurchaseOrderStatus | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Response:
    creator = aliased(User)
    approver = aliased(User)
    statement = (
        select(PurchaseOrder, PurchaseOrderItem, Product, Supplier, Branch, creator, approver)
        .join(PurchaseOrder.items)
        .join(PurchaseOrderItem.product)
        .join(PurchaseOrder.supplier)
        .join(PurchaseOrder.branch)
        .join(creator, PurchaseOrder.created_by == creator.id)
        .outerjoin(approver, PurchaseOrder.approved_by == approver.id)
        .order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc(), PurchaseOrderItem.id)
    )
    statement = _apply_branch_scope(statement, branch_scope, branch_id, PurchaseOrder.branch_id)
    if supplier_id is not None:
        statement = statement.where(PurchaseOrder.supplier_id == supplier_id)
    if status is not None:
        statement = statement.where(PurchaseOrder.status == status)
    if start_date is not None:
        statement = statement.where(PurchaseOrder.order_date >= start_date)
    if end_date is not None:
        statement = statement.where(PurchaseOrder.order_date <= end_date)

    rows: list[dict[str, Any]] = []
    for purchase_order, item, product, supplier, branch, created_by, approved_by in db.execute(statement).all():
        rows.append(
            {
                "po_number": purchase_order.po_number,
                "status": purchase_order.status,
                "order_date": purchase_order.order_date,
                "expected_delivery_date": purchase_order.expected_delivery_date,
                "branch_name": branch.name,
                "supplier_name": supplier.name,
                "product_sku": product.sku,
                "product_name": product.name,
                "quantity_ordered": item.quantity_ordered,
                "quantity_received": item.quantity_received,
                "remaining_quantity": item.quantity_ordered - item.quantity_received,
                "unit_cost": item.unit_cost,
                "line_total": item.line_total,
                "total_amount": purchase_order.total_amount,
                "created_by_name": created_by.name,
                "approved_by_name": approved_by.name if approved_by else None,
                "approved_at": purchase_order.approved_at,
            }
        )

    return _csv_response(
        filename="purchase_orders_export.csv",
        fieldnames=[
            "po_number",
            "status",
            "order_date",
            "expected_delivery_date",
            "branch_name",
            "supplier_name",
            "product_sku",
            "product_name",
            "quantity_ordered",
            "quantity_received",
            "remaining_quantity",
            "unit_cost",
            "line_total",
            "total_amount",
            "created_by_name",
            "approved_by_name",
            "approved_at",
        ],
        rows=rows,
    )


def export_forecasts_csv(
    db: Session,
    *,
    branch_scope: BranchScope,
    forecast_type: ForecastType | None = None,
    branch_id: int | None = None,
    category_id: int | None = None,
    product_id: int | None = None,
    limit: int = 200,
) -> Response:
    statement = (
        select(Forecast, Product, Category, Branch)
        .outerjoin(Forecast.product)
        .outerjoin(Forecast.category)
        .outerjoin(Forecast.branch)
        .order_by(Forecast.created_at.desc(), Forecast.id.desc())
        .limit(max(1, min(limit, 1000)))
    )
    statement = _apply_branch_scope(statement, branch_scope, branch_id, Forecast.branch_id)
    if forecast_type is not None:
        statement = statement.where(Forecast.forecast_type == forecast_type)
    if category_id is not None:
        statement = statement.where(Forecast.category_id == category_id)
    if product_id is not None:
        statement = statement.where(Forecast.product_id == product_id)

    rows: list[dict[str, Any]] = []
    for forecast, product, category, branch in db.execute(statement).all():
        if product is not None:
            scope_type = "product"
            scope_name = product.name
        elif category is not None:
            scope_type = "category"
            scope_name = category.name
        elif branch is not None:
            scope_type = "branch"
            scope_name = branch.name
        else:
            scope_type = "overall"
            scope_name = "All accessible business"

        rows.append(
            {
                "created_at": forecast.created_at,
                "forecast_type": forecast.forecast_type,
                "scope_type": scope_type,
                "scope_name": scope_name,
                "branch_name": branch.name if branch else None,
                "category_name": category.name if category else None,
                "product_name": product.name if product else None,
                "forecast_start_date": forecast.forecast_start_date,
                "forecast_end_date": forecast.forecast_end_date,
                "forecast_value": forecast.forecast_value,
                "confidence_low": forecast.confidence_low,
                "confidence_high": forecast.confidence_high,
                "model_name": forecast.model_name,
            }
        )

    return _csv_response(
        filename="forecasts_export.csv",
        fieldnames=[
            "created_at",
            "forecast_type",
            "scope_type",
            "scope_name",
            "branch_name",
            "category_name",
            "product_name",
            "forecast_start_date",
            "forecast_end_date",
            "forecast_value",
            "confidence_low",
            "confidence_high",
            "model_name",
        ],
        rows=rows,
    )
