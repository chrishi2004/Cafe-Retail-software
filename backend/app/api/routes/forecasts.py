from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import BranchScope, get_branch_scope, require_reporting_access
from app.db.session import get_db
from app.models import ForecastType, User
from app.schemas.forecasts import ForecastRead, ForecastRunCreate, ForecastRunRead
from app.services.forecasting import (
    ForecastFilters,
    query_forecasts,
    query_product_forecasts,
    run_forecast,
)

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


@router.post("/run", response_model=ForecastRunRead)
def run_forecast_route(
    payload: ForecastRunCreate,
    _user: Annotated[User, Depends(require_reporting_access)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> ForecastRunRead:
    return run_forecast(db, payload=payload, branch_scope=branch_scope)


@router.get("", response_model=list[ForecastRead])
def list_forecasts(
    _user: Annotated[User, Depends(require_reporting_access)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    forecast_type: ForecastType | None = None,
    branch_id: int | None = None,
    category_id: int | None = None,
    product_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ForecastRead]:
    return query_forecasts(
        db,
        branch_scope=branch_scope,
        filters=ForecastFilters(
            forecast_type=forecast_type,
            branch_id=branch_id,
            category_id=category_id,
            product_id=product_id,
            limit=limit,
        ),
    )


@router.get("/products/{product_id}", response_model=list[ForecastRead])
def list_product_forecasts(
    product_id: int,
    _user: Annotated[User, Depends(require_reporting_access)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    branch_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ForecastRead]:
    return query_product_forecasts(
        db,
        product_id=product_id,
        branch_scope=branch_scope,
        branch_id=branch_id,
        limit=limit,
    )
