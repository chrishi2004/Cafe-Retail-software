from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import BranchScope
from app.api.errors import raise_bad_request, raise_forbidden, raise_not_found
from app.models import (
    AuditLog,
    Branch,
    Category,
    Inventory,
    Product,
    StockMovement,
    StockMovementType,
    Supplier,
    User,
    UserRole,
)
from app.schemas.inventory import (
    InventoryRead,
    ProductInventoryDetail,
    StockAdjustmentCreate,
    StockAdjustmentResponse,
    StockMovementRead,
)
from app.services.audit import write_audit_log


@dataclass(frozen=True)
class InventoryFilters:
    branch_id: int | None = None
    category_id: int | None = None
    supplier_id: int | None = None
    search: str | None = None
    low_stock: bool | None = None


@dataclass(frozen=True)
class MovementFilters:
    product_id: int | None = None
    branch_id: int | None = None
    movement_type: StockMovementType | None = None
    limit: int = 100


def inventory_to_read(inventory: Inventory) -> InventoryRead:
    product = inventory.product
    stock_value = (inventory.quantity_on_hand * product.unit_cost).quantize(Decimal("0.01"))
    return InventoryRead(
        id=inventory.id,
        product_id=product.id,
        product_sku=product.sku,
        product_name=product.name,
        category_id=product.category_id,
        category_name=product.category.name,
        supplier_id=product.supplier_id,
        supplier_name=product.supplier.name,
        branch_id=inventory.branch_id,
        branch_name=inventory.branch.name,
        quantity_on_hand=inventory.quantity_on_hand,
        quantity_reserved=inventory.quantity_reserved,
        quantity_on_order=inventory.quantity_on_order,
        reorder_threshold=product.reorder_threshold,
        target_stock_level=product.target_stock_level,
        unit_cost=product.unit_cost,
        stock_value=stock_value,
        is_low_stock=inventory.quantity_on_hand <= product.reorder_threshold,
        last_updated_at=inventory.last_updated_at,
    )


def movement_to_read(movement: StockMovement) -> StockMovementRead:
    return StockMovementRead(
        id=movement.id,
        product_id=movement.product_id,
        product_sku=movement.product.sku,
        product_name=movement.product.name,
        branch_id=movement.branch_id,
        branch_name=movement.branch.name,
        movement_type=movement.movement_type,
        quantity_change=movement.quantity_change,
        reason=movement.reason,
        reference_type=movement.reference_type,
        reference_id=movement.reference_id,
        created_by=movement.created_by,
        created_by_name=movement.creator.name if movement.creator else None,
        created_at=movement.created_at,
    )


def apply_branch_scope(statement, branch_scope: BranchScope, branch_id: int | None):
    if branch_scope.all_branches:
        if branch_id is not None:
            return statement.where(Inventory.branch_id == branch_id)
        return statement

    if branch_id is not None and branch_id not in branch_scope.branch_ids:
        raise_forbidden("You can only access inventory for your assigned branch.")

    return statement.where(Inventory.branch_id.in_(branch_scope.branch_ids))


def apply_movement_branch_scope(statement, branch_scope: BranchScope, branch_id: int | None):
    if branch_scope.all_branches:
        if branch_id is not None:
            return statement.where(StockMovement.branch_id == branch_id)
        return statement

    if branch_id is not None and branch_id not in branch_scope.branch_ids:
        raise_forbidden("You can only access stock movements for your assigned branch.")

    return statement.where(StockMovement.branch_id.in_(branch_scope.branch_ids))


def query_inventory(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: InventoryFilters,
) -> list[InventoryRead]:
    statement = (
        select(Inventory)
        .options(
            joinedload(Inventory.branch),
            joinedload(Inventory.product).joinedload(Product.category),
            joinedload(Inventory.product).joinedload(Product.supplier),
        )
        .join(Inventory.product)
        .join(Product.category)
        .join(Product.supplier)
        .join(Inventory.branch)
        .where(Product.is_active.is_(True))
        .order_by(Branch.name, Product.name)
    )
    statement = apply_branch_scope(statement, branch_scope, filters.branch_id)

    if filters.category_id is not None:
        statement = statement.where(Product.category_id == filters.category_id)
    if filters.supplier_id is not None:
        statement = statement.where(Product.supplier_id == filters.supplier_id)
    if filters.low_stock is True:
        statement = statement.where(Inventory.quantity_on_hand <= Product.reorder_threshold)
    if filters.low_stock is False:
        statement = statement.where(Inventory.quantity_on_hand > Product.reorder_threshold)
    if filters.search:
        term = f"%{filters.search.strip()}%"
        statement = statement.where(
            Product.sku.ilike(term)
            | Product.name.ilike(term)
            | Category.name.ilike(term)
            | Supplier.name.ilike(term)
        )

    return [inventory_to_read(row) for row in db.scalars(statement).unique().all()]


def get_product_inventory_detail(
    db: Session,
    *,
    product_id: int,
    branch_scope: BranchScope,
) -> ProductInventoryDetail:
    product = db.get(Product, product_id)
    if product is None:
        raise_not_found("Product not found.")

    inventory_rows = query_inventory(
        db,
        branch_scope=branch_scope,
        filters=InventoryFilters(search=None),
    )
    rows = [row for row in inventory_rows if row.product_id == product_id]
    if not rows:
        raise_not_found("No accessible inventory found for this product.")

    return ProductInventoryDetail(
        product_id=product_id,
        product_sku=rows[0].product_sku,
        product_name=rows[0].product_name,
        category_name=rows[0].category_name,
        supplier_name=rows[0].supplier_name,
        total_quantity_on_hand=sum((row.quantity_on_hand for row in rows), Decimal("0.00")),
        total_stock_value=sum((row.stock_value for row in rows), Decimal("0.00")),
        is_low_stock_any_branch=any(row.is_low_stock for row in rows),
        inventory=rows,
    )


def query_low_stock(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: InventoryFilters,
) -> list[InventoryRead]:
    return query_inventory(
        db,
        branch_scope=branch_scope,
        filters=InventoryFilters(
            branch_id=filters.branch_id,
            category_id=filters.category_id,
            supplier_id=filters.supplier_id,
            search=filters.search,
            low_stock=True,
        ),
    )


def query_movements(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: MovementFilters,
) -> list[StockMovementRead]:
    limit = max(1, min(filters.limit, 500))
    statement = (
        select(StockMovement)
        .options(
            joinedload(StockMovement.branch),
            joinedload(StockMovement.product),
            joinedload(StockMovement.creator),
        )
        .join(StockMovement.product)
        .join(StockMovement.branch)
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(limit)
    )
    statement = apply_movement_branch_scope(statement, branch_scope, filters.branch_id)

    if filters.product_id is not None:
        statement = statement.where(StockMovement.product_id == filters.product_id)
    if filters.movement_type is not None:
        statement = statement.where(StockMovement.movement_type == filters.movement_type)

    return [movement_to_read(row) for row in db.scalars(statement).unique().all()]


def ensure_adjust_permission(user: User, branch_id: int) -> None:
    if user.role == UserRole.ADMIN:
        return

    if user.role == UserRole.STORE_MANAGER:
        if user.branch_id == branch_id:
            return
        raise_forbidden("Store managers can only adjust inventory for their assigned branch.")

    if user.role == UserRole.STAFF:
        raise_forbidden("Staff stock adjustment permission is not configured yet.")

    raise_forbidden("This role is read-only for inventory adjustments.")


def apply_stock_adjustment(
    db: Session,
    *,
    payload: StockAdjustmentCreate,
    user: User,
    request: Request,
) -> StockAdjustmentResponse:
    ensure_adjust_permission(user, payload.branch_id)

    product = db.get(Product, payload.product_id)
    if product is None:
        raise_not_found("Product not found.")

    branch = db.get(Branch, payload.branch_id)
    if branch is None:
        raise_not_found("Branch not found.")

    inventory = db.scalar(
        select(Inventory).where(
            Inventory.product_id == payload.product_id,
            Inventory.branch_id == payload.branch_id,
        )
    )
    if inventory is None:
        inventory = Inventory(
            product_id=payload.product_id,
            branch_id=payload.branch_id,
            quantity_on_hand=Decimal("0.00"),
            quantity_reserved=Decimal("0.00"),
            quantity_on_order=Decimal("0.00"),
        )
        db.add(inventory)
        db.flush()

    old_quantity = inventory.quantity_on_hand
    new_quantity = old_quantity + payload.quantity_change
    if new_quantity < 0:
        raise_bad_request("Adjustment would make quantity on hand negative.")

    inventory.quantity_on_hand = new_quantity
    inventory.last_updated_at = datetime.now(UTC)
    movement = StockMovement(
        product_id=payload.product_id,
        branch_id=payload.branch_id,
        movement_type=StockMovementType.MANUAL_ADJUSTMENT,
        quantity_change=payload.quantity_change,
        reason=payload.reason,
        reference_type="inventory_adjustment",
        reference_id=inventory.id,
        created_by=user.id,
    )
    db.add(movement)
    db.flush()

    write_audit_log(
        db,
        action="inventory.adjust",
        entity_type="inventory",
        entity_id=inventory.id,
        user=user,
        old_value_json={"quantity_on_hand": str(old_quantity)},
        new_value_json={
            "quantity_on_hand": str(new_quantity),
            "quantity_change": str(payload.quantity_change),
            "product_id": payload.product_id,
            "branch_id": payload.branch_id,
            "reason": payload.reason,
            "movement_id": movement.id,
        },
        request=request,
    )
    db.commit()

    inventory = db.scalar(
        select(Inventory)
        .options(
            joinedload(Inventory.branch),
            joinedload(Inventory.product).joinedload(Product.category),
            joinedload(Inventory.product).joinedload(Product.supplier),
        )
        .where(Inventory.id == inventory.id)
    )
    movement = db.scalar(
        select(StockMovement)
        .options(
            joinedload(StockMovement.branch),
            joinedload(StockMovement.product),
            joinedload(StockMovement.creator),
        )
        .where(StockMovement.id == movement.id)
    )
    if inventory is None or movement is None:
        raise_not_found("Adjustment could not be loaded after save.")

    return StockAdjustmentResponse(
        inventory=inventory_to_read(inventory),
        movement=movement_to_read(movement),
    )
