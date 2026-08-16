from datetime import date
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import BranchScope, get_branch_scope, get_current_user
from app.db.session import get_db
from app.models import InvoiceStatus, User
from app.schemas.invoices import (
    InvoiceCancelRequest,
    InvoiceCreate,
    InvoiceIssueRequest,
    InvoiceListItemRead,
    InvoicePaymentCreate,
    InvoiceQuoteRead,
    InvoiceRead,
    POSCheckoutRequest,
    POSProductSearchRead,
)
from app.services.invoices import (
    InvoiceFilters,
    add_invoice_payment,
    cancel_invoice,
    create_invoice,
    get_invoice_or_404,
    invoice_to_read,
    issue_invoice,
    list_invoices,
    pos_checkout,
    quote_invoice,
    search_pos_products,
)
from app.services.tax_operation import enforce_invoice_tax_policy

router = APIRouter(tags=["invoices"])


@router.get("/invoices", response_model=list[InvoiceListItemRead])
def read_invoices(
    _user: Annotated[User, Depends(get_current_user)],
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
    db: Annotated[Session, Depends(get_db)],
    branch_id: int | None = None,
    customer_id: int | None = None,
    status_filter: InvoiceStatus | None = Query(default=None, alias="status"),
    start_date: date | None = None,
    end_date: date | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[InvoiceListItemRead]:
    return list_invoices(
        db,
        branch_scope=branch_scope,
        filters=InvoiceFilters(
            branch_id=branch_id,
            customer_id=customer_id,
            status=status_filter,
            start_date=start_date,
            end_date=end_date,
            search=search,
            limit=limit,
        ),
    )


@router.post("/invoices", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def add_invoice(
    payload: InvoiceCreate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InvoiceRead:
    authoritative = cast(InvoiceCreate, enforce_invoice_tax_policy(db, payload=payload))
    return create_invoice(db, payload=authoritative, user=current_user, request=request)


@router.get("/invoices/{invoice_id}", response_model=InvoiceRead)
def read_invoice(
    invoice_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InvoiceRead:
    return invoice_to_read(get_invoice_or_404(db, invoice_id, user=current_user))


@router.post("/invoices/{invoice_id}/issue", response_model=InvoiceRead)
def issue_draft_invoice(
    invoice_id: int,
    payload: InvoiceIssueRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InvoiceRead:
    return issue_invoice(db, invoice_id=invoice_id, payload=payload, user=current_user, request=request)


@router.post("/invoices/{invoice_id}/cancel", response_model=InvoiceRead)
def cancel_draft_invoice(
    invoice_id: int,
    payload: InvoiceCancelRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InvoiceRead:
    return cancel_invoice(db, invoice_id=invoice_id, payload=payload, user=current_user, request=request)


@router.post("/invoices/{invoice_id}/payments", response_model=InvoiceRead)
def collect_invoice_payment(
    invoice_id: int,
    payload: InvoicePaymentCreate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InvoiceRead:
    return add_invoice_payment(db, invoice_id=invoice_id, payload=payload, user=current_user, request=request)


@router.get("/pos/products/search", response_model=list[POSProductSearchRead])
def search_products_for_pos(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    q: str = Query(min_length=1),
    branch_id: int | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> list[POSProductSearchRead]:
    return search_pos_products(db, query=q, user=current_user, branch_id=branch_id, limit=limit)


@router.post("/pos/quote", response_model=InvoiceQuoteRead)
def quote_pos_invoice(
    payload: InvoiceCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InvoiceQuoteRead:
    authoritative = cast(InvoiceCreate, enforce_invoice_tax_policy(db, payload=payload))
    return quote_invoice(db, payload=authoritative, user=current_user)


@router.post("/pos/checkout", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def checkout_pos_invoice(
    payload: POSCheckoutRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InvoiceRead:
    authoritative = cast(POSCheckoutRequest, enforce_invoice_tax_policy(db, payload=payload))
    return pos_checkout(db, payload=authoritative, user=current_user, request=request)
