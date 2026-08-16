from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import ProductItemType


def normalize_blank(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return normalize_blank(value)


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(CategoryBase):
    pass


class CategoryRead(CategoryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class SupplierBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    contact_person: str | None = Field(default=None, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = None
    payment_terms: str | None = Field(default=None, max_length=100)
    lead_time_days: int = Field(default=7, ge=0, le=365)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("contact_person", "phone", "address", "payment_terms")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return normalize_blank(value)


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(SupplierBase):
    pass


class SupplierRead(SupplierBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class BranchBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    manager_name: str | None = Field(default=None, max_length=150)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("address", "city", "manager_name")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return normalize_blank(value)


class BranchCreate(BranchBase):
    pass


class BranchUpdate(BranchBase):
    pass


class BranchRead(BranchBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category_id: int
    supplier_id: int
    gst_rate_id: int | None = None
    unit_cost: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    selling_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    hsn_sac_code: str | None = Field(default=None, max_length=20)
    cess_rate_percent: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=5, decimal_places=2)
    primary_barcode: str | None = Field(default=None, max_length=64)
    unit_of_measure: str = Field(default="pcs", min_length=1, max_length=20)
    mrp: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    brand: str | None = Field(default=None, max_length=120)
    manufacturer: str | None = Field(default=None, max_length=160)
    item_type: ProductItemType = ProductItemType.GOODS
    batch_tracking_enabled: bool = False
    serial_tracking_enabled: bool = False
    expiry_tracking_enabled: bool = False
    reorder_threshold: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    target_stock_level: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    is_active: bool = True

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("primary_barcode")
    @classmethod
    def normalize_barcode(cls, value: str | None) -> str | None:
        normalized = normalize_blank(value)
        if normalized is None:
            return None
        return "".join(normalized.split()).upper()

    @field_validator("hsn_sac_code")
    @classmethod
    def normalize_hsn(cls, value: str | None) -> str | None:
        normalized = normalize_blank(value)
        return normalized.upper() if normalized else None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("description", "brand", "manufacturer")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return normalize_blank(value)

    @field_validator("unit_of_measure")
    @classmethod
    def normalize_unit(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def service_items_do_not_track_stock_detail(self) -> "ProductBase":
        if self.item_type == ProductItemType.SERVICE and (
            self.batch_tracking_enabled or self.serial_tracking_enabled or self.expiry_tracking_enabled
        ):
            raise ValueError("Service items cannot enable batch, serial, or expiry tracking.")
        return self


class ProductCreate(ProductBase):
    pass


class ProductUpdate(ProductBase):
    pass


class ProductRead(ProductBase):
    id: int
    category_name: str
    supplier_name: str
    gst_rate_name: str | None = None
    gst_rate_percent: Decimal | None = None
    total_quantity_on_hand: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    stock_status: str = Field(default="No stock records", max_length=40)

    model_config = ConfigDict(from_attributes=True)
