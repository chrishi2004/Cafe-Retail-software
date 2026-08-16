from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class SalesKpiRead(BaseModel):
    revenue: Decimal
    gross_profit: Decimal
    gross_margin_percent: Decimal | None
    units_sold: Decimal
    transaction_count: int
    average_order_value: Decimal
    sales_growth_percent: Decimal | None
    previous_period_revenue: Decimal


class InventoryKpiRead(BaseModel):
    current_stock_value: Decimal
    total_quantity_on_hand: Decimal
    low_stock_product_count: int
    slow_moving_stock_count: int


class PurchaseOrderKpiRead(BaseModel):
    pending_purchase_orders: int
    pending_approval_count: int
    approved_count: int
    ordered_count: int
    overdue_count: int
    total_open_order_value: Decimal


class SalesTrendPointRead(BaseModel):
    date: date
    revenue: Decimal
    gross_profit: Decimal
    units_sold: Decimal
    transaction_count: int


class RevenueByCategoryPointRead(BaseModel):
    category_id: int
    category_name: str
    revenue: Decimal
    gross_profit: Decimal
    units_sold: Decimal


class TopProductPointRead(BaseModel):
    product_id: int
    product_sku: str
    product_name: str
    category_name: str
    units_sold: Decimal
    revenue: Decimal
    gross_profit: Decimal


class DashboardKpiRead(BaseModel):
    sales: SalesKpiRead
    inventory: InventoryKpiRead
    purchase_orders: PurchaseOrderKpiRead
    top_selling_product: TopProductPointRead | None


class BranchPerformancePointRead(BaseModel):
    branch_id: int
    branch_name: str
    revenue: Decimal
    gross_profit: Decimal
    units_sold: Decimal
    transaction_count: int


class InventoryHealthPointRead(BaseModel):
    status: str
    product_count: int
    quantity_on_hand: Decimal
    stock_value: Decimal


class StockValueByCategoryPointRead(BaseModel):
    category_id: int
    category_name: str
    quantity_on_hand: Decimal
    stock_value: Decimal
    low_stock_count: int


class LowStockRowRead(BaseModel):
    product_id: int
    product_sku: str
    product_name: str
    branch_id: int
    branch_name: str
    category_name: str
    supplier_name: str
    quantity_on_hand: Decimal
    reorder_threshold: Decimal
    target_stock_level: Decimal
    quantity_on_order: Decimal
    stock_value: Decimal


class SlowMovingStockRowRead(BaseModel):
    product_id: int
    product_sku: str
    product_name: str
    branch_id: int
    branch_name: str
    category_name: str
    supplier_name: str
    quantity_on_hand: Decimal
    stock_value: Decimal
    last_sale_date: date | None


class OverviewDashboardRead(BaseModel):
    period_start: date
    period_end: date
    previous_period_start: date
    previous_period_end: date
    kpis: DashboardKpiRead
    sales_trend: list[SalesTrendPointRead]
    revenue_by_category: list[RevenueByCategoryPointRead]
    top_products: list[TopProductPointRead]
    branch_performance: list[BranchPerformancePointRead]
    inventory_health: list[InventoryHealthPointRead]
    low_stock_items: list[LowStockRowRead]


class SalesDashboardRead(BaseModel):
    period_start: date
    period_end: date
    previous_period_start: date
    previous_period_end: date
    summary: SalesKpiRead
    sales_trend: list[SalesTrendPointRead]
    revenue_by_category: list[RevenueByCategoryPointRead]
    top_products: list[TopProductPointRead]
    branch_performance: list[BranchPerformancePointRead]


class InventoryDashboardRead(BaseModel):
    period_start: date
    period_end: date
    summary: InventoryKpiRead
    inventory_health: list[InventoryHealthPointRead]
    stock_value_by_category: list[StockValueByCategoryPointRead]
    low_stock_items: list[LowStockRowRead]
    slow_moving_stock: list[SlowMovingStockRowRead]


class PurchaseOrderStatusPointRead(BaseModel):
    status: str
    count: int
    total_amount: Decimal


class PurchaseOrderSupplierPointRead(BaseModel):
    supplier_id: int
    supplier_name: str
    count: int
    total_amount: Decimal


class PurchaseOrderBranchPointRead(BaseModel):
    branch_id: int
    branch_name: str
    count: int
    total_amount: Decimal


class RecentPurchaseOrderRead(BaseModel):
    id: int
    po_number: str
    supplier_name: str
    branch_name: str
    status: str
    order_date: date
    expected_delivery_date: date | None
    total_amount: Decimal


class PurchaseOrdersDashboardRead(BaseModel):
    period_start: date
    period_end: date
    summary: PurchaseOrderKpiRead
    by_status: list[PurchaseOrderStatusPointRead]
    by_supplier: list[PurchaseOrderSupplierPointRead]
    branch_performance: list[PurchaseOrderBranchPointRead]
    recent_orders: list[RecentPurchaseOrderRead]
