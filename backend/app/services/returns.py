from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import ensure_branch_access
from app.api.errors import raise_bad_request, raise_conflict, raise_not_found
from app.core.scope import ScopeContext
from app.models import (
    CreditNote,
    CreditNoteStatus,
    CustomerLedgerEntryType,
    FinancialReversal,
    Inventory,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    InvoiceStatusHistory,
    ProductItemType,
    ReversalType,
    ReturnCondition,
    RefundMode,
    SalesReturn,
    SalesReturnItem,
    SalesReturnStatus,
    StockMovement,
    StockMovementType,
    User,
)
from app.schemas.returns import CreditNoteRead, ReturnItemRead, SalesReturnCreate, SalesReturnRead
from app.services.audit import write_audit_log
from app.services.customers import add_customer_ledger_entry

MONEY = Decimal("0.01")
QUANTITY = Decimal("0.01")


def _money(value: Decimal | int | str | None) -> Decimal:
    return Decimal(str(value or "0")).quantize(MONEY, rounding=ROUND_HALF_UP)


def _quantity(value: Decimal | int | str) -> Decimal:
    return Decimal(str(value)).quantize(QUANTITY, rounding=ROUND_HALF_UP)


def _read(row: SalesReturn) -> SalesReturnRead:
    note = row.credit_note
    return SalesReturnRead(
        id=row.id,
        company_id=row.company_id,
        branch_id=row.branch_id,
        invoice_id=row.invoice_id,
        customer_id=row.customer_id,
        return_number=row.return_number,
        status=row.status,
        refund_mode=row.refund_mode,
        reason=row.reason,
        total_amount=row.total_amount,
        returned_at=row.returned_at,
        items=[
            ReturnItemRead(
                id=item.id,
                invoice_item_id=item.invoice_item_id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                taxable_value=item.taxable_value,
                tax_total=item.tax_total,
                line_total=item.line_total,
                condition=item.condition,
                restocked=item.restocked,
            )
            for item in sorted(row.items, key=lambda value: value.id)
        ],
        credit_note=CreditNoteRead(
            id=note.id,
            credit_note_number=note.credit_note_number,
            status=note.status,
            amount=note.amount,
            refund_mode=note.refund_mode,
            reason=note.reason,
            issued_at=note.issued_at,
        ),
    )


def _returned_quantity(db: Session, *, invoice_item_id: int) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(SalesReturnItem.quantity), 0))
        .join(SalesReturn, SalesReturn.id == SalesReturnItem.return_id)
        .where(
            SalesReturnItem.invoice_item_id == invoice_item_id,
            SalesReturn.status == SalesReturnStatus.ISSUED,
        )
    )
    return _quantity(value)


def create_sales_return(
    db: Session,
    *,
    scope: ScopeContext,
    user: User,
    invoice_id: int,
    payload: SalesReturnCreate,
) -> SalesReturnRead:
    invoice = db.scalar(
        select(Invoice)
        .options(selectinload(Invoice.items), joinedload(Invoice.customer))
        .where(Invoice.id == invoice_id)
    )
    if invoice is None:
        raise_not_found("Invoice not found.")
    if scope.company_id is not None and invoice.company_id != scope.company_id:
        raise_not_found("Invoice not found.")
    ensure_branch_access(user, invoice.branch_id)
    existing = db.scalar(
        select(SalesReturn)
        .options(selectinload(SalesReturn.items), joinedload(SalesReturn.credit_note))
        .where(
            SalesReturn.company_id == invoice.company_id,
            SalesReturn.idempotency_key == payload.idempotency_key,
        )
    )
    if existing is not None:
        return _read(existing)
    if invoice.status in {InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED, InvoiceStatus.RETURNED}:
        raise_conflict("Only an issued, paid, partial-paid, or credit invoice can be returned.")

    item_map = {item.id: item for item in invoice.items}
    requested_ids = [item.invoice_item_id for item in payload.items]
    if len(set(requested_ids)) != len(requested_ids):
        raise_bad_request("Each invoice item may appear only once in a return.")

    now = datetime.now(UTC)
    return_row = SalesReturn(
        company_id=invoice.company_id,
        branch_id=invoice.branch_id,
        invoice_id=invoice.id,
        customer_id=invoice.customer_id,
        return_number=f"RET-{now:%Y%m%d}-{uuid4().hex[:8].upper()}",
        status=SalesReturnStatus.ISSUED,
        refund_mode=payload.refund_mode,
        reason=payload.reason,
        total_amount=Decimal("0.00"),
        created_by=user.id,
        returned_at=now,
        idempotency_key=payload.idempotency_key,
    )
    db.add(return_row)
    db.flush()

    total = Decimal("0.00")
    for requested in payload.items:
        item = item_map.get(requested.invoice_item_id)
        if item is None:
            raise_bad_request("Return item does not belong to the invoice.")
        requested_quantity = _quantity(requested.quantity)
        already_returned = _returned_quantity(db, invoice_item_id=item.id)
        if already_returned + requested_quantity > _quantity(item.quantity):
            raise_conflict(f"Return quantity exceeds the remaining quantity for item {item.id}.")

        ratio = requested_quantity / _quantity(item.quantity)
        line_total = _money(_money(item.line_total) * ratio)
        taxable_value = _money(_money(item.taxable_value) * ratio)
        tax_total = _money((_money(item.cgst_total) + _money(item.sgst_total) + _money(item.igst_total) + _money(item.cess_total)) * ratio)
        restocked = bool(requested.restock and requested.condition == ReturnCondition.SALEABLE and item.product_id is not None)
        return_item = SalesReturnItem(
            return_id=return_row.id,
            invoice_item_id=item.id,
            product_id=item.product_id,
            quantity=requested_quantity,
            unit_price=_money(item.unit_price),
            taxable_value=taxable_value,
            tax_total=tax_total,
            line_total=line_total,
            condition=requested.condition,
            restocked=restocked,
        )
        db.add(return_item)
        total += line_total

        if restocked:
            inventory = db.scalar(
                select(Inventory).where(
                    Inventory.product_id == item.product_id,
                    Inventory.branch_id == invoice.branch_id,
                )
            )
            if inventory is None:
                raise_conflict(f"No inventory record exists for product {item.product_id}.")
            inventory.quantity_on_hand = _quantity(inventory.quantity_on_hand + requested_quantity)
            db.add(
                StockMovement(
                    company_id=invoice.company_id,
                    product_id=item.product_id,
                    branch_id=invoice.branch_id,
                    movement_type=StockMovementType.RETURN,
                    quantity_change=requested_quantity,
                    reason=f"Sales return {return_row.return_number}",
                    reference_type="sales_return",
                    reference_id=return_row.id,
                    created_by=user.id,
                    created_at=now,
                )
            )

    total = _money(total)
    if total <= 0:
        raise_bad_request("Return total must be greater than zero.")
    if payload.refund_mode == RefundMode.CUSTOMER_CREDIT and invoice.customer_id is None:
        raise_bad_request("Customer credit requires an invoice customer; choose cash or original payment for walk-in sales.")
    return_row.total_amount = total
    db.flush()

    note = CreditNote(
        company_id=invoice.company_id,
        branch_id=invoice.branch_id,
        invoice_id=invoice.id,
        sales_return_id=return_row.id,
        customer_id=invoice.customer_id,
        credit_note_number=f"CN-{now:%Y%m%d}-{uuid4().hex[:8].upper()}",
        status=CreditNoteStatus.ISSUED,
        amount=total,
        refund_mode=payload.refund_mode,
        reason=payload.reason,
        issued_by=user.id,
        issued_at=now,
        idempotency_key=payload.idempotency_key,
    )
    db.add(note)
    db.flush()

    if payload.refund_mode == RefundMode.CUSTOMER_CREDIT:
        add_customer_ledger_entry(
            db,
            customer_id=invoice.customer_id,
            branch_id=invoice.branch_id,
            entry_type=CustomerLedgerEntryType.CREDIT_NOTE,
            credit=total,
            reference_type="credit_note",
            reference_id=note.id,
            reason=f"Credit note {note.credit_note_number}",
            user=user,
        )
    else:
        db.add(
            FinancialReversal(
                company_id=invoice.company_id,
                branch_id=invoice.branch_id,
                invoice_id=invoice.id,
                reversal_type=ReversalType.REFUND,
                amount=total,
                reason=payload.reason,
                idempotency_key=f"{payload.idempotency_key}:refund",
                actor_id=user.id,
                compensation_json={"credit_note_id": note.id, "refund_mode": payload.refund_mode.value},
            )
        )

    all_returned = all(_returned_quantity(db, invoice_item_id=item.id) >= _quantity(item.quantity) for item in invoice.items)
    if all_returned:
        old_status = invoice.status
        invoice.status = InvoiceStatus.RETURNED
        invoice.balance_due = Decimal("0.00")
        db.add(InvoiceStatusHistory(invoice_id=invoice.id, from_status=old_status, to_status=InvoiceStatus.RETURNED, changed_by=user.id, notes=f"Fully returned via {note.credit_note_number}"))

    write_audit_log(
        db,
        action="sales_return.created",
        entity_type="sales_return",
        entity_id=return_row.id,
        user=user,
        company_id=invoice.company_id,
        new_value_json={"invoice_id": invoice.id, "total_amount": str(total), "refund_mode": payload.refund_mode.value, "credit_note_id": note.id},
        notes=payload.reason,
    )
    db.commit()
    db.refresh(return_row)
    return _read(return_row)


def get_sales_return(db: Session, *, scope: ScopeContext, user: User, return_id: int) -> SalesReturnRead:
    row = db.scalar(
        select(SalesReturn)
        .options(selectinload(SalesReturn.items), joinedload(SalesReturn.credit_note))
        .where(SalesReturn.id == return_id)
    )
    if row is None or (scope.company_id is not None and row.company_id != scope.company_id):
        raise_not_found("Sales return not found.")
    ensure_branch_access(user, row.branch_id)
    return _read(row)
