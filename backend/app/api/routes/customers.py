from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import BranchScope, get_branch_scope, get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.customers import (
    CustomerCreate,
    CustomerLedgerEntryRead,
    CustomerOutstandingRead,
    CustomerPaymentCreate,
    CustomerPaymentRead,
    CustomerRead,
    CustomerUpdate,
)
from app.services.customers import (
    create_customer,
    deactivate_customer,
    get_customer_ledger,
    get_customer_or_404,
    customer_to_read,
    list_customer_outstanding,
    list_customers,
    record_customer_payment,
    update_customer,
)

router = APIRouter(tags=["customers"])


@router.get("/customers", response_model=list[CustomerRead])
def read_customers(
    _user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    branch_id: int | None = None,
    include_inactive: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[CustomerRead]:
    return list_customers(
        db,
        branch_scope=branch_scope,
        search=search,
        branch_id=branch_id,
        include_inactive=include_inactive,
        limit=limit,
    )


@router.post("/customers", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def add_customer(
    payload: CustomerCreate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CustomerRead:
    return create_customer(db, payload=payload, user=current_user, request=request)


@router.get("/customers/{customer_id}", response_model=CustomerRead)
def read_customer(
    customer_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CustomerRead:
    return customer_to_read(db, get_customer_or_404(db, customer_id, user=current_user))


@router.put("/customers/{customer_id}", response_model=CustomerRead)
def edit_customer(
    customer_id: int,
    payload: CustomerUpdate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CustomerRead:
    return update_customer(db, customer_id=customer_id, payload=payload, user=current_user, request=request)


@router.patch("/customers/{customer_id}/deactivate", response_model=CustomerRead)
def disable_customer(
    customer_id: int,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CustomerRead:
    return deactivate_customer(db, customer_id=customer_id, user=current_user, request=request)


@router.get("/customers/{customer_id}/ledger", response_model=list[CustomerLedgerEntryRead])
def read_customer_ledger(
    customer_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[CustomerLedgerEntryRead]:
    return get_customer_ledger(db, customer_id=customer_id, user=current_user)


@router.post("/customers/{customer_id}/payments", response_model=CustomerPaymentRead, status_code=status.HTTP_201_CREATED)
def add_customer_payment(
    customer_id: int,
    payload: CustomerPaymentCreate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CustomerPaymentRead:
    return record_customer_payment(db, customer_id=customer_id, payload=payload, user=current_user, request=request)


@router.get("/customer-ledger/outstanding", response_model=list[CustomerOutstandingRead])
def read_customer_outstanding(
    _user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    branch_id: int | None = None,
    include_zero: bool = Query(default=False),
) -> list[CustomerOutstandingRead]:
    return list_customer_outstanding(
        db,
        branch_scope=branch_scope,
        branch_id=branch_id,
        include_zero=include_zero,
    )
