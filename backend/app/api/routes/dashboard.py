from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import BranchScope, get_branch_scope, get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.dashboard import (
    InventoryDashboardRead,
    OverviewDashboardRead,
    PurchaseOrdersDashboardRead,
    SalesDashboardRead,
)
from app.services.dashboard import (
    DashboardFilters,
    get_inventory_dashboard,
    get_overview_dashboard,
    get_purchase_orders_dashboard,
    get_sales_dashboard,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def dashboard_filters(
    branch_id: int | None = None,
    category_id: int | None = None,
    product_id: int | None = None,
    supplier_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> DashboardFilters:
    return DashboardFilters(
        branch_id=branch_id,
        category_id=category_id,
        product_id=product_id,
        supplier_id=supplier_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/overview", response_model=OverviewDashboardRead)
def overview_dashboard(
    _user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    filters: Annotated[DashboardFilters, Depends(dashboard_filters)],
) -> OverviewDashboardRead:
    return get_overview_dashboard(db, branch_scope=branch_scope, filters=filters)


@router.get("/sales", response_model=SalesDashboardRead)
def sales_dashboard(
    _user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    filters: Annotated[DashboardFilters, Depends(dashboard_filters)],
) -> SalesDashboardRead:
    return get_sales_dashboard(db, branch_scope=branch_scope, filters=filters)


@router.get("/inventory", response_model=InventoryDashboardRead)
def inventory_dashboard(
    _user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    filters: Annotated[DashboardFilters, Depends(dashboard_filters)],
) -> InventoryDashboardRead:
    return get_inventory_dashboard(db, branch_scope=branch_scope, filters=filters)


@router.get("/purchase-orders", response_model=PurchaseOrdersDashboardRead)
def purchase_orders_dashboard(
    _user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    filters: Annotated[DashboardFilters, Depends(dashboard_filters)],
) -> PurchaseOrdersDashboardRead:
    return get_purchase_orders_dashboard(db, branch_scope=branch_scope, filters=filters)
