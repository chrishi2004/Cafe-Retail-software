from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import BranchScope, get_branch_scope, get_current_user
from app.db.session import get_db
from app.models import PurchaseOrderStatus, User
from app.schemas.purchase_orders import (
    PurchaseOrderCreate,
    PurchaseOrderDraftRead,
    PurchaseOrderListItemRead,
    PurchaseOrderRead,
    PurchaseOrderReceive,
    PurchaseOrderUpdate,
    PurchaseOrdersFromRecommendationsCreate,
)
from app.services.purchase_orders import (
    PurchaseOrderFilters,
    approve_purchase_order,
    cancel_purchase_order,
    create_purchase_order,
    create_purchase_orders_from_recommendations,
    get_purchase_order_detail,
    mark_purchase_order_ordered,
    query_purchase_orders,
    receive_purchase_order,
    submit_purchase_order,
    update_purchase_order,
)

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


@router.get("", response_model=list[PurchaseOrderListItemRead])
def list_purchase_orders(
    _user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    branch_id: int | None = None,
    supplier_id: int | None = None,
    status: PurchaseOrderStatus | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[PurchaseOrderListItemRead]:
    return query_purchase_orders(
        db,
        branch_scope=branch_scope,
        filters=PurchaseOrderFilters(
            branch_id=branch_id,
            supplier_id=supplier_id,
            status=status,
            search=search,
            limit=limit,
        ),
    )


@router.post("", response_model=PurchaseOrderRead)
def create_manual_purchase_order(
    payload: PurchaseOrderCreate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrderRead:
    return create_purchase_order(db, payload=payload, user=current_user, request=request)


@router.post("/from-recommendations", response_model=list[PurchaseOrderDraftRead])
def create_from_recommendations(
    payload: PurchaseOrdersFromRecommendationsCreate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[PurchaseOrderDraftRead]:
    return create_purchase_orders_from_recommendations(
        db,
        payload=payload,
        user=current_user,
        request=request,
    )


@router.get("/{purchase_order_id}", response_model=PurchaseOrderRead)
def get_purchase_order(
    purchase_order_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrderRead:
    return get_purchase_order_detail(db, purchase_order_id=purchase_order_id, user=current_user)


@router.put("/{purchase_order_id}", response_model=PurchaseOrderRead)
def update_purchase_order_route(
    purchase_order_id: int,
    payload: PurchaseOrderUpdate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrderRead:
    return update_purchase_order(
        db,
        purchase_order_id=purchase_order_id,
        payload=payload,
        user=current_user,
        request=request,
    )


@router.post("/{purchase_order_id}/submit", response_model=PurchaseOrderRead)
def submit_purchase_order_route(
    purchase_order_id: int,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrderRead:
    return submit_purchase_order(db, purchase_order_id=purchase_order_id, user=current_user, request=request)


@router.post("/{purchase_order_id}/approve", response_model=PurchaseOrderRead)
def approve_purchase_order_route(
    purchase_order_id: int,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrderRead:
    return approve_purchase_order(db, purchase_order_id=purchase_order_id, user=current_user, request=request)


@router.post("/{purchase_order_id}/cancel", response_model=PurchaseOrderRead)
def cancel_purchase_order_route(
    purchase_order_id: int,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrderRead:
    return cancel_purchase_order(db, purchase_order_id=purchase_order_id, user=current_user, request=request)


@router.post("/{purchase_order_id}/mark-ordered", response_model=PurchaseOrderRead)
def mark_purchase_order_ordered_route(
    purchase_order_id: int,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrderRead:
    return mark_purchase_order_ordered(db, purchase_order_id=purchase_order_id, user=current_user, request=request)


@router.post("/{purchase_order_id}/receive", response_model=PurchaseOrderRead)
def receive_purchase_order_route(
    purchase_order_id: int,
    payload: PurchaseOrderReceive,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrderRead:
    return receive_purchase_order(
        db,
        purchase_order_id=purchase_order_id,
        payload=payload,
        user=current_user,
        request=request,
    )
