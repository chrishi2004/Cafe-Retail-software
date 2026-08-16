from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import BranchScope, get_branch_scope, get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.sales import (
    SaleCreate,
    SaleListItemRead,
    SaleRead,
    SalesSummaryRead,
    SalesTrendPoint,
)
from app.services.sales import (
    SalesFilters,
    create_sale,
    get_sale_detail,
    query_sales,
    query_sales_summary,
    query_sales_trends,
)

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("", response_model=list[SaleListItemRead])
def list_sales(
    _user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    branch_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    product_id: int | None = None,
    category_id: int | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[SaleListItemRead]:
    return query_sales(
        db,
        branch_scope=branch_scope,
        filters=SalesFilters(
            branch_id=branch_id,
            start_date=start_date,
            end_date=end_date,
            product_id=product_id,
            category_id=category_id,
            search=search,
            limit=limit,
        ),
    )


@router.post("", response_model=SaleRead)
def record_sale(
    payload: SaleCreate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SaleRead:
    return create_sale(db, payload=payload, user=current_user, request=request)


@router.get("/summary", response_model=SalesSummaryRead)
def get_sales_summary(
    _user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    branch_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    product_id: int | None = None,
    category_id: int | None = None,
) -> SalesSummaryRead:
    return query_sales_summary(
        db,
        branch_scope=branch_scope,
        filters=SalesFilters(
            branch_id=branch_id,
            start_date=start_date,
            end_date=end_date,
            product_id=product_id,
            category_id=category_id,
        ),
    )


@router.get("/trends", response_model=list[SalesTrendPoint])
def get_sales_trends(
    _user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    branch_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    product_id: int | None = None,
    category_id: int | None = None,
) -> list[SalesTrendPoint]:
    return query_sales_trends(
        db,
        branch_scope=branch_scope,
        filters=SalesFilters(
            branch_id=branch_id,
            start_date=start_date,
            end_date=end_date,
            product_id=product_id,
            category_id=category_id,
        ),
    )


@router.get("/{sale_id}", response_model=SaleRead)
def get_sale(
    sale_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SaleRead:
    return get_sale_detail(db, sale_id=sale_id, user=current_user)
