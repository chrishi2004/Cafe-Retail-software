from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import BranchScope, ensure_branch_access
from app.api.errors import raise_bad_request, raise_forbidden, raise_not_found
from app.models import (
    Branch,
    Inventory,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    StockMovement,
    StockMovementType,
    Supplier,
    User,
    UserRole,
)
from app.schemas.purchase_orders import (
    PurchaseOrderCreate,
    PurchaseOrderDraftItemCreate,
    PurchaseOrderDraftRead,
    PurchaseOrderItemCreate,
    PurchaseOrderItemRead,
    PurchaseOrderListItemRead,
    PurchaseOrderRead,
    PurchaseOrderReceive,
    PurchaseOrderUpdate,
    PurchaseOrdersFromRecommendationsCreate,
)
from app.services.audit import write_audit_log

MONEY = Decimal("0.01")
QUANTITY = Decimal("0.01")

OPEN_ORDER_STATUSES = {
    PurchaseOrderStatus.DRAFT,
    PurchaseOrderStatus.PENDING_APPROVAL,
    PurchaseOrderStatus.APPROVED,
    PurchaseOrderStatus.ORDERED,
    PurchaseOrderStatus.PARTIALLY_RECEIVED,
}


@dataclass(frozen=True)
class PurchaseOrderFilters:
    branch_id: int | None = None
    supplier_id: int | None = None
    status: PurchaseOrderStatus | None = None
    search: str | None = None
    limit: int = 100


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def quantity(value: Decimal) -> Decimal:
    return value.quantize(QUANTITY, rounding=ROUND_HALF_UP)


def purchase_order_options():
    return (
        joinedload(PurchaseOrder.branch),
        joinedload(PurchaseOrder.supplier),
        joinedload(PurchaseOrder.creator),
        joinedload(PurchaseOrder.approver),
        joinedload(PurchaseOrder.items).joinedload(PurchaseOrderItem.product),
    )


def remaining_quantity(item: PurchaseOrderItem) -> Decimal:
    return quantity(max(item.quantity_ordered - item.quantity_received, Decimal("0.00")))


def purchase_order_item_to_read(item: PurchaseOrderItem) -> PurchaseOrderItemRead:
    return PurchaseOrderItemRead(
        id=item.id,
        product_id=item.product_id,
        product_sku=item.product.sku,
        product_name=item.product.name,
        quantity_ordered=quantity(item.quantity_ordered),
        quantity_received=quantity(item.quantity_received),
        remaining_quantity=remaining_quantity(item),
        unit_cost=money(item.unit_cost),
        line_total=money(item.line_total),
    )


def purchase_order_to_list_read(purchase_order: PurchaseOrder) -> PurchaseOrderListItemRead:
    items = list(purchase_order.items)
    return PurchaseOrderListItemRead(
        id=purchase_order.id,
        po_number=purchase_order.po_number,
        supplier_id=purchase_order.supplier_id,
        supplier_name=purchase_order.supplier.name,
        branch_id=purchase_order.branch_id,
        branch_name=purchase_order.branch.name,
        status=purchase_order.status,
        order_date=purchase_order.order_date,
        expected_delivery_date=purchase_order.expected_delivery_date,
        total_amount=money(purchase_order.total_amount),
        created_by=purchase_order.created_by,
        created_by_name=purchase_order.creator.name,
        approved_by=purchase_order.approved_by,
        approved_by_name=purchase_order.approver.name if purchase_order.approver else None,
        approved_at=purchase_order.approved_at,
        item_count=len(items),
        total_quantity_ordered=quantity(sum((item.quantity_ordered for item in items), Decimal("0.00"))),
        total_quantity_received=quantity(sum((item.quantity_received for item in items), Decimal("0.00"))),
        created_at=purchase_order.created_at,
        updated_at=purchase_order.updated_at,
    )


def purchase_order_to_read(purchase_order: PurchaseOrder) -> PurchaseOrderRead:
    list_read = purchase_order_to_list_read(purchase_order)
    return PurchaseOrderRead(
        **list_read.model_dump(),
        items=[purchase_order_item_to_read(item) for item in purchase_order.items],
    )


def apply_purchase_order_scope(statement, branch_scope: BranchScope, branch_id: int | None):
    if branch_scope.all_branches:
        if branch_id is not None:
            return statement.where(PurchaseOrder.branch_id == branch_id)
        return statement

    if branch_id is not None and branch_id not in branch_scope.branch_ids:
        raise_forbidden("You can only access purchase orders for your assigned branch.")

    return statement.where(PurchaseOrder.branch_id.in_(branch_scope.branch_ids))


def query_purchase_orders(
    db: Session,
    *,
    branch_scope: BranchScope,
    filters: PurchaseOrderFilters,
) -> list[PurchaseOrderListItemRead]:
    statement = (
        select(PurchaseOrder)
        .options(*purchase_order_options())
        .join(PurchaseOrder.supplier)
        .join(PurchaseOrder.branch)
        .order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc())
        .limit(max(1, min(filters.limit, 500)))
    )
    statement = apply_purchase_order_scope(statement, branch_scope, filters.branch_id)

    if filters.supplier_id is not None:
        statement = statement.where(PurchaseOrder.supplier_id == filters.supplier_id)
    if filters.status is not None:
        statement = statement.where(PurchaseOrder.status == filters.status)
    if filters.search:
        term = f"%{filters.search.strip()}%"
        statement = statement.where(
            PurchaseOrder.po_number.ilike(term)
            | Supplier.name.ilike(term)
            | Branch.name.ilike(term)
        )

    return [purchase_order_to_list_read(row) for row in db.scalars(statement).unique().all()]


def get_purchase_order_detail(
    db: Session,
    *,
    purchase_order_id: int,
    user: User,
) -> PurchaseOrderRead:
    purchase_order = db.scalar(
        select(PurchaseOrder)
        .options(*purchase_order_options())
        .where(PurchaseOrder.id == purchase_order_id)
        .execution_options(populate_existing=True)
    )
    if purchase_order is None:
        raise_not_found("Purchase order not found.")

    ensure_branch_access(user, purchase_order.branch_id)
    return purchase_order_to_read(purchase_order)


def load_purchase_order_for_update(db: Session, purchase_order_id: int, user: User) -> PurchaseOrder:
    purchase_order = db.scalar(
        select(PurchaseOrder)
        .options(*purchase_order_options())
        .where(PurchaseOrder.id == purchase_order_id)
        .with_for_update()
    )
    if purchase_order is None:
        raise_not_found("Purchase order not found.")

    ensure_branch_access(user, purchase_order.branch_id)
    return purchase_order


def ensure_purchase_order_create_permission(user: User, branch_id: int) -> None:
    if user.role == UserRole.ANALYST:
        raise_forbidden("Analysts can view purchase orders but cannot create them.")
    if user.role == UserRole.STAFF:
        raise_forbidden("Staff purchase order creation is not configured.")
    if user.role not in {UserRole.ADMIN, UserRole.STORE_MANAGER}:
        raise_forbidden("You do not have permission to create purchase orders.")
    ensure_branch_access(user, branch_id)


def ensure_purchase_order_operational_permission(user: User, branch_id: int) -> None:
    if user.role == UserRole.ADMIN:
        return
    if user.role == UserRole.STORE_MANAGER:
        ensure_branch_access(user, branch_id)
        return
    if user.role == UserRole.ANALYST:
        raise_forbidden("Analysts are read-only for purchase order operations.")
    raise_forbidden("You do not have permission to update purchase orders.")


def ensure_purchase_order_approval_permission(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise_forbidden("Only admins can approve purchase orders.")


def ensure_cancel_permission(user: User, purchase_order: PurchaseOrder) -> None:
    if user.role == UserRole.ADMIN:
        return
    if user.role == UserRole.STORE_MANAGER and purchase_order.status in {
        PurchaseOrderStatus.DRAFT,
        PurchaseOrderStatus.PENDING_APPROVAL,
    }:
        ensure_branch_access(user, purchase_order.branch_id)
        return
    raise_forbidden("You do not have permission to cancel this purchase order.")


def validate_branch_and_supplier(db: Session, branch_id: int, supplier_id: int) -> tuple[Branch, Supplier]:
    branch = db.get(Branch, branch_id)
    if branch is None or not branch.is_active:
        raise_not_found("Branch not found.")

    supplier = db.get(Supplier, supplier_id)
    if supplier is None or not supplier.is_active:
        raise_not_found("Supplier not found.")

    return branch, supplier


def validate_purchase_order_items(
    db: Session,
    *,
    supplier_id: int,
    items: list[PurchaseOrderItemCreate],
) -> dict[int, Product]:
    product_ids = {item.product_id for item in items}
    products = {
        product.id: product
        for product in db.scalars(select(Product).where(Product.id.in_(product_ids))).all()
    }
    if product_ids - products.keys():
        raise_not_found("One or more products were not found.")

    for item in items:
        product = products[item.product_id]
        if not product.is_active:
            raise_bad_request(f"Inactive product {product.sku} cannot be added to a purchase order.")
        if product.supplier_id != supplier_id:
            raise_bad_request(f"Product {product.sku} belongs to a different supplier.")

    return products


def set_purchase_order_items(
    db: Session,
    *,
    purchase_order: PurchaseOrder,
    items: list[PurchaseOrderItemCreate],
    products: dict[int, Product],
) -> None:
    purchase_order.items = []
    db.flush()

    total_amount = Decimal("0.00")
    for item in items:
        product = products[item.product_id]
        ordered_quantity = quantity(item.quantity_ordered)
        unit_cost = money(item.unit_cost if item.unit_cost is not None else product.unit_cost)
        line_total = money(ordered_quantity * unit_cost)
        total_amount += line_total
        purchase_order.items.append(
            PurchaseOrderItem(
                product_id=product.id,
                quantity_ordered=ordered_quantity,
                quantity_received=Decimal("0.00"),
                unit_cost=unit_cost,
                line_total=line_total,
            )
        )

    purchase_order.total_amount = money(total_amount)
    db.flush()


def purchase_order_snapshot(purchase_order: PurchaseOrder) -> dict[str, object]:
    return {
        "po_number": purchase_order.po_number,
        "supplier_id": purchase_order.supplier_id,
        "branch_id": purchase_order.branch_id,
        "status": purchase_order.status.value,
        "order_date": purchase_order.order_date.isoformat(),
        "expected_delivery_date": purchase_order.expected_delivery_date.isoformat()
        if purchase_order.expected_delivery_date
        else None,
        "total_amount": str(purchase_order.total_amount),
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "quantity_ordered": str(quantity(item.quantity_ordered)),
                "quantity_received": str(quantity(item.quantity_received)),
                "unit_cost": str(money(item.unit_cost)),
                "line_total": str(money(item.line_total)),
            }
            for item in purchase_order.items
        ],
    }


def create_purchase_order(
    db: Session,
    *,
    payload: PurchaseOrderCreate,
    user: User,
    request: Request,
) -> PurchaseOrderRead:
    ensure_purchase_order_create_permission(user, payload.branch_id)

    try:
        _, supplier = validate_branch_and_supplier(db, payload.branch_id, payload.supplier_id)
        products = validate_purchase_order_items(db, supplier_id=payload.supplier_id, items=payload.items)
        order_date = payload.order_date or datetime.now(UTC).date()
        purchase_order = PurchaseOrder(
            po_number=f"PO-{order_date:%Y%m%d}-{uuid4().hex[:8].upper()}",
            supplier_id=payload.supplier_id,
            branch_id=payload.branch_id,
            status=PurchaseOrderStatus.DRAFT,
            order_date=order_date,
            expected_delivery_date=payload.expected_delivery_date
            or order_date + timedelta(days=supplier.lead_time_days),
            total_amount=Decimal("0.00"),
            created_by=user.id,
        )
        db.add(purchase_order)
        db.flush()
        set_purchase_order_items(db, purchase_order=purchase_order, items=payload.items, products=products)
        db.flush()

        write_audit_log(
            db,
            action="purchase_orders.create",
            entity_type="purchase_order",
            entity_id=purchase_order.id,
            user=user,
            new_value_json=purchase_order_snapshot(purchase_order),
            request=request,
        )
        purchase_order_id = purchase_order.id
        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_purchase_order_detail(db, purchase_order_id=purchase_order_id, user=user)


def update_purchase_order(
    db: Session,
    *,
    purchase_order_id: int,
    payload: PurchaseOrderUpdate,
    user: User,
    request: Request,
) -> PurchaseOrderRead:
    try:
        purchase_order = load_purchase_order_for_update(db, purchase_order_id, user)
        if purchase_order.status != PurchaseOrderStatus.DRAFT:
            raise_bad_request("Only draft purchase orders can be edited.")

        ensure_purchase_order_create_permission(user, payload.branch_id)
        validate_branch_and_supplier(db, payload.branch_id, payload.supplier_id)
        products = validate_purchase_order_items(db, supplier_id=payload.supplier_id, items=payload.items)
        old_value = purchase_order_snapshot(purchase_order)

        purchase_order.supplier_id = payload.supplier_id
        purchase_order.branch_id = payload.branch_id
        purchase_order.order_date = payload.order_date or purchase_order.order_date
        purchase_order.expected_delivery_date = payload.expected_delivery_date
        set_purchase_order_items(db, purchase_order=purchase_order, items=payload.items, products=products)

        write_audit_log(
            db,
            action="purchase_orders.update",
            entity_type="purchase_order",
            entity_id=purchase_order.id,
            user=user,
            old_value_json=old_value,
            new_value_json=purchase_order_snapshot(purchase_order),
            request=request,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_purchase_order_detail(db, purchase_order_id=purchase_order_id, user=user)


def transition_purchase_order(
    db: Session,
    *,
    purchase_order_id: int,
    user: User,
    request: Request,
    from_statuses: set[PurchaseOrderStatus],
    to_status: PurchaseOrderStatus,
    action: str,
    admin_only: bool = False,
) -> PurchaseOrderRead:
    try:
        purchase_order = load_purchase_order_for_update(db, purchase_order_id, user)
        if admin_only:
            ensure_purchase_order_approval_permission(user)
        else:
            ensure_purchase_order_operational_permission(user, purchase_order.branch_id)

        if purchase_order.status not in from_statuses:
            allowed = ", ".join(status.value for status in sorted(from_statuses, key=lambda item: item.value))
            raise_bad_request(f"Purchase order must be in one of these statuses: {allowed}.")
        if not purchase_order.items:
            raise_bad_request("Purchase order must have at least one line item.")

        old_status = purchase_order.status
        purchase_order.status = to_status
        if to_status == PurchaseOrderStatus.APPROVED:
            purchase_order.approved_by = user.id
            purchase_order.approved_at = datetime.now(UTC)

        write_audit_log(
            db,
            action=action,
            entity_type="purchase_order",
            entity_id=purchase_order.id,
            user=user,
            old_value_json={"status": old_status.value},
            new_value_json={"status": purchase_order.status.value},
            request=request,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_purchase_order_detail(db, purchase_order_id=purchase_order_id, user=user)


def submit_purchase_order(
    db: Session,
    *,
    purchase_order_id: int,
    user: User,
    request: Request,
) -> PurchaseOrderRead:
    return transition_purchase_order(
        db,
        purchase_order_id=purchase_order_id,
        user=user,
        request=request,
        from_statuses={PurchaseOrderStatus.DRAFT},
        to_status=PurchaseOrderStatus.PENDING_APPROVAL,
        action="purchase_orders.submit",
    )


def approve_purchase_order(
    db: Session,
    *,
    purchase_order_id: int,
    user: User,
    request: Request,
) -> PurchaseOrderRead:
    return transition_purchase_order(
        db,
        purchase_order_id=purchase_order_id,
        user=user,
        request=request,
        from_statuses={PurchaseOrderStatus.PENDING_APPROVAL},
        to_status=PurchaseOrderStatus.APPROVED,
        action="purchase_orders.approve",
        admin_only=True,
    )


def get_or_create_inventory(
    db: Session,
    *,
    product_id: int,
    branch_id: int,
) -> Inventory:
    inventory = db.scalar(
        select(Inventory)
        .where(Inventory.product_id == product_id, Inventory.branch_id == branch_id)
        .with_for_update()
    )
    if inventory is None:
        inventory = Inventory(
            product_id=product_id,
            branch_id=branch_id,
            quantity_on_hand=Decimal("0.00"),
            quantity_reserved=Decimal("0.00"),
            quantity_on_order=Decimal("0.00"),
        )
        db.add(inventory)
        db.flush()
    return inventory


def update_quantity_on_order(
    db: Session,
    *,
    purchase_order: PurchaseOrder,
    direction: int,
) -> list[dict[str, str | int]]:
    changes: list[dict[str, str | int]] = []
    for item in purchase_order.items:
        remaining = remaining_quantity(item)
        if remaining <= 0:
            continue
        inventory = get_or_create_inventory(
            db,
            product_id=item.product_id,
            branch_id=purchase_order.branch_id,
        )
        old_quantity_on_order = inventory.quantity_on_order
        if direction > 0:
            inventory.quantity_on_order = quantity(inventory.quantity_on_order + remaining)
        else:
            inventory.quantity_on_order = quantity(max(inventory.quantity_on_order - remaining, Decimal("0.00")))
        inventory.last_updated_at = datetime.now(UTC)
        changes.append(
            {
                "product_id": item.product_id,
                "old_quantity_on_order": str(quantity(old_quantity_on_order)),
                "new_quantity_on_order": str(quantity(inventory.quantity_on_order)),
            }
        )
    return changes


def mark_purchase_order_ordered(
    db: Session,
    *,
    purchase_order_id: int,
    user: User,
    request: Request,
) -> PurchaseOrderRead:
    try:
        purchase_order = load_purchase_order_for_update(db, purchase_order_id, user)
        ensure_purchase_order_operational_permission(user, purchase_order.branch_id)
        if purchase_order.status != PurchaseOrderStatus.APPROVED:
            raise_bad_request("Only approved purchase orders can be marked as ordered.")

        old_status = purchase_order.status
        purchase_order.status = PurchaseOrderStatus.ORDERED
        on_order_changes = update_quantity_on_order(db, purchase_order=purchase_order, direction=1)
        write_audit_log(
            db,
            action="purchase_orders.mark_ordered",
            entity_type="purchase_order",
            entity_id=purchase_order.id,
            user=user,
            old_value_json={"status": old_status.value},
            new_value_json={
                "status": purchase_order.status.value,
                "quantity_on_order_changes": on_order_changes,
            },
            request=request,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_purchase_order_detail(db, purchase_order_id=purchase_order_id, user=user)


def cancel_purchase_order(
    db: Session,
    *,
    purchase_order_id: int,
    user: User,
    request: Request,
) -> PurchaseOrderRead:
    try:
        purchase_order = load_purchase_order_for_update(db, purchase_order_id, user)
        ensure_cancel_permission(user, purchase_order)
        if purchase_order.status not in OPEN_ORDER_STATUSES:
            raise_bad_request("Only open purchase orders can be cancelled.")

        old_status = purchase_order.status
        on_order_changes: list[dict[str, str | int]] = []
        if purchase_order.status in {PurchaseOrderStatus.ORDERED, PurchaseOrderStatus.PARTIALLY_RECEIVED}:
            on_order_changes = update_quantity_on_order(db, purchase_order=purchase_order, direction=-1)

        purchase_order.status = PurchaseOrderStatus.CANCELLED
        write_audit_log(
            db,
            action="purchase_orders.cancel",
            entity_type="purchase_order",
            entity_id=purchase_order.id,
            user=user,
            old_value_json={"status": old_status.value},
            new_value_json={
                "status": purchase_order.status.value,
                "quantity_on_order_changes": on_order_changes,
            },
            request=request,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_purchase_order_detail(db, purchase_order_id=purchase_order_id, user=user)


def receive_purchase_order(
    db: Session,
    *,
    purchase_order_id: int,
    payload: PurchaseOrderReceive,
    user: User,
    request: Request,
) -> PurchaseOrderRead:
    try:
        purchase_order = load_purchase_order_for_update(db, purchase_order_id, user)
        ensure_purchase_order_operational_permission(user, purchase_order.branch_id)
        if purchase_order.status not in {PurchaseOrderStatus.ORDERED, PurchaseOrderStatus.PARTIALLY_RECEIVED}:
            raise_bad_request("Only ordered purchase orders can be received.")

        items_by_id = {item.id: item for item in purchase_order.items}
        received_changes: list[dict[str, str | int]] = []
        for receive_item in payload.items:
            item = items_by_id.get(receive_item.item_id)
            if item is None:
                raise_bad_request("One or more received items do not belong to this purchase order.")

            received_quantity = quantity(receive_item.quantity_received)
            if received_quantity > remaining_quantity(item):
                raise_bad_request(f"Received quantity exceeds remaining quantity for {item.product.sku}.")

            inventory = get_or_create_inventory(
                db,
                product_id=item.product_id,
                branch_id=purchase_order.branch_id,
            )
            old_quantity_on_hand = inventory.quantity_on_hand
            old_quantity_on_order = inventory.quantity_on_order
            inventory.quantity_on_hand = quantity(inventory.quantity_on_hand + received_quantity)
            inventory.quantity_on_order = quantity(max(inventory.quantity_on_order - received_quantity, Decimal("0.00")))
            inventory.last_updated_at = datetime.now(UTC)
            item.quantity_received = quantity(item.quantity_received + received_quantity)

            movement = StockMovement(
                product_id=item.product_id,
                branch_id=purchase_order.branch_id,
                movement_type=StockMovementType.PURCHASE_RECEIVED,
                quantity_change=received_quantity,
                reason=f"Received purchase order {purchase_order.po_number}",
                reference_type="purchase_order",
                reference_id=purchase_order.id,
                created_by=user.id,
            )
            db.add(movement)
            db.flush()
            received_changes.append(
                {
                    "product_id": item.product_id,
                    "purchase_order_item_id": item.id,
                    "quantity_received": str(received_quantity),
                    "old_quantity_on_hand": str(quantity(old_quantity_on_hand)),
                    "new_quantity_on_hand": str(quantity(inventory.quantity_on_hand)),
                    "old_quantity_on_order": str(quantity(old_quantity_on_order)),
                    "new_quantity_on_order": str(quantity(inventory.quantity_on_order)),
                    "movement_id": movement.id,
                }
            )

        old_status = purchase_order.status
        all_received = all(remaining_quantity(item) <= 0 for item in purchase_order.items)
        purchase_order.status = (
            PurchaseOrderStatus.RECEIVED if all_received else PurchaseOrderStatus.PARTIALLY_RECEIVED
        )

        write_audit_log(
            db,
            action="purchase_orders.receive",
            entity_type="purchase_order",
            entity_id=purchase_order.id,
            user=user,
            old_value_json={"status": old_status.value},
            new_value_json={
                "status": purchase_order.status.value,
                "received_items": received_changes,
            },
            request=request,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_purchase_order_detail(db, purchase_order_id=purchase_order_id, user=user)


def load_created_purchase_orders(db: Session, purchase_order_ids: list[int]) -> list[PurchaseOrderDraftRead]:
    statement = (
        select(PurchaseOrder)
        .options(*purchase_order_options())
        .where(PurchaseOrder.id.in_(purchase_order_ids))
        .order_by(PurchaseOrder.id)
        .execution_options(populate_existing=True)
    )
    return [PurchaseOrderDraftRead(**purchase_order_to_read(row).model_dump()) for row in db.scalars(statement).unique().all()]


def create_purchase_orders_from_recommendations(
    db: Session,
    *,
    payload: PurchaseOrdersFromRecommendationsCreate,
    user: User,
    request: Request,
) -> list[PurchaseOrderDraftRead]:
    try:
        branch_ids = {item.branch_id for item in payload.items}
        for branch_id in branch_ids:
            ensure_purchase_order_create_permission(user, branch_id)

        product_ids = {item.product_id for item in payload.items}
        products = {
            product.id: product
            for product in db.scalars(
                select(Product).options(joinedload(Product.supplier)).where(Product.id.in_(product_ids))
            ).all()
        }
        if product_ids - products.keys():
            raise_not_found("One or more products were not found.")

        branches = {branch.id: branch for branch in db.scalars(select(Branch).where(Branch.id.in_(branch_ids))).all()}
        if branch_ids - branches.keys():
            raise_not_found("One or more branches were not found.")

        inventories = {
            (inventory.product_id, inventory.branch_id): inventory
            for inventory in db.scalars(
                select(Inventory).where(
                    Inventory.product_id.in_(product_ids),
                    Inventory.branch_id.in_(branch_ids),
                )
            ).all()
        }

        grouped_items: dict[tuple[int, int], list[PurchaseOrderDraftItemCreate]] = defaultdict(list)
        for item in payload.items:
            product = products[item.product_id]
            branch = branches[item.branch_id]
            if not product.is_active:
                raise_bad_request(f"Inactive product {product.sku} cannot be added to a purchase order.")
            if not branch.is_active:
                raise_bad_request(f"Inactive branch {branch.name} cannot receive a purchase order.")
            if (item.product_id, item.branch_id) not in inventories:
                raise_bad_request(f"No inventory row exists for {product.sku} at {branch.name}.")
            grouped_items[(product.supplier_id, item.branch_id)].append(item)

        order_date = datetime.now(UTC).date()
        created_ids: list[int] = []
        for (supplier_id, branch_id), items in grouped_items.items():
            supplier = db.get(Supplier, supplier_id)
            if supplier is None:
                raise_not_found("Supplier not found.")

            purchase_order = PurchaseOrder(
                po_number=f"PO-{order_date:%Y%m%d}-{uuid4().hex[:8].upper()}",
                supplier_id=supplier_id,
                branch_id=branch_id,
                status=PurchaseOrderStatus.DRAFT,
                order_date=order_date,
                expected_delivery_date=order_date + timedelta(days=supplier.lead_time_days),
                total_amount=Decimal("0.00"),
                created_by=user.id,
            )
            db.add(purchase_order)
            db.flush()

            create_items = [
                PurchaseOrderItemCreate(
                    product_id=item.product_id,
                    quantity_ordered=item.quantity_ordered,
                    unit_cost=products[item.product_id].unit_cost,
                )
                for item in items
            ]
            set_purchase_order_items(
                db,
                purchase_order=purchase_order,
                items=create_items,
                products=products,
            )

            write_audit_log(
                db,
                action="purchase_orders.create_from_recommendations",
                entity_type="purchase_order",
                entity_id=purchase_order.id,
                user=user,
                new_value_json=purchase_order_snapshot(purchase_order),
                request=request,
            )
            created_ids.append(purchase_order.id)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return load_created_purchase_orders(db, created_ids)
