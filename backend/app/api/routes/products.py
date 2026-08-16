from decimal import Decimal
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import get_current_user, require_admin
from app.api.errors import raise_conflict, raise_not_found
from app.db.session import get_db
from app.models import Category, Product, ProductBarcode, ProductPriceHistory, Supplier, TaxRate, User
from app.schemas.master_data import ProductCreate, ProductRead, ProductUpdate
from app.services.audit import write_audit_log
from app.services.barcodes import ensure_barcode_available, normalize_barcode

router = APIRouter(prefix="/products", tags=["products"])


def product_to_read(product: Product) -> ProductRead:
    inventory_rows = list(product.inventory_items)
    total_quantity_on_hand = sum((row.quantity_on_hand for row in inventory_rows), Decimal("0.00"))
    if product.item_type == "service":
        stock_status = "Service"
    elif not inventory_rows:
        stock_status = "No stock records"
    elif total_quantity_on_hand <= 0:
        stock_status = "Out of stock"
    elif any(row.quantity_on_hand <= product.reorder_threshold for row in inventory_rows):
        stock_status = "Low stock"
    else:
        stock_status = "Healthy"

    return ProductRead(
        id=product.id,
        sku=product.sku,
        name=product.name,
        description=product.description,
        category_id=product.category_id,
        category_name=product.category.name,
        supplier_id=product.supplier_id,
        supplier_name=product.supplier.name,
        gst_rate_id=product.gst_rate_id,
        gst_rate_name=product.gst_rate.name if product.gst_rate else None,
        gst_rate_percent=product.gst_rate.rate_percent if product.gst_rate else None,
        unit_cost=product.unit_cost,
        selling_price=product.selling_price,
        hsn_sac_code=product.hsn_sac_code,
        cess_rate_percent=product.cess_rate_percent,
        primary_barcode=product.primary_barcode,
        unit_of_measure=product.unit_of_measure,
        mrp=product.mrp,
        brand=product.brand,
        manufacturer=product.manufacturer,
        item_type=product.item_type,
        batch_tracking_enabled=product.batch_tracking_enabled,
        serial_tracking_enabled=product.serial_tracking_enabled,
        expiry_tracking_enabled=product.expiry_tracking_enabled,
        reorder_threshold=product.reorder_threshold,
        target_stock_level=product.target_stock_level,
        total_quantity_on_hand=total_quantity_on_hand,
        stock_status=stock_status,
        is_active=product.is_active,
    )


def ensure_product_sku_available(db: Session, sku: str, product_id: int | None = None) -> None:
    existing = db.scalar(select(Product).where(Product.sku == sku))
    if existing is not None and existing.id != product_id:
        raise_conflict("Product SKU already exists.")


def ensure_product_relationships(db: Session, payload: ProductCreate | ProductUpdate) -> None:
    if db.get(Category, payload.category_id) is None:
        raise_not_found("Category not found.")
    if db.get(Supplier, payload.supplier_id) is None:
        raise_not_found("Supplier not found.")
    if payload.gst_rate_id is not None and db.get(TaxRate, payload.gst_rate_id) is None:
        raise_not_found("GST/tax rate not found.")


def get_product_or_404(db: Session, product_id: int) -> Product:
    product = db.scalar(
        select(Product)
        .options(
            joinedload(Product.category),
            joinedload(Product.supplier),
            joinedload(Product.gst_rate),
            selectinload(Product.inventory_items),
        )
        .where(Product.id == product_id)
    )
    if product is None:
        raise_not_found("Product not found.")
    return product


def product_payload_data(payload: ProductCreate | ProductUpdate) -> dict:
    data = payload.model_dump()
    data["primary_barcode"] = normalize_barcode(payload.primary_barcode)
    if isinstance(data.get("item_type"), Enum):
        data["item_type"] = data["item_type"].value
    return data


def json_safe_product_payload(payload: ProductCreate | ProductUpdate) -> dict[str, str | int | bool | None]:
    data = product_payload_data(payload)
    for key, value in data.items():
        if isinstance(value, Decimal):
            data[key] = str(value)
        elif isinstance(value, Enum):
            data[key] = value.value
    return data


def sync_primary_barcode(db: Session, product: Product, barcode: str | None) -> None:
    existing_primary = db.scalar(
        select(ProductBarcode).where(
            ProductBarcode.product_id == product.id,
            ProductBarcode.is_primary.is_(True),
        )
    )
    if barcode is None:
        if existing_primary is not None:
            db.delete(existing_primary)
        return

    if existing_primary is None:
        db.add(
            ProductBarcode(
                product_id=product.id,
                barcode=barcode,
                barcode_type="primary",
                is_primary=True,
                is_active=True,
            )
        )
        return

    existing_primary.barcode = barcode
    existing_primary.barcode_type = "primary"
    existing_primary.is_active = True


def add_price_history(
    db: Session,
    product: Product,
    user: User,
    old_unit_cost: Decimal | None,
    old_selling_price: Decimal | None,
    old_mrp: Decimal | None,
    reason: str,
) -> None:
    db.add(
        ProductPriceHistory(
            product_id=product.id,
            old_unit_cost=old_unit_cost,
            new_unit_cost=product.unit_cost,
            old_selling_price=old_selling_price,
            new_selling_price=product.selling_price,
            old_mrp=old_mrp,
            new_mrp=product.mrp,
            changed_by=user.id,
            reason=reason,
        )
    )


@router.get("", response_model=list[ProductRead])
def list_products(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    category_id: int | None = None,
    supplier_id: int | None = None,
    include_inactive: bool = Query(default=False),
) -> list[ProductRead]:
    statement = (
        select(Product)
        .options(
            joinedload(Product.category),
            joinedload(Product.supplier),
            joinedload(Product.gst_rate),
            selectinload(Product.inventory_items),
        )
        .join(Product.category)
        .join(Product.supplier)
        .order_by(Product.name)
    )
    if not include_inactive:
        statement = statement.where(Product.is_active.is_(True))
    if category_id is not None:
        statement = statement.where(Product.category_id == category_id)
    if supplier_id is not None:
        statement = statement.where(Product.supplier_id == supplier_id)
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                Product.sku.ilike(term),
                Product.name.ilike(term),
                Product.primary_barcode.ilike(term),
                Category.name.ilike(term),
                Supplier.name.ilike(term),
                Product.barcodes.any(ProductBarcode.barcode.ilike(term)),
            )
        )

    products = db.scalars(statement).unique().all()
    return [product_to_read(product) for product in products]


@router.get("/search", response_model=list[ProductRead])
def search_products(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    q: str = Query(min_length=1, max_length=120),
    include_inactive: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ProductRead]:
    term = f"%{q.strip()}%"
    statement = (
        select(Product)
        .options(
            joinedload(Product.category),
            joinedload(Product.supplier),
            joinedload(Product.gst_rate),
            selectinload(Product.inventory_items),
        )
        .where(
            or_(
                Product.sku.ilike(term),
                Product.name.ilike(term),
                Product.primary_barcode.ilike(term),
                Product.barcodes.any(ProductBarcode.barcode.ilike(term)),
            )
        )
        .order_by(Product.name)
        .limit(limit)
    )
    if not include_inactive:
        statement = statement.where(Product.is_active.is_(True))

    products = db.scalars(statement).unique().all()
    return [product_to_read(product) for product in products]


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    request: Request,
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ProductRead:
    ensure_product_sku_available(db, payload.sku)
    ensure_barcode_available(db, payload.primary_barcode)
    ensure_product_relationships(db, payload)
    product = Product(**product_payload_data(payload))
    db.add(product)
    db.flush()
    sync_primary_barcode(db, product, product.primary_barcode)
    add_price_history(
        db,
        product,
        _admin,
        old_unit_cost=None,
        old_selling_price=None,
        old_mrp=None,
        reason="Initial product pricing",
    )
    write_audit_log(
        db,
        action="product.create",
        entity_type="product",
        entity_id=product.id,
        user=_admin,
        new_value_json=json_safe_product_payload(payload),
        request=request,
    )
    db.commit()
    return product_to_read(get_product_or_404(db, product.id))


@router.get("/{product_id}", response_model=ProductRead)
def get_product(
    product_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProductRead:
    return product_to_read(get_product_or_404(db, product_id))


@router.put("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    request: Request,
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ProductRead:
    product = get_product_or_404(db, product_id)
    ensure_product_sku_available(db, payload.sku, product_id=product.id)
    ensure_barcode_available(db, payload.primary_barcode, product_id=product.id)
    ensure_product_relationships(db, payload)
    old_value = product_to_read(product).model_dump(mode="json")
    old_unit_cost = product.unit_cost
    old_selling_price = product.selling_price
    old_mrp = product.mrp
    for field, value in product_payload_data(payload).items():
        setattr(product, field, value)
    if (
        old_unit_cost != product.unit_cost
        or old_selling_price != product.selling_price
        or old_mrp != product.mrp
    ):
        add_price_history(
            db,
            product,
            _admin,
            old_unit_cost=old_unit_cost,
            old_selling_price=old_selling_price,
            old_mrp=old_mrp,
            reason="Product pricing updated",
        )
    sync_primary_barcode(db, product, product.primary_barcode)
    write_audit_log(
        db,
        action="product.update",
        entity_type="product",
        entity_id=product.id,
        user=_admin,
        old_value_json=old_value,
        new_value_json=json_safe_product_payload(payload),
        request=request,
    )
    db.commit()
    return product_to_read(get_product_or_404(db, product.id))


@router.patch("/{product_id}/deactivate", response_model=ProductRead)
def deactivate_product(
    product_id: int,
    request: Request,
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ProductRead:
    product = get_product_or_404(db, product_id)
    old_value = {"is_active": product.is_active}
    product.is_active = False
    write_audit_log(
        db,
        action="product.deactivate",
        entity_type="product",
        entity_id=product.id,
        user=_admin,
        old_value_json=old_value,
        new_value_json={"is_active": False},
        request=request,
    )
    db.commit()
    return product_to_read(get_product_or_404(db, product.id))
