from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PublishedCategoryInput(BaseModel):
    source_category_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True


class PublishedItemInput(BaseModel):
    source_menu_item_id: str = Field(min_length=1, max_length=64)
    source_product_id: str | None = Field(default=None, max_length=64)
    source_category_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=180)
    description: str | None = None
    image_reference: str | None = Field(default=None, max_length=500)
    selling_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    preparation_area: str = Field(min_length=1, max_length=20)
    available: bool = True
    display_order: int = Field(default=0, ge=0)

    @field_validator("preparation_area")
    @classmethod
    def validate_preparation_area(cls, value: str) -> str:
        if value not in {"kitchen", "beverage", "counter", "none"}:
            raise ValueError("Unsupported preparation area.")
        return value


class PublishedTableInput(BaseModel):
    source_table_id: str = Field(min_length=1, max_length=64)
    table_code: str = Field(min_length=1, max_length=60)
    table_display_name: str = Field(min_length=1, max_length=120)
    public_reference: str = Field(min_length=8, max_length=64)
    verifier_digest: str = Field(min_length=64, max_length=64)
    valid_until: datetime | None = None
    disabled_at: datetime | None = None
    available: bool = True


class AvailabilityInput(BaseModel):
    source_product_id: str = Field(min_length=1, max_length=64)
    available: bool


class MenuPublicationInput(BaseModel):
    publication_id: UUID
    business_group_id: str = Field(min_length=1, max_length=64)
    company_id: str = Field(min_length=1, max_length=64)
    branch_id: str = Field(min_length=1, max_length=64)
    version: int = Field(ge=1)
    snapshot_at: datetime
    categories: list[PublishedCategoryInput]
    items: list[PublishedItemInput]
    tables: list[PublishedTableInput]
    availability: list[AvailabilityInput] = Field(default_factory=list)


class MenuPublicationRead(BaseModel):
    publication_id: UUID
    version: int
    state: str
    snapshot_at: datetime
    activated_at: datetime | None
    replayed: bool = False


class SafeMenuCategoryRead(BaseModel):
    source_category_id: str
    name: str
    display_order: int


class SafeMenuItemRead(BaseModel):
    source_menu_item_id: str
    source_category_id: str
    name: str
    description: str | None
    image_reference: str | None
    selling_price: Decimal
    preparation_area: str
    available: bool
    display_order: int


class SafeMenuRead(BaseModel):
    publication_id: UUID
    version: int
    snapshot_at: datetime
    stale_age_seconds: int
    categories: list[SafeMenuCategoryRead]
    items: list[SafeMenuItemRead]
