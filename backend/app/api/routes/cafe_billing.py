from __future__ import annotations

from typing import Annotated
from datetime import date

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_scope_context
from app.core.scope import ScopeContext
from app.db.session import get_db
from app.models import User
from app.schemas.cafe_billing import (
    CafeBillQuoteRead,
    CafeBillRequest,
    CafeBillResultRead,
    CafePaymentCollectRequest,
    CafeReceiptRead,
    CafeInvoiceHistoryRead,
)
from app.services.cafe_billing import (
    bill_standalone_order,
    bill_table_session,
    collect_invoice_payment,
    quote_standalone_order,
    quote_table_session,
    receipt_for_invoice,
    list_cafe_invoice_history,
)

router = APIRouter(prefix="/cafe/billing", tags=["cafe-billing"])
Database = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentScope = Annotated[ScopeContext, Depends(get_scope_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]


@router.get("/table-sessions/{public_id}/quote", response_model=CafeBillQuoteRead)
def read_table_quote(
    public_id: str,
    _user: CurrentUser,
    scope: CurrentScope,
    db: Database,
) -> CafeBillQuoteRead:
    return quote_table_session(db, scope=scope, session_public_id=public_id)


@router.post("/table-sessions/{public_id}/bill", response_model=CafeBillResultRead)
def create_table_bill(
    public_id: str,
    payload: CafeBillRequest,
    idempotency_key: IdempotencyKey,
    request: Request,
    user: CurrentUser,
    scope: CurrentScope,
    db: Database,
) -> CafeBillResultRead:
    return bill_table_session(
        db,
        scope=scope,
        user=user,
        session_public_id=public_id,
        payload=payload,
        idempotency_key=idempotency_key,
        request=request,
    )


@router.get("/orders/{public_id}/quote", response_model=CafeBillQuoteRead)
def read_order_quote(
    public_id: str,
    _user: CurrentUser,
    scope: CurrentScope,
    db: Database,
) -> CafeBillQuoteRead:
    return quote_standalone_order(db, scope=scope, order_public_id=public_id)


@router.post("/orders/{public_id}/bill", response_model=CafeBillResultRead)
def create_order_bill(
    public_id: str,
    payload: CafeBillRequest,
    idempotency_key: IdempotencyKey,
    request: Request,
    user: CurrentUser,
    scope: CurrentScope,
    db: Database,
) -> CafeBillResultRead:
    return bill_standalone_order(
        db,
        scope=scope,
        user=user,
        order_public_id=public_id,
        payload=payload,
        idempotency_key=idempotency_key,
        request=request,
    )


@router.get("/invoices/{invoice_id}/receipt", response_model=CafeReceiptRead)
def read_receipt(
    invoice_id: int,
    _user: CurrentUser,
    scope: CurrentScope,
    db: Database,
) -> CafeReceiptRead:
    return receipt_for_invoice(db, scope=scope, invoice_id=invoice_id)


@router.post("/invoices/{invoice_id}/payments", response_model=CafeBillResultRead)
def collect_payment(
    invoice_id: int,
    payload: CafePaymentCollectRequest,
    request: Request,
    user: CurrentUser,
    scope: CurrentScope,
    db: Database,
) -> CafeBillResultRead:
    return collect_invoice_payment(
        db,
        scope=scope,
        user=user,
        invoice_id=invoice_id,
        payload=payload,
        request=request,
    )


from app.schemas.cafe_pos import CafeCheckoutRequest
from app.services.cafe_pos import checkout


@router.post('/pos/checkout', response_model=CafeBillResultRead)
def checkout_pos(
    payload: CafeCheckoutRequest,
    idempotency_key: IdempotencyKey,
    request: Request,
    user: CurrentUser,
    scope: CurrentScope,
    db: Database,
) -> CafeBillResultRead:
    return checkout(db, scope=scope, user=user, payload=payload,
                    idempotency_key=idempotency_key, request=request)


@router.get('/invoices', response_model=CafeInvoiceHistoryRead)
def read_invoice_history(
    _user: CurrentUser,
    scope: CurrentScope,
    db: Database,
    search: str | None = Query(default=None, max_length=100),
    branch_id: int | None = Query(default=None, ge=1),
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CafeInvoiceHistoryRead:
    return list_cafe_invoice_history(db, scope=scope, search=search, branch_id=branch_id,
        start_date=start_date, end_date=end_date, limit=limit, offset=offset)
