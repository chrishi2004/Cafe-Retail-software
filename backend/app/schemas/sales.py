from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class SaleItemCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)


class SaleCreate(BaseModel):
    branch_id: int
    sale_datetime: datetime | None = None
    tax_rate: Decimal = Field(default=Decimal("0.05"), ge=0, le=1, max_digits=5, decimal_places=4)
    items: list[SaleItemCreate] = Field(min_length=1)

    @field_validator("items")
    @classmethod
    def validate_items(cls, value: list[SaleItemCreate]) -> list[SaleItemCreate]:
        if not value:
            raise ValueError("At least one sale item is required.")
        return value


class SaleItemRead(BaseModel):
    id: int
    product_id: int
    product_sku: str
    product_name: str
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    line_total: Decimal
    gross_profit: Decimal


class SaleListItemRead(BaseModel):
    id: int
    sale_number: str
    branch_id: int
    branch_name: str
    sale_datetime: datetime
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total_amount: Decimal
    gross_profit: Decimal
    units_sold: Decimal
    item_count: int
    created_by: int
    created_by_name: str
    created_at: datetime


class SaleRead(SaleListItemRead):
    items: list[SaleItemRead]


class SalesSummaryRead(BaseModel):
    revenue: Decimal
    gross_profit: Decimal
    units_sold: Decimal
    transaction_count: int
    average_order_value: Decimal
    discount_total: Decimal
    tax_total: Decimal


class SalesTrendPoint(BaseModel):
    date: date
    revenue: Decimal
    gross_profit: Decimal
    units_sold: Decimal
    transaction_count: int
