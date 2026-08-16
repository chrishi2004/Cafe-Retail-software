from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import PreparationArea, TableSessionStatus, TableSessionType


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class MenuCategoryCreate(BaseModel):
    branch_id: int | None = None
    name: str = Field(min_length=1, max_length=120)
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class MenuCategoryUpdate(MenuCategoryCreate):
    pass


class MenuCategoryRead(MenuCategoryCreate):
    id: int
    public_id: str
    company_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MenuItemCreate(BaseModel):
    branch_id: int | None = None
    category_id: int
    product_id: int | None = None
    name: str = Field(min_length=1, max_length=180)
    description: str | None = None
    image_reference: str | None = Field(default=None, max_length=500)
    selling_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    preparation_area: PreparationArea = PreparationArea.NONE
    available: bool = True
    is_active: bool = True
    display_order: int = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("description", "image_reference")
    @classmethod
    def normalize_optional(cls, value: str | None) -> str | None:
        return _clean(value)


class MenuItemUpdate(MenuItemCreate):
    expected_version: int | None = Field(default=None, ge=1)


class MenuItemAvailabilityUpdate(BaseModel):
    available: bool
    expected_version: int | None = Field(default=None, ge=1)


class MenuItemRead(MenuItemCreate):
    id: int
    public_id: str
    company_id: int
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CafeTableCreate(BaseModel):
    branch_id: int
    table_code: str = Field(min_length=1, max_length=60)
    display_name: str = Field(min_length=1, max_length=120)
    capacity: int | None = Field(default=None, gt=0)
    area: str | None = Field(default=None, max_length=100)
    is_active: bool = True

    @field_validator("table_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("area")
    @classmethod
    def normalize_area(cls, value: str | None) -> str | None:
        return _clean(value)


class CafeTableUpdate(CafeTableCreate):
    expected_version: int | None = Field(default=None, ge=1)


class CafeTableRead(CafeTableCreate):
    id: int
    company_id: int
    version: int
    active_session_public_id: str | None = None
    active_session_status: TableSessionStatus | None = None
    qr_active: bool = False
    qr_public_reference: str | None = None
    created_at: datetime
    updated_at: datetime


class QRRotateRequest(BaseModel):
    expires_in_days: int = Field(default=365, ge=1, le=3650)
    public_base_url: str = Field(default="/order", min_length=1, max_length=500)


class QRTokenStatusRead(BaseModel):
    public_reference: str
    token_prefix: str
    expires_at: datetime | None
    revoked_at: datetime | None
    last_used_at: datetime | None
    active: bool
    created_at: datetime


class QRPrintDataRead(BaseModel):
    table_code: str
    table_display_name: str
    public_reference: str
    token_prefix: str
    expires_at: datetime | None
    qr_svg_data_uri: str | None = None


class QRRotateRead(QRPrintDataRead):
    raw_token: str


class QRPrintDataRequest(BaseModel):
    raw_token: str = Field(min_length=20, max_length=1000)
    public_base_url: str = Field(default="/order", min_length=1, max_length=500)


class QRRevokeRead(BaseModel):
    public_reference: str
    revoked_at: datetime


class PublicQRResolveRead(BaseModel):
    cafe_name: str
    table_code: str
    table_display_name: str
    ordering_enabled: bool = False
    message: str = "Online ordering is not enabled yet."


class TableSessionOpen(BaseModel):
    table_id: int
    session_type: TableSessionType = TableSessionType.DINE_IN


class TableSessionClose(BaseModel):
    expected_version: int | None = Field(default=None, ge=1)
    cancel: bool = False


class TableSessionRead(BaseModel):
    id: int
    public_id: str
    company_id: int
    branch_id: int
    table_id: int
    session_type: TableSessionType
    status: TableSessionStatus
    opened_by: int | None
    opened_at: datetime
    bill_requested_at: datetime | None
    closed_by: int | None
    closed_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)