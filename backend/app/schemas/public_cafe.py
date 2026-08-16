from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PublicQrResolveRead(BaseModel):
    cafe_name: str
    table_code: str
    table_display_name: str
    session_public_id: str
    guest_access: str
    guest_expires_at: datetime
    ordering_enabled: bool = True


class PublicMenuCategoryRead(BaseModel):
    public_id: str
    name: str
    display_order: int


class PublicMenuItemRead(BaseModel):
    public_id: str
    category_public_id: str
    name: str
    description: str | None
    image_reference: str | None
    selling_price: Decimal
    preparation_area: str
    available: bool
    display_order: int


class PublicMenuRead(BaseModel):
    cafe_name: str
    table_code: str
    table_display_name: str
    session_public_id: str
    session_status: str
    categories: list[PublicMenuCategoryRead]
    items: list[PublicMenuItemRead]


class PublicOrderItemInput(BaseModel):
    menu_item_public_id: str = Field(min_length=8, max_length=64)
    quantity: int = Field(ge=1, le=20)
    notes: str | None = Field(default=None, max_length=300)

    model_config = ConfigDict(extra="forbid")

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class PublicOrderCreate(BaseModel):
    items: list[PublicOrderItemInput] = Field(min_length=1, max_length=25)
    customer_notes: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")

    @field_validator("customer_notes")
    @classmethod
    def clean_customer_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class PublicOrderItemRead(BaseModel):
    menu_item_public_id: str
    name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    status: str
    notes: str | None


class PublicOrderRead(BaseModel):
    public_id: str
    order_number: str
    status: str
    subtotal: Decimal
    discount_total: Decimal
    estimated_total: Decimal
    customer_notes: str | None
    placed_at: datetime
    items: list[PublicOrderItemRead]
    replayed: bool = False


class PublicSessionOrdersRead(BaseModel):
    cafe_name: str
    table_code: str
    table_display_name: str
    session_public_id: str
    session_status: str
    orders: list[PublicOrderRead]


class PublicBillRequestRead(BaseModel):
    session_public_id: str
    session_status: str
    bill_requested_at: datetime
