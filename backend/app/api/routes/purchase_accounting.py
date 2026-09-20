from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.purchase_accounting import PurchaseBillCreate, PurchaseBillRead, PurchaseDebitNoteCreate, PurchasePaymentCreate, SupplierLedgerEntryRead
from app.services.purchase_accounting import create_purchase_bill, create_purchase_debit_note, record_purchase_payment, supplier_ledger

router = APIRouter(prefix="/purchase-bills", tags=["purchase-accounting"])
WRITE_ROLES = (UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.STORE_MANAGER)


@router.post("", response_model=PurchaseBillRead, status_code=status.HTTP_201_CREATED)
def create_bill(payload: PurchaseBillCreate, user: Annotated[User, Depends(require_roles(*WRITE_ROLES))], db: Annotated[Session, Depends(get_db)]) -> PurchaseBillRead:
    return create_purchase_bill(db, user=user, payload=payload)


@router.post("/{bill_id}/payments", response_model=PurchaseBillRead)
def pay_bill(bill_id: int, payload: PurchasePaymentCreate, user: Annotated[User, Depends(require_roles(*WRITE_ROLES))], db: Annotated[Session, Depends(get_db)]) -> PurchaseBillRead:
    return record_purchase_payment(db, bill_id=bill_id, user=user, payload=payload)


@router.post("/{bill_id}/debit-notes", response_model=PurchaseBillRead)
def debit_bill(bill_id: int, payload: PurchaseDebitNoteCreate, user: Annotated[User, Depends(require_roles(*WRITE_ROLES))], db: Annotated[Session, Depends(get_db)]) -> PurchaseBillRead:
    return create_purchase_debit_note(db, bill_id=bill_id, user=user, payload=payload)


@router.get("/suppliers/{supplier_id}/ledger", response_model=list[SupplierLedgerEntryRead])
def read_supplier_ledger(supplier_id: int, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> list[SupplierLedgerEntryRead]:
    return supplier_ledger(db, supplier_id=supplier_id, user=user)
