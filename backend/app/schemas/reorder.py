from __future__ import annotations

import enum
from decimal import Decimal

from pydantic import BaseModel


class ReorderPriority(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReorderRecommendationRead(BaseModel):
    product_id: int
    product_sku: str
    product_name: str
    category_id: int
    category_name: str
    supplier_id: int
    supplier_name: str
    branch_id: int
    branch_name: str
    current_stock: Decimal
    quantity_on_order: Decimal
    reorder_threshold: Decimal
    target_stock_level: Decimal
    average_daily_sales: Decimal
    supplier_lead_time_days: int
    expected_demand_during_lead_time: Decimal
    days_until_stockout: Decimal | None
    suggested_reorder_quantity: Decimal
    priority: ReorderPriority
    unit_cost: Decimal
    estimated_cost: Decimal
