from __future__ import annotations

import enum
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CompanyScopeMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.forecast import Forecast
    from app.models.inventory import Inventory, StockMovement
    from app.models.purchase_order import PurchaseOrderItem
    from app.models.sale import SaleItem
    from app.models.supplier import Supplier
    from app.models.business_settings import TaxRate


class ProductItemType(str, enum.Enum):
    GOODS = "goods"
    SERVICE = "service"


class Product(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    gst_rate_id: Mapped[int | None] = mapped_column(ForeignKey("tax_rates.id"), nullable=True)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    hsn_sac_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cess_rate_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    primary_barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit_of_measure: Mapped[str] = mapped_column(String(20), nullable=False, default="pcs")
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(160), nullable=True)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False, default=ProductItemType.GOODS.value)
    batch_tracking_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    serial_tracking_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    expiry_tracking_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    reorder_threshold: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    target_stock_level: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    category: Mapped[Category] = relationship(back_populates="products")
    supplier: Mapped[Supplier] = relationship(back_populates="products")
    gst_rate: Mapped[TaxRate | None] = relationship()
    inventory_items: Mapped[list[Inventory]] = relationship(back_populates="product")
    stock_movements: Mapped[list[StockMovement]] = relationship(back_populates="product")
    sale_items: Mapped[list[SaleItem]] = relationship(back_populates="product")
    purchase_order_items: Mapped[list[PurchaseOrderItem]] = relationship(back_populates="product")
    forecasts: Mapped[list[Forecast]] = relationship(back_populates="product")
    barcodes: Mapped[list[ProductBarcode]] = relationship(back_populates="product", cascade="all, delete-orphan")
    price_history: Mapped[list[ProductPriceHistory]] = relationship(back_populates="product", cascade="all, delete-orphan")
    inventory_batches: Mapped[list[InventoryBatch]] = relationship(back_populates="product", cascade="all, delete-orphan")
    serial_numbers: Mapped[list[SerialNumber]] = relationship(back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("company_id", "sku", name="uq_products_company_sku"),
        UniqueConstraint("company_id", "primary_barcode", name="uq_products_company_primary_barcode"),
        Index("ix_products_company_id", "company_id"),
        Index("ix_products_category_id", "category_id"),
        Index("ix_products_supplier_id", "supplier_id"),
        Index("ix_products_gst_rate_id", "gst_rate_id"),
        Index("ix_products_primary_barcode", "primary_barcode"),
        CheckConstraint("unit_cost >= 0", name="products_unit_cost_non_negative"),
        CheckConstraint("selling_price >= 0", name="products_selling_price_non_negative"),
        CheckConstraint("reorder_threshold >= 0", name="products_reorder_threshold_non_negative"),
        CheckConstraint("target_stock_level >= 0", name="products_target_stock_non_negative"),
        CheckConstraint("mrp IS NULL OR mrp >= 0", name="products_mrp_non_negative"),
        CheckConstraint("cess_rate_percent >= 0", name="products_cess_non_negative"),
        CheckConstraint("item_type IN ('goods', 'service')", name="products_item_type"),
    )


class ProductBarcode(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "product_barcodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    barcode: Mapped[str] = mapped_column(String(64), nullable=False)
    barcode_type: Mapped[str] = mapped_column(String(30), nullable=False, default="internal")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    product: Mapped[Product] = relationship(back_populates="barcodes")

    __table_args__ = (
        UniqueConstraint("company_id", "barcode", name="uq_product_barcodes_company_barcode"),
        Index("ix_product_barcodes_company_id", "company_id"),
        Index("ix_product_barcodes_product_id", "product_id"),
        Index("ix_product_barcodes_barcode", "barcode"),
    )


class ProductUnit(TimestampMixin, Base):
    __tablename__ = "product_units"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class ProductPriceHistory(CompanyScopeMixin, Base):
    __tablename__ = "product_price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    old_unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    new_unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    old_selling_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    new_selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    old_mrp: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    new_mrp: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    product: Mapped[Product] = relationship(back_populates="price_history")

    __table_args__ = (
        Index("ix_product_price_history_company_id", "company_id"),
        Index("ix_product_price_history_product_id", "product_id"),
        Index("ix_product_price_history_changed_at", "changed_at"),
        CheckConstraint("new_unit_cost >= 0", name="product_price_history_unit_cost_non_negative"),
        CheckConstraint("new_selling_price >= 0", name="product_price_history_selling_price_non_negative"),
        CheckConstraint("new_mrp IS NULL OR new_mrp >= 0", name="product_price_history_mrp_non_negative"),
    )


class InventoryBatch(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "inventory_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(80), nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    quantity_on_hand: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    product: Mapped[Product] = relationship(back_populates="inventory_batches")

    __table_args__ = (
        UniqueConstraint("product_id", "branch_id", "batch_number", name="uq_inventory_batches_product_branch_batch"),
        Index("ix_inventory_batches_company_id", "company_id"),
        Index("ix_inventory_batches_product_id", "product_id"),
        Index("ix_inventory_batches_branch_id", "branch_id"),
        Index("ix_inventory_batches_expiry_date", "expiry_date"),
        CheckConstraint("quantity_on_hand >= 0", name="inventory_batches_quantity_non_negative"),
        CheckConstraint("mrp IS NULL OR mrp >= 0", name="inventory_batches_mrp_non_negative"),
    )


class SerialNumber(CompanyScopeMixin, TimestampMixin, Base):
    __tablename__ = "serial_numbers"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    serial_number: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="available")

    product: Mapped[Product] = relationship(back_populates="serial_numbers")

    __table_args__ = (
        Index("ix_serial_numbers_company_id", "company_id"),
        Index("ix_serial_numbers_product_id", "product_id"),
        Index("ix_serial_numbers_branch_id", "branch_id"),
        Index("ix_serial_numbers_status", "status"),
    )
