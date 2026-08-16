from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.errors import raise_bad_request, raise_conflict
from app.models import (
    CafeOrder,
    CafeOrderItem,
    CafeOrderItemStatus,
    CafeOrderSource,
    CafeOrderStatus,
    CafeOrderStatusHistory,
    MenuCategory,
    MenuItem,
    Product,
    TableSession,
    TableSessionStatus,
    TableSessionType,
)


@dataclass(frozen=True)
class CafeOrderLineInput:
    menu_item_public_id: str
    quantity: int
    notes: str | None = None


def new_order_number(now: datetime | None = None) -> str:
    current = now or datetime.now(UTC)
    return f"C{current:%Y%m%d}-{secrets.token_hex(4).upper()}"


def create_order_snapshot(
    db: Session,
    *,
    company_id: int,
    branch_id: int,
    order_type: TableSessionType,
    source_channel: CafeOrderSource,
    lines: list[CafeOrderLineInput],
    customer_notes: str | None,
    table_session_id: int | None = None,
    guest_access_id: int | None = None,
    created_by: int | None = None,
    idempotency_key_hash: str | None = None,
    request_hash: str | None = None,
    guest_action: bool = False,
    history_reason: str = "Cafe order placed",
    public_id: str | None = None,
    order_number: str | None = None,
    now: datetime | None = None,
) -> CafeOrder:
    """Create the canonical Cafe order and item snapshots without committing.

    Both public QR and authenticated staff entry call this service. Prices,
    product links, source snapshots, and initial history therefore come from one
    backend path. The caller owns idempotency, authorization, and transaction
    commit/rollback boundaries.
    """

    if not lines:
        raise_bad_request("At least one Cafe order item is required.")

    requested_ids = [row.menu_item_public_id for row in lines]
    if len(requested_ids) != len(set(requested_ids)):
        raise_bad_request("Each menu item may appear only once per order.")
    if any(row.quantity < 1 or row.quantity > 20 for row in lines):
        raise_bad_request("Cafe order item quantity must be between 1 and 20.")

    locked_session: TableSession | None = None
    if order_type == TableSessionType.DINE_IN:
        if table_session_id is None:
            raise_bad_request("Dine-in orders require an active table session.")
        locked_session = db.scalar(
            select(TableSession)
            .where(
                TableSession.id == table_session_id,
                TableSession.company_id == company_id,
                TableSession.branch_id == branch_id,
            )
            .with_for_update()
        )
        if locked_session is None or locked_session.status != TableSessionStatus.OPEN:
            raise_conflict("This table session is no longer accepting items.")
    elif table_session_id is not None:
        raise_bad_request("Takeaway and counter orders cannot use a dine-in table session.")

    menu_items = list(
        db.scalars(
            select(MenuItem).where(
                MenuItem.company_id == company_id,
                MenuItem.public_id.in_(requested_ids),
                MenuItem.is_active.is_(True),
                MenuItem.available.is_(True),
                or_(MenuItem.branch_id.is_(None), MenuItem.branch_id == branch_id),
            )
        ).all()
    )
    by_public_id = {row.public_id: row for row in menu_items}
    if set(by_public_id) != set(requested_ids):
        raise_conflict("One or more selected menu items are unavailable.")

    active_categories = set(
        db.scalars(
            select(MenuCategory.id).where(
                MenuCategory.company_id == company_id,
                MenuCategory.is_active.is_(True),
                or_(MenuCategory.branch_id.is_(None), MenuCategory.branch_id == branch_id),
            )
        ).all()
    )
    if any(item.category_id not in active_categories for item in menu_items):
        raise_conflict("One or more selected menu items are unavailable.")

    current = now or datetime.now(UTC)
    order = CafeOrder(
        public_id=public_id or secrets.token_urlsafe(18),
        company_id=company_id,
        branch_id=branch_id,
        table_session_id=locked_session.id if locked_session is not None else None,
        guest_access_id=guest_access_id,
        order_number=order_number or new_order_number(current),
        order_type=order_type,
        source_channel=source_channel,
        status=CafeOrderStatus.PLACED,
        subtotal=Decimal("0.00"),
        discount_total=Decimal("0.00"),
        estimated_total=Decimal("0.00"),
        customer_notes=customer_notes,
        created_by=created_by,
        idempotency_key_hash=idempotency_key_hash,
        request_hash=request_hash,
        placed_at=current,
    )
    db.add(order)
    db.flush()

    subtotal = Decimal("0.00")
    for requested in lines:
        menu_item = by_public_id[requested.menu_item_public_id]
        product_sku: str | None = None
        if menu_item.product_id is not None:
            product = db.get(Product, menu_item.product_id)
            if product is None or product.company_id != company_id or not product.is_active:
                raise_conflict("One or more selected menu items are unavailable.")
            product_sku = product.sku

        line_total = (menu_item.selling_price * requested.quantity).quantize(Decimal("0.01"))
        subtotal += line_total
        db.add(
            CafeOrderItem(
                company_id=company_id,
                branch_id=branch_id,
                cafe_order_id=order.id,
                menu_item_id=menu_item.id,
                product_id=menu_item.product_id,
                menu_item_public_id_snapshot=menu_item.public_id,
                menu_item_name_snapshot=menu_item.name,
                product_sku_snapshot=product_sku,
                quantity=requested.quantity,
                unit_price_snapshot=menu_item.selling_price,
                discount_amount=Decimal("0.00"),
                line_total=line_total,
                item_status=CafeOrderItemStatus.PLACED,
                preparation_notes=requested.notes,
                source_channel=source_channel,
                created_by=created_by,
            )
        )

    order.subtotal = subtotal.quantize(Decimal("0.01"))
    order.estimated_total = order.subtotal
    db.add(
        CafeOrderStatusHistory(
            company_id=company_id,
            branch_id=branch_id,
            cafe_order_id=order.id,
            from_status=None,
            to_status=CafeOrderStatus.PLACED,
            changed_by=created_by,
            guest_action=guest_action,
            reason=history_reason,
            created_at=current,
        )
    )
    db.flush()
    return order
