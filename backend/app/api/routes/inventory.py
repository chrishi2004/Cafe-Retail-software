from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import BranchScope, get_branch_scope, get_current_user
from app.db.session import get_db
from app.models import StockMovementType, User
from app.schemas.inventory import (
    InventoryRead,
    ProductInventoryDetail,
    StockAdjustmentCreate,
    StockAdjustmentResponse,
    StockMovementRead,
)
from app.schemas.reorder import ReorderPriority, ReorderRecommendationRead
from app.services.inventory import (
    InventoryFilters,
    MovementFilters,
    apply_stock_adjustment,
    get_product_inventory_detail,
    query_inventory,
    query_low_stock,
    query_movements,
)
from app.services.reorder import ReorderFilters, query_reorder_recommendations

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("", response_model=list[InventoryRead])
def list_inventory(
    _user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    branch_id: int | None = None,
    category_id: int | None = None,
    supplier_id: int | None = None,
    search: str | None = None,
    low_stock: bool | None = None,
) -> list[InventoryRead]:
    return query_inventory(
        db,
        branch_scope=branch_scope,
        filters=InventoryFilters(
            branch_id=branch_id,
            category_id=category_id,
            supplier_id=supplier_id,
            search=search,
            low_stock=low_stock,
        ),
    )


@router.get("/low-stock", response_model=list[InventoryRead])
def list_low_stock_inventory(
    _user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    branch_id: int | None = None,
    category_id: int | None = None,
    supplier_id: int | None = None,
    search: str | None = None,
) -> list[InventoryRead]:
    return query_low_stock(
        db,
        branch_scope=branch_scope,
        filters=InventoryFilters(
            branch_id=branch_id,
            category_id=category_id,
            supplier_id=supplier_id,
            search=search,
        ),
    )


@router.post("/adjustments", response_model=StockAdjustmentResponse)
def create_stock_adjustment(
    payload: StockAdjustmentCreate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> StockAdjustmentResponse:
    return apply_stock_adjustment(
        db,
        payload=payload,
        user=current_user,
        request=request,
    )


@router.get("/movements", response_model=list[StockMovementRead])
def list_stock_movements(
    _user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    product_id: int | None = None,
    branch_id: int | None = None,
    movement_type: StockMovementType | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[StockMovementRead]:
    return query_movements(
        db,
        branch_scope=branch_scope,
        filters=MovementFilters(
            product_id=product_id,
            branch_id=branch_id,
            movement_type=movement_type,
            limit=limit,
        ),
    )


@router.get("/reorder-recommendations", response_model=list[ReorderRecommendationRead])
def list_reorder_recommendations(
    _user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    branch_id: int | None = None,
    category_id: int | None = None,
    supplier_id: int | None = None,
    priority: ReorderPriority | None = None,
    lookback_days: int = Query(default=30, ge=1, le=365),
    as_of_date: date | None = None,
) -> list[ReorderRecommendationRead]:
    return query_reorder_recommendations(
        db,
        branch_scope=branch_scope,
        filters=ReorderFilters(
            branch_id=branch_id,
            category_id=category_id,
            supplier_id=supplier_id,
            priority=priority,
            lookback_days=lookback_days,
            as_of_date=as_of_date,
        ),
    )


@router.get("/{product_id}", response_model=ProductInventoryDetail)
def get_product_inventory(
    product_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> ProductInventoryDetail:
    return get_product_inventory_detail(
        db,
        product_id=product_id,
        branch_scope=branch_scope,
    )
