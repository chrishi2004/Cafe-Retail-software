from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import CafeOrderSource, CafeOrderStatus, PreparationArea, TableSessionStatus, TableSessionType


class StaffOrderItemInput(BaseModel):
    menu_item_public_id: str = Field(min_length=8, max_length=64)
    quantity: int = Field(ge=1, le=20)
    notes: str | None = Field(default=None, max_length=300)

    model_config = ConfigDict(extra="forbid")

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class StaffOrderCreate(BaseModel):
    order_type: TableSessionType
    branch_id: int | None = Field(default=None, ge=1)
    table_session_public_id: str | None = Field(default=None, min_length=8, max_length=64)
    items: list[StaffOrderItemInput] = Field(min_length=1, max_length=25)
    customer_notes: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")

    @field_validator("customer_notes")
    @classmethod
    def clean_customer_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class OrderVersionInput(BaseModel):
    expected_version: int = Field(ge=1)

    model_config = ConfigDict(extra="forbid")


class OrderReasonInput(OrderVersionInput):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("A reason is required.")
        return cleaned


class TableSessionBillRequestInput(BaseModel):
    expected_version: int = Field(ge=1)

    model_config = ConfigDict(extra="forbid")


class TableSessionBillRequestRead(BaseModel):
    public_id: str
    status: TableSessionStatus
    bill_requested_at: datetime
    version: int
    affected_order_public_ids: list[str]


class StaffOrderItemRead(BaseModel):
    menu_item_public_id: str
    name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    status: str
    preparation_area: PreparationArea
    notes: str | None


class StaffOrderRead(BaseModel):
    public_id: str
    order_number: str
    order_type: TableSessionType
    source_channel: CafeOrderSource
    status: CafeOrderStatus
    branch_id: int
    table_session_public_id: str | None
    table_code: str | None
    subtotal: Decimal
    discount_total: Decimal
    estimated_total: Decimal
    customer_notes: str | None
    created_by: int | None
    accepted_by: int | None
    version: int
    placed_at: datetime
    accepted_at: datetime | None
    served_at: datetime | None
    cancelled_at: datetime | None
    items: list[StaffOrderItemRead]


class KitchenOrderItemRead(BaseModel):
    name: str
    quantity: int
    status: str
    preparation_area: PreparationArea
    notes: str | None


class KitchenOrderRead(BaseModel):
    public_id: str
    order_number: str
    table_reference: str | None
    source_channel: CafeOrderSource
    status: CafeOrderStatus
    age_seconds: int
    version: int
    items: list[KitchenOrderItemRead]
