from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import BranchScope, get_branch_scope, get_current_user, get_scope_context, require_reporting_access
from app.db.session import get_db
from app.models import User
from app.core.scope import ScopeContext
from app.schemas.p9 import P9ConsolidatedRead, P9DashboardFilters, P9DashboardRead
from app.services.p9_reporting import get_cafe_dashboard, get_consolidated_dashboard
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


def p9_filters(
    branch_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    source_channel: str | None = None,
    status: str | None = None,
    payment_mode: str | None = None,
    menu_category_id: int | None = None,
    menu_item_id: int | None = None,
    table_id: int | None = None,
) -> P9DashboardFilters:
    return P9DashboardFilters(
        branch_id=branch_id,
        start_date=start_date,
        end_date=end_date,
        source_channel=source_channel,
        status=status,
        payment_mode=payment_mode,
        menu_category_id=menu_category_id,
        menu_item_id=menu_item_id,
        table_id=table_id,
    )


@router.get("/cafe", response_model=P9DashboardRead)
def cafe_dashboard(
    _user: Annotated[User, Depends(require_reporting_access)],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
    filters: Annotated[P9DashboardFilters, Depends(p9_filters)],
) -> P9DashboardRead:
    return get_cafe_dashboard(db, scope=scope, filters=filters)


@router.get("/consolidated", response_model=P9ConsolidatedRead)
def consolidated_dashboard(
    _user: Annotated[User, Depends(require_reporting_access)],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
    filters: Annotated[P9DashboardFilters, Depends(p9_filters)],
) -> P9ConsolidatedRead:
    return get_consolidated_dashboard(db, scope=scope, filters=filters)
