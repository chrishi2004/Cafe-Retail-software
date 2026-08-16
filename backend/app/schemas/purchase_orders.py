from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models import PurchaseOrderStatus


class PurchaseOrderItemCreate(BaseModel):
    product_id: int
    quantity_ordered: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    branch_id: int
    order_date: date | None = None
    expected_delivery_date: date | None = None
    items: list[PurchaseOrderItemCreate] = Field(min_length=1)

    @field_validator("items")
    @classmethod
    def validate_unique_products(
        cls,
        value: list[PurchaseOrderItemCreate],
    ) -> list[PurchaseOrderItemCreate]:
        seen: set[int] = set()
        for item in value:
            if item.product_id in seen:
                raise ValueError("Each product can only appear once per purchase order.")
            seen.add(item.product_id)
        return value


class PurchaseOrderUpdate(PurchaseOrderCreate):
    pass


class PurchaseOrderDraftItemCreate(BaseModel):
    product_id: int
    branch_id: int
    quantity_ordered: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class PurchaseOrdersFromRecommendationsCreate(BaseModel):
    items: list[PurchaseOrderDraftItemCreate] = Field(min_length=1)

    @field_validator("items")
    @classmethod
    def validate_unique_product_branch(
        cls,
        value: list[PurchaseOrderDraftItemCreate],
    ) -> list[PurchaseOrderDraftItemCreate]:
        seen: set[tuple[int, int]] = set()
        for item in value:
            key = (item.product_id, item.branch_id)
            if key in seen:
                raise ValueError("Each product and branch can only be submitted once.")
            seen.add(key)
        return value


class PurchaseOrderReceiveItem(BaseModel):
    item_id: int
    quantity_received: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class PurchaseOrderReceive(BaseModel):
    items: list[PurchaseOrderReceiveItem] = Field(min_length=1)

    @field_validator("items")
    @classmethod
    def validate_unique_items(
        cls,
        value: list[PurchaseOrderReceiveItem],
    ) -> list[PurchaseOrderReceiveItem]:
        seen: set[int] = set()
        for item in value:
            if item.item_id in seen:
                raise ValueError("Each purchase order item can only be received once per request.")
            seen.add(item.item_id)
        return value


class PurchaseOrderItemRead(BaseModel):
    id: int
    product_id: int
    product_sku: str
    product_name: str
    quantity_ordered: Decimal
    quantity_received: Decimal
    remaining_quantity: Decimal
    unit_cost: Decimal
    line_total: Decimal


class PurchaseOrderListItemRead(BaseModel):
    id: int
    po_number: str
    supplier_id: int
    supplier_name: str
    branch_id: int
    branch_name: str
    status: PurchaseOrderStatus
    order_date: date
    expected_delivery_date: date | None
    total_amount: Decimal
    created_by: int
    created_by_name: str
    approved_by: int | None
    approved_by_name: str | None
    approved_at: datetime | None
    item_count: int
    total_quantity_ordered: Decimal
    total_quantity_received: Decimal
    created_at: datetime
    updated_at: datetime


class PurchaseOrderRead(PurchaseOrderListItemRead):
    items: list[PurchaseOrderItemRead]


class PurchaseOrderDraftItemRead(PurchaseOrderItemRead):
    pass


class PurchaseOrderDraftRead(PurchaseOrderRead):
    pass
