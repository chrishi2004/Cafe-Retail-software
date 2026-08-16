from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import raise_conflict
from app.models import Product, ProductBarcode


def normalize_barcode(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = "".join(value.strip().split()).upper()
    return normalized or None


def ensure_barcode_available(db: Session, barcode: str | None, product_id: int | None = None) -> None:
    normalized = normalize_barcode(barcode)
    if normalized is None:
        return

    existing_product = db.scalar(select(Product).where(Product.primary_barcode == normalized))
    if existing_product is not None and existing_product.id != product_id:
        raise_conflict("Product barcode already exists.")

    existing_barcode = db.scalar(select(ProductBarcode).where(ProductBarcode.barcode == normalized))
    if existing_barcode is not None and existing_barcode.product_id != product_id:
        raise_conflict("Product barcode already exists.")


def generate_internal_barcode(product_id: int, sku: str) -> str:
    compact_sku = "".join(character for character in sku.upper() if character.isalnum())
    suffix = compact_sku[-4:] if compact_sku else "ITEM"
    return f"HR{product_id:08d}{suffix}"
