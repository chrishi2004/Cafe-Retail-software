from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import BranchScope, get_branch_scope, get_scope_context, require_reporting_access
from app.db.session import get_db
from app.models import ForecastType, PurchaseOrderStatus, User
from app.core.scope import ScopeContext
from app.schemas.p9 import P9DashboardFilters
from app.services.p9_reporting import export_cafe_csv, export_consolidated_csv
from app.services.exports import (
    export_forecasts_csv,
    export_inventory_csv,
    export_purchase_orders_csv,
    export_sales_csv,
)

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/sales", response_class=Response)
def export_sales(
    _user: Annotated[User, Depends(require_reporting_access)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    branch_id: int | None = None,
    category_id: int | None = None,
    product_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Response:
    return export_sales_csv(
        db,
        branch_scope=branch_scope,
        branch_id=branch_id,
        category_id=category_id,
        product_id=product_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/inventory", response_class=Response)
def export_inventory(
    _user: Annotated[User, Depends(require_reporting_access)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    branch_id: int | None = None,
    category_id: int | None = None,
    supplier_id: int | None = None,
    low_stock: bool | None = None,
) -> Response:
    return export_inventory_csv(
        db,
        branch_scope=branch_scope,
        branch_id=branch_id,
        category_id=category_id,
        supplier_id=supplier_id,
        low_stock=low_stock,
    )


@router.get("/purchase-orders", response_class=Response)
def export_purchase_orders(
    _user: Annotated[User, Depends(require_reporting_access)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    branch_id: int | None = None,
    supplier_id: int | None = None,
    status: PurchaseOrderStatus | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Response:
    return export_purchase_orders_csv(
        db,
        branch_scope=branch_scope,
        branch_id=branch_id,
        supplier_id=supplier_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/forecasts", response_class=Response)
def export_forecasts(
    _user: Annotated[User, Depends(require_reporting_access)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    forecast_type: ForecastType | None = None,
    branch_id: int | None = None,
    category_id: int | None = None,
    product_id: int | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
) -> Response:
    return export_forecasts_csv(
        db,
        branch_scope=branch_scope,
        forecast_type=forecast_type,
        branch_id=branch_id,
        category_id=category_id,
        product_id=product_id,
        limit=limit,
    )


def p9_export_filters(
    branch_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    source_channel: str | None = None,
    status: str | None = None,
    payment_mode: str | None = None,
) -> P9DashboardFilters:
    return P9DashboardFilters(
        branch_id=branch_id,
        start_date=start_date,
        end_date=end_date,
        source_channel=source_channel,
        status=status,
        payment_mode=payment_mode,
    )


@router.get("/cafe", response_class=Response)
def export_cafe(
    _user: Annotated[User, Depends(require_reporting_access)],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
    filters: Annotated[P9DashboardFilters, Depends(p9_export_filters)],
) -> Response:
    return Response(
        content=export_cafe_csv(db, scope=scope, filters=filters),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cafe-report.csv"},
    )


@router.get("/consolidated", response_class=Response)
def export_consolidated(
    _user: Annotated[User, Depends(require_reporting_access)],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
    filters: Annotated[P9DashboardFilters, Depends(p9_export_filters)],
) -> Response:
    return Response(
        content=export_consolidated_csv(db, scope=scope, filters=filters),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=consolidated-report.csv"},
    )
