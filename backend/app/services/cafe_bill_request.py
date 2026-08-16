from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import raise_conflict, raise_forbidden, raise_not_found
from app.core.config import settings
from app.core.scope import ScopeContext
from app.models import (
    BusinessType,
    CafeOrder,
    CafeOrderStatus,
    CafeOrderStatusHistory,
    CloudRecordLink,
    Company,
    TableSession,
    TableSessionStatus,
    User,
    UserRole,
)
from app.schemas.cafe_orders import TableSessionBillRequestRead
from app.services.audit import write_audit_log
from app.sync.cafe_orders import enqueue_cafe_order_status_snapshot

_ALLOWED_ROLES = {UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.ORDER_TAKER}


def _stale() -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "stale_state", "message": "This table session changed. Refresh and try again."},
    )


def request_table_session_bill(
    db: Session,
    *,
    scope: ScopeContext,
    user: User,
    session_public_id: str,
    expected_version: int,
    request: Request | None = None,
) -> TableSessionBillRequestRead:
    if scope.role != UserRole.SUPER_ADMIN and scope.role not in _ALLOWED_ROLES:
        raise_forbidden("This Cafe action is not available to your role.")
    if scope.company_id is None:
        raise_forbidden("Select the Cafe venture before using Cafe operations.")
    company = db.get(Company, scope.company_id)
    if company is None or not company.is_active or company.business_type != BusinessType.CAFE:
        raise_forbidden("Cafe operations are not available in this venture.")

    statement = (
        select(TableSession)
        .where(
            TableSession.public_id == session_public_id,
            TableSession.company_id == company.id,
        )
        .with_for_update()
    )
    if scope.branch_ids:
        statement = statement.where(TableSession.branch_id.in_(scope.branch_ids))
    session = db.scalar(statement)
    if session is None:
        raise_not_found("Cafe table session not found.")
    if session.version != expected_version:
        _stale()
    if session.status == TableSessionStatus.BILL_REQUESTED:
        requested_at = session.bill_requested_at or datetime.now(UTC)
        return TableSessionBillRequestRead(
            public_id=session.public_id,
            status=session.status,
            bill_requested_at=requested_at,
            version=session.version,
            affected_order_public_ids=[],
        )
    if session.status != TableSessionStatus.OPEN:
        raise_conflict("This table session cannot request a bill.")

    orders = list(
        db.scalars(
            select(CafeOrder)
            .where(
                CafeOrder.table_session_id == session.id,
                CafeOrder.company_id == company.id,
                CafeOrder.branch_id == session.branch_id,
            )
            .order_by(CafeOrder.placed_at, CafeOrder.id)
            .with_for_update()
        ).all()
    )
    active = [
        row
        for row in orders
        if row.status not in {CafeOrderStatus.REJECTED, CafeOrderStatus.CANCELLED, CafeOrderStatus.CLOSED}
    ]
    if not active:
        raise_conflict("This table session has no served orders to bill.")
    if any(row.status != CafeOrderStatus.SERVED for row in active):
        raise_conflict("All active orders must be served before requesting the bill.")

    now = datetime.now(UTC)
    affected: list[str] = []
    for order in active:
        old = order.status
        order.status = CafeOrderStatus.BILL_REQUESTED
        order.version += 1
        affected.append(order.public_id)
        db.add(
            CafeOrderStatusHistory(
                company_id=order.company_id,
                branch_id=order.branch_id,
                cafe_order_id=order.id,
                from_status=old,
                to_status=CafeOrderStatus.BILL_REQUESTED,
                changed_by=user.id,
                guest_action=False,
                reason="Table session bill requested",
                created_at=now,
            )
        )
        if settings.sync_device_id:
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
                    status_value=CafeOrderStatus.BILL_REQUESTED.value,
                )

    session.status = TableSessionStatus.BILL_REQUESTED
    session.bill_requested_at = now
    session.version += 1
    write_audit_log(
        db,
        action="cafe_table_session_bill_requested",
        entity_type="table_session",
        entity_id=session.id,
        user=user,
        company_id=company.id,
        old_value_json={"status": TableSessionStatus.OPEN.value, "version": expected_version},
        new_value_json={"status": session.status.value, "version": session.version, "orders": affected},
        request=request,
    )
    db.commit()
    db.refresh(session)
    return TableSessionBillRequestRead(
        public_id=session.public_id,
        status=session.status,
        bill_requested_at=session.bill_requested_at or now,
        version=session.version,
        affected_order_public_ids=affected,
    )
