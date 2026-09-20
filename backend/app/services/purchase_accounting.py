from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import ensure_branch_access
from app.api.errors import raise_bad_request, raise_conflict, raise_forbidden, raise_not_found
from app.models import (
    Product,
    PurchaseBill,
    PurchaseBillItem,
    PurchaseBillStatus,
    PurchaseDebitNote,
    Supplier,
    SupplierLedgerEntry,
    SupplierLedgerEntryType,
    User,
    UserRole,
)
from app.schemas.purchase_accounting import PurchaseBillCreate, PurchaseBillItemRead, PurchaseBillRead, PurchaseDebitNoteCreate, PurchasePaymentCreate, SupplierLedgerEntryRead
from app.services.audit import write_audit_log

MONEY = Decimal("0.01")


def _money(value: Decimal | int | str | None) -> Decimal:
    return Decimal(str(value or "0")).quantize(MONEY, rounding=ROUND_HALF_UP)


def _ensure_write(user: User, branch_id: int) -> None:
    if user.role not in {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.STORE_MANAGER}:
        raise_forbidden("Only an admin or store manager can post purchase accounting records.")
    ensure_branch_access(user, branch_id)


def _bill_read(row: PurchaseBill) -> PurchaseBillRead:
    return PurchaseBillRead(
        id=row.id, company_id=row.company_id, branch_id=row.branch_id, supplier_id=row.supplier_id,
        bill_number=row.bill_number, supplier_invoice_number=row.supplier_invoice_number,
        bill_date=row.bill_date, status=row.status, total_amount=row.total_amount,
        paid_amount=row.paid_amount, balance_due=row.balance_due,
        items=[PurchaseBillItemRead(id=item.id, product_id=item.product_id, quantity=item.quantity, unit_cost=item.unit_cost, line_total=item.line_total) for item in row.items],
    )


def _load_bill(db: Session, bill_id: int, user: User) -> PurchaseBill:
    row = db.scalar(select(PurchaseBill).options(selectinload(PurchaseBill.items)).where(PurchaseBill.id == bill_id))
    if row is None:
        raise_not_found("Purchase bill not found.")
    ensure_branch_access(user, row.branch_id)
    return row


def create_purchase_bill(db: Session, *, user: User, payload: PurchaseBillCreate) -> PurchaseBillRead:
    _ensure_write(user, payload.branch_id)
    existing = db.scalar(select(PurchaseBill).options(selectinload(PurchaseBill.items)).where(PurchaseBill.company_id == user.company_id, PurchaseBill.idempotency_key == payload.idempotency_key))
    if existing is not None:
        return _bill_read(existing)
    supplier = db.get(Supplier, payload.supplier_id)
    if supplier is None or not supplier.is_active:
        raise_not_found("Supplier not found or inactive.")
    rows = []
    seen: set[int] = set()
    total = Decimal("0.00")
    for requested in payload.items:
        if requested.product_id in seen:
            raise_bad_request("Each product can only appear once on a purchase bill.")
        seen.add(requested.product_id)
        product = db.get(Product, requested.product_id)
        if product is None or not product.is_active:
            raise_not_found("One or more products are unavailable.")
        line_total = _money(requested.quantity * requested.unit_cost)
        total += line_total
        rows.append((requested, line_total))
    now = datetime.now(UTC)
    bill = PurchaseBill(
        company_id=user.company_id, branch_id=payload.branch_id, supplier_id=supplier.id,
        bill_number=f"PB-{now:%Y%m%d}-{uuid4().hex[:8].upper()}",
        supplier_invoice_number=payload.supplier_invoice_number, bill_date=payload.bill_date,
        status=PurchaseBillStatus.ISSUED, total_amount=_money(total), paid_amount=Decimal("0.00"),
        balance_due=_money(total), created_by=user.id, idempotency_key=payload.idempotency_key,
    )
    db.add(bill)
    db.flush()
    bill.items = [PurchaseBillItem(bill_id=bill.id, product_id=requested.product_id, quantity=requested.quantity, unit_cost=requested.unit_cost, line_total=line_total) for requested, line_total in rows]
    db.add(SupplierLedgerEntry(company_id=user.company_id, branch_id=payload.branch_id, supplier_id=supplier.id, entry_type=SupplierLedgerEntryType.BILL, debit=_money(total), credit=Decimal("0.00"), reference_type="purchase_bill", reference_id=bill.id, reason=f"Purchase bill {bill.bill_number}", idempotency_key=f"{payload.idempotency_key}:bill", created_by=user.id))
    write_audit_log(db, action="purchase_bill.created", entity_type="purchase_bill", entity_id=bill.id, user=user, new_value_json={"total_amount": str(_money(total)), "supplier_id": supplier.id})
    db.commit(); db.refresh(bill)
    return _bill_read(bill)


def record_purchase_payment(db: Session, *, bill_id: int, user: User, payload: PurchasePaymentCreate) -> PurchaseBillRead:
    bill = _load_bill(db, bill_id, user)
    _ensure_write(user, bill.branch_id)
    if bill.status == PurchaseBillStatus.VOIDED:
        raise_conflict("Voided purchase bills cannot receive payments.")
    existing = db.scalar(select(SupplierLedgerEntry).where(SupplierLedgerEntry.company_id == bill.company_id, SupplierLedgerEntry.idempotency_key == payload.idempotency_key))
    if existing is not None:
        return _bill_read(bill)
    amount = _money(payload.amount)
    if amount > _money(bill.balance_due):
        raise_bad_request("Payment cannot exceed the outstanding supplier balance.")
    bill.paid_amount = _money(bill.paid_amount + amount)
    bill.balance_due = _money(bill.total_amount - bill.paid_amount)
    bill.status = PurchaseBillStatus.PAID if bill.balance_due == 0 else PurchaseBillStatus.PARTIAL_PAID
    db.add(SupplierLedgerEntry(company_id=bill.company_id, branch_id=bill.branch_id, supplier_id=bill.supplier_id, entry_type=SupplierLedgerEntryType.PAYMENT, debit=Decimal("0.00"), credit=amount, reference_type="purchase_bill_payment", reference_id=bill.id, reason=payload.reason, idempotency_key=payload.idempotency_key, created_by=user.id))
    write_audit_log(db, action="purchase_bill.payment", entity_type="purchase_bill", entity_id=bill.id, user=user, new_value_json={"amount": str(amount), "balance_due": str(bill.balance_due)}, notes=payload.reason)
    db.commit(); db.refresh(bill)
    return _bill_read(bill)


def create_purchase_debit_note(db: Session, *, bill_id: int, user: User, payload: PurchaseDebitNoteCreate) -> PurchaseBillRead:
    bill = _load_bill(db, bill_id, user)
    _ensure_write(user, bill.branch_id)
    existing = db.scalar(select(PurchaseDebitNote).where(PurchaseDebitNote.company_id == bill.company_id, PurchaseDebitNote.idempotency_key == payload.idempotency_key))
    if existing is not None:
        return _bill_read(bill)
    amount = _money(payload.amount)
    if amount > _money(bill.balance_due):
        raise_bad_request("Debit note cannot exceed the outstanding supplier balance.")
    now = datetime.now(UTC)
    note = PurchaseDebitNote(company_id=bill.company_id, branch_id=bill.branch_id, supplier_id=bill.supplier_id, bill_id=bill.id, debit_note_number=f"DN-{now:%Y%m%d}-{uuid4().hex[:8].upper()}", amount=amount, reason=payload.reason, idempotency_key=payload.idempotency_key, created_by=user.id)
    db.add(note)
    bill.balance_due = _money(bill.balance_due - amount)
    if bill.balance_due == 0:
        bill.status = PurchaseBillStatus.PAID
    db.add(SupplierLedgerEntry(company_id=bill.company_id, branch_id=bill.branch_id, supplier_id=bill.supplier_id, entry_type=SupplierLedgerEntryType.DEBIT_NOTE, debit=Decimal("0.00"), credit=amount, reference_type="purchase_debit_note", reference_id=None, reason=payload.reason, idempotency_key=f"{payload.idempotency_key}:ledger", created_by=user.id))
    write_audit_log(db, action="purchase_debit_note.created", entity_type="purchase_debit_note", entity_id=None, user=user, new_value_json={"bill_id": bill.id, "amount": str(amount)}, notes=payload.reason)
    db.commit(); db.refresh(bill)
    return _bill_read(bill)


def supplier_ledger(db: Session, *, supplier_id: int, user: User) -> list[SupplierLedgerEntryRead]:
    rows = db.scalars(select(SupplierLedgerEntry).where(SupplierLedgerEntry.supplier_id == supplier_id).order_by(SupplierLedgerEntry.entry_datetime.desc(), SupplierLedgerEntry.id.desc())).all()
    return [SupplierLedgerEntryRead(id=row.id, supplier_id=row.supplier_id, entry_type=row.entry_type, debit=row.debit, credit=row.credit, reference_type=row.reference_type, reference_id=row.reference_id, reason=row.reason, entry_datetime=row.entry_datetime) for row in rows]
