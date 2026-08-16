from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models import StockMovementType
from app.schemas.master_data import normalize_blank


class InventoryRead(BaseModel):
    id: int
    product_id: int
    product_sku: str
    product_name: str
    category_id: int
    category_name: str
    supplier_id: int
    supplier_name: str
    branch_id: int
    branch_name: str
    quantity_on_hand: Decimal
    quantity_reserved: Decimal
    quantity_on_order: Decimal
    reorder_threshold: Decimal
    target_stock_level: Decimal
    unit_cost: Decimal
    stock_value: Decimal
    is_low_stock: bool
    last_updated_at: datetime


class ProductInventoryDetail(BaseModel):
    product_id: int
    product_sku: str
    product_name: str
    category_name: str
    supplier_name: str
    total_quantity_on_hand: Decimal
    total_stock_value: Decimal
    is_low_stock_any_branch: bool
    inventory: list[InventoryRead]


class StockAdjustmentCreate(BaseModel):
    product_id: int
    branch_id: int
    quantity_change: Decimal = Field(max_digits=12, decimal_places=2)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        reason = normalize_blank(value)
        if reason is None:
            raise ValueError("Adjustment reason is required.")
        return reason


class StockMovementRead(BaseModel):
    id: int
    product_id: int
    product_sku: str
    product_name: str
    branch_id: int
    branch_name: str
    movement_type: StockMovementType
    quantity_change: Decimal
    reason: str | None
    reference_type: str | None
    reference_id: int | None
    created_by: int | None
    created_by_name: str | None
    created_at: datetime


class StockAdjustmentResponse(BaseModel):
    inventory: InventoryRead
    movement: StockMovementRead
