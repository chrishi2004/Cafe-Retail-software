from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_scope_context
from app.api.errors import raise_bad_request
from app.core.scope import ScopeContext
from app.db.session import get_db
from app.models import CafeOrderSource, CafeOrderStatus, PreparationArea, User
from app.schemas.cafe_orders import (
    KitchenOrderRead,
    OrderReasonInput,
    OrderVersionInput,
    StaffOrderCreate,
    StaffOrderRead,
    TableSessionBillRequestInput,
    TableSessionBillRequestRead,
)
from app.services.cafe_bill_request import request_table_session_bill
from app.services.cafe_staff_orders import (
    create_staff_order,
    get_staff_order,
    list_kitchen_orders,
    list_staff_orders,
    transition_order,
)

router = APIRouter(prefix="/cafe", tags=["cafe-orders"])
Database = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentScope = Annotated[ScopeContext, Depends(get_scope_context)]


@router.get("/orders", response_model=list[StaffOrderRead])
def read_orders(
    _user: CurrentUser,
    scope: CurrentScope,
    db: Database,
    branch_id: int | None = None,
    table_id: int | None = None,
    status_filter: CafeOrderStatus | None = Query(default=None, alias="status"),
    source: CafeOrderSource | None = None,
    preparation_area: PreparationArea | None = None,
    business_date: date | None = None,
    unbilled_only: bool = False,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[StaffOrderRead]:
    return list_staff_orders(
        db,
        scope=scope,
        branch_id=branch_id,
        table_id=table_id,
        status_filter=status_filter,
        source=source,
        preparation_area=preparation_area,
        business_date=business_date,
        unbilled_only=unbilled_only,
        limit=limit,
    )


@router.post("/orders", response_model=StaffOrderRead, status_code=status.HTTP_201_CREATED)
def add_order(
    payload: StaffOrderCreate,
    request: Request,
    user: CurrentUser,
    scope: CurrentScope,
    db: Database,
) -> StaffOrderRead:
    return create_staff_order(db, scope=scope, user=user, payload=payload, request=request)


@router.get("/orders/{public_id}", response_model=StaffOrderRead)
def read_order(
    public_id: str,
    _user: CurrentUser,
    scope: CurrentScope,
    db: Database,
) -> StaffOrderRead:
    return get_staff_order(db, scope=scope, public_id=public_id)


@router.post("/orders/{public_id}/accept", response_model=StaffOrderRead)
def accept_order(public_id: str, payload: OrderVersionInput, request: Request, user: CurrentUser, scope: CurrentScope, db: Database) -> StaffOrderRead:
    return transition_order(db, scope=scope, user=user, public_id=public_id, expected_version=payload.expected_version, target=CafeOrderStatus.ACCEPTED, request=request)


@router.post("/orders/{public_id}/reject", response_model=StaffOrderRead)
def reject_order(public_id: str, payload: OrderReasonInput, request: Request, user: CurrentUser, scope: CurrentScope, db: Database) -> StaffOrderRead:
    return transition_order(db, scope=scope, user=user, public_id=public_id, expected_version=payload.expected_version, target=CafeOrderStatus.REJECTED, reason=payload.reason, request=request)


@router.post("/orders/{public_id}/start-preparing", response_model=StaffOrderRead)
def start_preparing(public_id: str, payload: OrderVersionInput, request: Request, user: CurrentUser, scope: CurrentScope, db: Database) -> StaffOrderRead:
    return transition_order(db, scope=scope, user=user, public_id=public_id, expected_version=payload.expected_version, target=CafeOrderStatus.PREPARING, request=request)


@router.post("/orders/{public_id}/mark-ready", response_model=StaffOrderRead)
def mark_ready(public_id: str, payload: OrderVersionInput, request: Request, user: CurrentUser, scope: CurrentScope, db: Database) -> StaffOrderRead:
    return transition_order(db, scope=scope, user=user, public_id=public_id, expected_version=payload.expected_version, target=CafeOrderStatus.READY, request=request)


@router.post("/orders/{public_id}/serve", response_model=StaffOrderRead)
def serve_order(public_id: str, payload: OrderVersionInput, request: Request, user: CurrentUser, scope: CurrentScope, db: Database) -> StaffOrderRead:
    return transition_order(db, scope=scope, user=user, public_id=public_id, expected_version=payload.expected_version, target=CafeOrderStatus.SERVED, request=request)


@router.post("/orders/{public_id}/request-bill", response_model=StaffOrderRead)
def request_standalone_order_bill(public_id: str, payload: OrderVersionInput, request: Request, user: CurrentUser, scope: CurrentScope, db: Database) -> StaffOrderRead:
    current = get_staff_order(db, scope=scope, public_id=public_id)
    if current.table_session_public_id is not None:
        raise_bad_request("Dine-in billing intent must be requested for the table session.")
    return transition_order(db, scope=scope, user=user, public_id=public_id, expected_version=payload.expected_version, target=CafeOrderStatus.BILL_REQUESTED, request=request)


@router.post("/orders/{public_id}/cancel", response_model=StaffOrderRead)
def cancel_order(public_id: str, payload: OrderReasonInput, request: Request, user: CurrentUser, scope: CurrentScope, db: Database) -> StaffOrderRead:
    return transition_order(db, scope=scope, user=user, public_id=public_id, expected_version=payload.expected_version, target=CafeOrderStatus.CANCELLED, reason=payload.reason, request=request)


@router.post("/table-sessions/{public_id}/request-bill", response_model=TableSessionBillRequestRead)
def request_session_bill(
    public_id: str,
    payload: TableSessionBillRequestInput,
    request: Request,
    user: CurrentUser,
    scope: CurrentScope,
    db: Database,
) -> TableSessionBillRequestRead:
    return request_table_session_bill(
        db,
        scope=scope,
        user=user,
        session_public_id=public_id,
        expected_version=payload.expected_version,
        request=request,
    )


@router.get("/kitchen/orders", response_model=list[KitchenOrderRead])
def read_kitchen_queue(
    _user: CurrentUser,
    scope: CurrentScope,
    db: Database,
    branch_id: int | None = None,
    preparation_area: PreparationArea | None = None,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[KitchenOrderRead]:
    return list_kitchen_orders(db, scope=scope, branch_id=branch_id, preparation_area=preparation_area, limit=limit)
