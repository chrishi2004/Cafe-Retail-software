from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.errors import raise_bad_request, raise_conflict, raise_forbidden, raise_not_found
from app.core.config import settings
from app.core.scope import ScopeContext
from app.models import (
    Branch,
    BusinessType,
    CafeOrder,
    CafeOrderItem,
    CafeOrderItemStatus,
    CafeOrderSource,
    CafeOrderStatus,
    CafeOrderStatusHistory,
    CafeTable,
    CloudRecordLink,
    Company,
    MenuItem,
    PreparationArea,
    TableSession,
    TableSessionStatus,
    TableSessionType,
    User,
    UserRole,
)
from app.schemas.cafe_orders import (
    KitchenOrderItemRead,
    KitchenOrderRead,
    StaffOrderCreate,
    StaffOrderItemRead,
    StaffOrderRead,
)
from app.services.audit import write_audit_log
from app.services.cafe_order_engine import CafeOrderLineInput, create_order_snapshot
from app.sync.cafe_orders import enqueue_cafe_order_status_snapshot


READ_ROLES = {UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.ORDER_TAKER, UserRole.ANALYST}
WRITE_ROLES = {UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.ORDER_TAKER}
KITCHEN_ROLES = {UserRole.KITCHEN}

VALID_TRANSITIONS: dict[CafeOrderStatus, set[CafeOrderStatus]] = {
    CafeOrderStatus.PLACED: {
        CafeOrderStatus.ACCEPTED,
        CafeOrderStatus.REJECTED,
        CafeOrderStatus.CANCELLED,
    },
    CafeOrderStatus.ACCEPTED: {CafeOrderStatus.PREPARING, CafeOrderStatus.CANCELLED},
    CafeOrderStatus.PREPARING: {CafeOrderStatus.READY, CafeOrderStatus.CANCELLED},
    CafeOrderStatus.READY: {CafeOrderStatus.SERVED},
    CafeOrderStatus.SERVED: {CafeOrderStatus.BILL_REQUESTED},
    CafeOrderStatus.BILL_REQUESTED: set(),
    CafeOrderStatus.BILLED: {CafeOrderStatus.CLOSED},
    CafeOrderStatus.CLOSED: set(),
    CafeOrderStatus.REJECTED: set(),
    CafeOrderStatus.CANCELLED: set(),
}

ITEM_STATUS_BY_ORDER_STATUS: dict[CafeOrderStatus, CafeOrderItemStatus] = {
    CafeOrderStatus.ACCEPTED: CafeOrderItemStatus.ACCEPTED,
    CafeOrderStatus.PREPARING: CafeOrderItemStatus.PREPARING,
    CafeOrderStatus.READY: CafeOrderItemStatus.READY,
    CafeOrderStatus.SERVED: CafeOrderItemStatus.SERVED,
    CafeOrderStatus.REJECTED: CafeOrderItemStatus.REJECTED,
    CafeOrderStatus.CANCELLED: CafeOrderItemStatus.CANCELLED,
}


def _require_cafe_company(db: Session, scope: ScopeContext) -> Company:
    if scope.company_id is None:
        raise_forbidden("Select the Cafe venture before using Cafe operations.")
    company = db.get(Company, scope.company_id)
    if company is None or not company.is_active or company.business_type != BusinessType.CAFE:
        raise_forbidden("Cafe operations are not available in this venture.")
    return company


def _check_role(scope: ScopeContext, roles: set[UserRole]) -> None:
    if scope.role != UserRole.SUPER_ADMIN and scope.role not in roles:
        raise_forbidden("This Cafe action is not available to your role.")


def _resolve_branch(db: Session, scope: ScopeContext, branch_id: int | None) -> Branch:
    company = _require_cafe_company(db, scope)
    resolved = branch_id
    if resolved is None and len(scope.branch_ids) == 1 and scope.branch_ids[0] > 0:
        resolved = scope.branch_ids[0]
    if resolved is None:
        branches = list(
            db.scalars(
                select(Branch)
                .where(Branch.company_id == company.id, Branch.is_active.is_(True))
                .order_by(Branch.id)
                .limit(2)
            ).all()
        )
        if len(branches) == 1:
            resolved = branches[0].id
        else:
            raise_bad_request("Select a Cafe branch for this operation.")
    if scope.branch_ids and resolved not in scope.branch_ids:
        raise_forbidden("This branch is outside your assigned scope.")
    branch = db.scalar(
        select(Branch).where(
            Branch.id == resolved,
            Branch.company_id == company.id,
            Branch.is_active.is_(True),
        )
    )
    if branch is None:
        raise_not_found("Cafe branch not found.")
    return branch


def _source_for_actor(user: User, order_type: TableSessionType) -> CafeOrderSource:
    if user.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.STORE_MANAGER}:
        return CafeOrderSource.MANAGER
    if order_type == TableSessionType.COUNTER:
        return CafeOrderSource.BILLING_COUNTER
    return CafeOrderSource.ORDER_TAKER


def _session_for_staff_order(
    db: Session,
    *,
    scope: ScopeContext,
    branch: Branch,
    order_type: TableSessionType,
    session_public_id: str | None,
) -> TableSession | None:
    if order_type != TableSessionType.DINE_IN:
        if session_public_id is not None:
            raise_bad_request("Takeaway and counter orders do not use a table session.")
        return None
    if not session_public_id:
        raise_bad_request("Dine-in orders require an active table session.")
    session = db.scalar(
        select(TableSession).where(
            TableSession.public_id == session_public_id,
            TableSession.company_id == scope.company_id,
            TableSession.branch_id == branch.id,
        )
    )
    if session is None:
        raise_not_found("Cafe table session not found.")
    if session.status != TableSessionStatus.OPEN:
        raise_conflict("This table session is no longer accepting items.")
    return session


def _order_items(db: Session, order: CafeOrder) -> list[CafeOrderItem]:
    return list(
        db.scalars(
            select(CafeOrderItem)
            .where(CafeOrderItem.cafe_order_id == order.id)
            .order_by(CafeOrderItem.id)
        ).all()
    )


def _table_context(db: Session, order: CafeOrder) -> tuple[str | None, str | None]:
    if order.table_session_id is None:
        return None, None
    session = db.get(TableSession, order.table_session_id)
    if session is None:
        return None, None
    table = db.get(CafeTable, session.table_id)
    return session.public_id, table.table_code if table is not None else None


def order_to_staff_read(db: Session, order: CafeOrder) -> StaffOrderRead:
    session_public_id, table_code = _table_context(db, order)
    items = _order_items(db, order)
    menu_rows = {
        row.id: row
        for row in db.scalars(
            select(MenuItem).where(MenuItem.id.in_({item.menu_item_id for item in items} or {-1}))
        ).all()
    }
    return StaffOrderRead(
        public_id=order.public_id,
        order_number=order.order_number,
        order_type=order.order_type,
        source_channel=order.source_channel,
        status=order.status,
        branch_id=order.branch_id,
        table_session_public_id=session_public_id,
        table_code=table_code,
        subtotal=order.subtotal,
        discount_total=order.discount_total,
        estimated_total=order.estimated_total,
        customer_notes=order.customer_notes,
        created_by=order.created_by,
        accepted_by=order.accepted_by,
        version=order.version,
        placed_at=order.placed_at,
        accepted_at=order.accepted_at,
        served_at=order.served_at,
        cancelled_at=order.cancelled_at,
        items=[
            StaffOrderItemRead(
                menu_item_public_id=item.menu_item_public_id_snapshot,
                name=item.menu_item_name_snapshot,
                quantity=item.quantity,
                unit_price=item.unit_price_snapshot,
                line_total=item.line_total,
                status=item.item_status.value,
                preparation_area=(
                    menu_rows[item.menu_item_id].preparation_area
                    if item.menu_item_id in menu_rows
                    else PreparationArea.NONE
                ),
                notes=item.preparation_notes,
            )
            for item in items
        ],
    )


def create_staff_order(
    db: Session,
    *,
    scope: ScopeContext,
    user: User,
    payload: StaffOrderCreate,
    request: Request | None = None,
) -> StaffOrderRead:
    _check_role(scope, WRITE_ROLES)
    branch = _resolve_branch(db, scope, payload.branch_id)
    session = _session_for_staff_order(
        db,
        scope=scope,
        branch=branch,
        order_type=payload.order_type,
        session_public_id=payload.table_session_public_id,
    )
    source = _source_for_actor(user, payload.order_type)
    order = create_order_snapshot(
        db,
        company_id=branch.company_id,
        branch_id=branch.id,
        table_session_id=session.id if session else None,
        order_type=payload.order_type,
        source_channel=source,
        created_by=user.id,
        lines=[
            CafeOrderLineInput(
                menu_item_public_id=row.menu_item_public_id,
                quantity=row.quantity,
                notes=row.notes,
            )
            for row in payload.items
        ],
        customer_notes=payload.customer_notes,
        guest_action=False,
        history_reason="Staff order placed",
    )
    write_audit_log(
        db,
        action="cafe_order_create",
        entity_type="cafe_order",
        entity_id=order.id,
        user=user,
        company_id=branch.company_id,
        new_value_json={
            "public_id": order.public_id,
            "status": order.status.value,
            "source_channel": order.source_channel.value,
            "order_type": order.order_type.value,
        },
        request=request,
    )
    db.commit()
    db.refresh(order)
    return order_to_staff_read(db, order)


def list_staff_orders(
    db: Session,
    *,
    scope: ScopeContext,
    branch_id: int | None = None,
    table_id: int | None = None,
    status_filter: CafeOrderStatus | None = None,
    source: CafeOrderSource | None = None,
    preparation_area: PreparationArea | None = None,
    business_date: date | None = None,
    unbilled_only: bool = False,
    limit: int = 200,
) -> list[StaffOrderRead]:
    _check_role(scope, READ_ROLES)
    company = _require_cafe_company(db, scope)
    statement = select(CafeOrder).where(CafeOrder.company_id == company.id)
    if scope.branch_ids:
        statement = statement.where(CafeOrder.branch_id.in_(scope.branch_ids))
    if branch_id is not None:
        _resolve_branch(db, scope, branch_id)
        statement = statement.where(CafeOrder.branch_id == branch_id)
    if table_id is not None:
        statement = statement.join(TableSession, CafeOrder.table_session_id == TableSession.id).where(
            TableSession.table_id == table_id
        )
    if status_filter is not None:
        statement = statement.where(CafeOrder.status == status_filter)
    if source is not None:
        statement = statement.where(CafeOrder.source_channel == source)
    if preparation_area is not None:
        statement = (
            statement.join(CafeOrderItem, CafeOrderItem.cafe_order_id == CafeOrder.id)
            .join(MenuItem, MenuItem.id == CafeOrderItem.menu_item_id)
            .where(MenuItem.preparation_area == preparation_area)
            .distinct()
        )
    if business_date is not None:
        start = datetime.combine(business_date, time.min, tzinfo=UTC)
        end = start + timedelta(days=1)
        statement = statement.where(CafeOrder.placed_at >= start, CafeOrder.placed_at < end)
    if unbilled_only:
        statement = statement.where(CafeOrder.billed_invoice_id.is_(None))
    orders = list(
        db.scalars(statement.order_by(CafeOrder.placed_at.desc(), CafeOrder.id.desc()).limit(limit)).all()
    )
    return [order_to_staff_read(db, row) for row in orders]


def get_staff_order(db: Session, *, scope: ScopeContext, public_id: str) -> StaffOrderRead:
    _check_role(scope, READ_ROLES)
    company = _require_cafe_company(db, scope)
    statement = select(CafeOrder).where(
        CafeOrder.public_id == public_id,
        CafeOrder.company_id == company.id,
    )
    if scope.branch_ids:
        statement = statement.where(CafeOrder.branch_id.in_(scope.branch_ids))
    order = db.scalar(statement)
    if order is None:
        raise_not_found("Cafe order not found.")
    return order_to_staff_read(db, order)


def _stale() -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "stale_state", "message": "This order changed. Refresh and try again."},
    )


def _load_for_transition(
    db: Session,
    *,
    scope: ScopeContext,
    public_id: str,
    expected_version: int,
) -> CafeOrder:
    company = _require_cafe_company(db, scope)
    statement = (
        select(CafeOrder)
        .where(CafeOrder.public_id == public_id, CafeOrder.company_id == company.id)
        .with_for_update()
    )
    if scope.branch_ids:
        statement = statement.where(CafeOrder.branch_id.in_(scope.branch_ids))
    order = db.scalar(statement)
    if order is None:
        raise_not_found("Cafe order not found.")
    if order.version != expected_version:
        _stale()
    return order


def _sync_status_if_linked(db: Session, order: CafeOrder) -> None:
    if not settings.sync_device_id:
        return
    link = db.scalar(
        select(CloudRecordLink).where(
            CloudRecordLink.provider == "cloud_gateway",
            CloudRecordLink.aggregate_type == "cafe_order",
            CloudRecordLink.local_record_id == order.id,
        )
    )
    if link is not None:
        enqueue_cafe_order_status_snapshot(
            db,
            order=order,
            local_device_id=settings.sync_device_id,
            status_value=order.status.value,
        )


def transition_order(
    db: Session,
    *,
    scope: ScopeContext,
    user: User,
    public_id: str,
    expected_version: int,
    target: CafeOrderStatus,
    reason: str | None = None,
    request: Request | None = None,
) -> StaffOrderRead:
    allowed_roles = WRITE_ROLES
    if target in {CafeOrderStatus.PREPARING, CafeOrderStatus.READY}:
        allowed_roles = WRITE_ROLES | KITCHEN_ROLES
    _check_role(scope, allowed_roles)

    order = _load_for_transition(
        db,
        scope=scope,
        public_id=public_id,
        expected_version=expected_version,
    )
    old = order.status
    if target not in VALID_TRANSITIONS.get(old, set()):
        raise_conflict(f"Cafe order cannot move from {old.value} to {target.value}.")
    if target in {CafeOrderStatus.REJECTED, CafeOrderStatus.CANCELLED} and not reason:
        raise_bad_request("A reason is required for rejection or cancellation.")
    if target == CafeOrderStatus.REJECTED and user.role == UserRole.KITCHEN:
        raise_forbidden("Kitchen cannot reject customer orders.")
    if target == CafeOrderStatus.CANCELLED:
        if old in {CafeOrderStatus.ACCEPTED, CafeOrderStatus.PREPARING} and user.role not in {
            UserRole.SUPER_ADMIN,
            UserRole.ADMIN,
            UserRole.STORE_MANAGER,
        }:
            raise_forbidden("Only a manager can cancel an accepted or preparing order.")

    now = datetime.now(UTC)
    order.status = target
    order.version += 1
    if target == CafeOrderStatus.ACCEPTED:
        order.accepted_by = user.id
        order.accepted_at = now
    elif target == CafeOrderStatus.SERVED:
        order.served_at = now
    elif target == CafeOrderStatus.CANCELLED:
        order.cancelled_at = now

    item_target = ITEM_STATUS_BY_ORDER_STATUS.get(target)
    if item_target is not None:
        for item in _order_items(db, order):
            if item.billed_invoice_item_id is None:
                item.item_status = item_target
                item.version += 1

    if target == CafeOrderStatus.BILL_REQUESTED and order.table_session_id is not None:
        session = db.scalar(
            select(TableSession).where(TableSession.id == order.table_session_id).with_for_update()
        )
        if session is None:
            raise_not_found("Cafe table session not found.")
        if session.status == TableSessionStatus.OPEN:
            session.status = TableSessionStatus.BILL_REQUESTED
            session.bill_requested_at = now
            session.version += 1
        elif session.status != TableSessionStatus.BILL_REQUESTED:
            raise_conflict("This table session cannot request a bill.")

    db.add(
        CafeOrderStatusHistory(
            company_id=order.company_id,
            branch_id=order.branch_id,
            cafe_order_id=order.id,
            from_status=old,
            to_status=target,
            changed_by=user.id,
            guest_action=False,
            reason=reason,
            created_at=now,
        )
    )
    write_audit_log(
        db,
        action=f"cafe_order_{target.value}",
        entity_type="cafe_order",
        entity_id=order.id,
        user=user,
        company_id=order.company_id,
        old_value_json={"status": old.value, "version": expected_version},
        new_value_json={"status": target.value, "version": order.version},
        request=request,
        notes=reason,
    )
    _sync_status_if_linked(db, order)
    db.commit()
    db.refresh(order)
    return order_to_staff_read(db, order)


def list_kitchen_orders(
    db: Session,
    *,
    scope: ScopeContext,
    branch_id: int | None = None,
    preparation_area: PreparationArea | None = None,
    limit: int = 200,
) -> list[KitchenOrderRead]:
    _check_role(scope, KITCHEN_ROLES)
    company = _require_cafe_company(db, scope)
    statement = select(CafeOrder).where(
        CafeOrder.company_id == company.id,
        CafeOrder.status.in_(
            [CafeOrderStatus.ACCEPTED, CafeOrderStatus.PREPARING, CafeOrderStatus.READY]
        ),
    )
    if scope.branch_ids:
        statement = statement.where(CafeOrder.branch_id.in_(scope.branch_ids))
    if branch_id is not None:
        _resolve_branch(db, scope, branch_id)
        statement = statement.where(CafeOrder.branch_id == branch_id)
    orders = list(
        db.scalars(statement.order_by(CafeOrder.placed_at, CafeOrder.id).limit(limit)).all()
    )
    now = datetime.now(UTC)
    response: list[KitchenOrderRead] = []
    for order in orders:
        session_public_id, table_code = _table_context(db, order)
        del session_public_id
        rows = _order_items(db, order)
        menu_rows = {
            row.id: row
            for row in db.scalars(
                select(MenuItem).where(MenuItem.id.in_({item.menu_item_id for item in rows} or {-1}))
            ).all()
        }
        safe_items: list[KitchenOrderItemRead] = []
        for item in rows:
            menu = menu_rows.get(item.menu_item_id)
            area = menu.preparation_area if menu is not None else PreparationArea.NONE
            if area == PreparationArea.NONE:
                continue
            if preparation_area is not None and area != preparation_area:
                continue
            safe_items.append(
                KitchenOrderItemRead(
                    name=item.menu_item_name_snapshot,
                    quantity=item.quantity,
                    status=item.item_status.value,
                    preparation_area=area,
                    notes=item.preparation_notes,
                )
            )
        if not safe_items:
            continue
        placed = order.placed_at if order.placed_at.tzinfo else order.placed_at.replace(tzinfo=UTC)
        response.append(
            KitchenOrderRead(
                public_id=order.public_id,
                order_number=order.order_number,
                table_reference=table_code,
                source_channel=order.source_channel,
                status=order.status,
                age_seconds=max(0, int((now - placed).total_seconds())),
                version=order.version,
                items=safe_items,
            )
        )
    return response
