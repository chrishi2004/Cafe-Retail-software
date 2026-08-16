from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.errors import raise_bad_request, raise_conflict, raise_forbidden, raise_not_found
from app.core.scope import ScopeContext
from app.core.security import verify_password
from app.models import (
    AuditLog, BusinessDayClosure, CafeOrder, CafeOrderItem, ClosingStatus,
    Company, FinancialReversal, Invoice, InvoicePayment, InvoiceStatus,
    PaymentMode, PurgeRequest, PurgeStatus, RecordTombstone, ReversalType, User, UserRole,
)
from app.schemas.governance import (
    ClosingCreate, ClosingReopen, ClosingSubmit, PurgeApprove, PurgeCreate,
    PurgeExecute, StepUpRequest, VoidInvoiceRequest,
)


def _money(value: Decimal | None) -> Decimal:
    return (value or Decimal("0.00")).quantize(Decimal("0.01"))


def _scope_company(scope: ScopeContext, company_id: int) -> None:
    if scope.company_id is not None and scope.company_id != company_id:
        raise_not_found()


def _scope_branch(scope: ScopeContext, branch_id: int) -> None:
    if scope.branch_ids and branch_id not in scope.branch_ids:
        raise_not_found()


def _audit(db: Session, *, user: User, company_id: int, branch_id: int | None, action: str, entity_type: str, entity_id: int | None, notes: str, old: dict | None = None, new: dict | None = None) -> None:
    db.add(AuditLog(
        user_id=user.id, company_id=company_id, branch_id=branch_id,
        action=action, entity_type=entity_type, entity_id=entity_id,
        old_value_json=old, new_value_json=new, notes=notes,
    ))


def _period(date_value: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_value, time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


def _payment_totals(db: Session, *, company_id: int, branch_id: int, business_date: date) -> tuple[Decimal, Decimal]:
    start, end = _period(business_date)
    rows = db.execute(
        select(InvoicePayment.amount, PaymentMode.name)
        .join(Invoice, Invoice.id == InvoicePayment.invoice_id)
        .outerjoin(PaymentMode, PaymentMode.id == InvoicePayment.payment_mode_id)
        .where(
            Invoice.company_id == company_id,
            Invoice.branch_id == branch_id,
            InvoicePayment.payment_datetime >= start,
            InvoicePayment.payment_datetime < end,
            Invoice.status.not_in([InvoiceStatus.CANCELLED, InvoiceStatus.RETURNED]),
            InvoicePayment.is_credit_marker.is_(False),
        )
    ).all()
    cash = Decimal("0.00")
    non_cash = Decimal("0.00")
    for amount, name in rows:
        if "cash" in (name or "").lower():
            cash += amount or Decimal("0.00")
        else:
            non_cash += amount or Decimal("0.00")
    return _money(cash), _money(non_cash)


def get_or_create_closing(db: Session, *, scope: ScopeContext, user: User, payload: ClosingCreate) -> BusinessDayClosure:
    _scope_branch(scope, payload.branch_id)
    if scope.company_id is None:
        raise_bad_request("Select a venture before creating a branch closing.")
    _scope_company(scope, scope.company_id)
    existing = db.scalar(select(BusinessDayClosure).where(
        BusinessDayClosure.company_id == scope.company_id,
        BusinessDayClosure.branch_id == payload.branch_id,
        BusinessDayClosure.business_date == payload.business_date,
    ))
    if existing:
        return existing
    cash, non_cash = _payment_totals(db, company_id=scope.company_id, branch_id=payload.branch_id, business_date=payload.business_date)
    expected = _money(payload.opening_cash + cash)
    row = BusinessDayClosure(
        company_id=scope.company_id, branch_id=payload.branch_id, business_date=payload.business_date,
        opening_cash=_money(payload.opening_cash), cash_collections=cash,
        expected_cash=expected, non_cash_total=non_cash, status=ClosingStatus.OPEN,
    )
    db.add(row)
    _audit(db, user=user, company_id=scope.company_id, branch_id=payload.branch_id, action="closing_opened", entity_type="business_day_closure", entity_id=None, notes="Business day closing opened.")
    db.commit()
    db.refresh(row)
    return row


def submit_closing(db: Session, *, scope: ScopeContext, user: User, row_id: int, payload: ClosingSubmit) -> BusinessDayClosure:
    row = db.get(BusinessDayClosure, row_id)
    if row is None:
        raise_not_found()
    _scope_company(scope, row.company_id); _scope_branch(scope, row.branch_id)
    if row.status not in {ClosingStatus.OPEN, ClosingStatus.REOPENED}:
        raise_conflict("Only an open or reopened day can be submitted.")
    row.counted_cash = _money(payload.counted_cash)
    row.variance = _money(row.counted_cash - row.expected_cash)
    row.status = ClosingStatus.SUBMITTED
    row.submitted_by = user.id
    _audit(db, user=user, company_id=row.company_id, branch_id=row.branch_id, action="closing_submitted", entity_type="business_day_closure", entity_id=row.id, notes="Counted cash submitted.", new={"counted_cash": str(row.counted_cash), "variance": str(row.variance)})
    db.commit(); db.refresh(row)
    return row


def close_day(db: Session, *, scope: ScopeContext, user: User, row_id: int) -> BusinessDayClosure:
    row = db.get(BusinessDayClosure, row_id)
    if row is None: raise_not_found()
    _scope_company(scope, row.company_id); _scope_branch(scope, row.branch_id)
    if row.status != ClosingStatus.SUBMITTED or row.counted_cash is None:
        raise_conflict("A counted cash submission is required before closing.")
    row.status = ClosingStatus.CLOSED; row.closed_by = user.id
    _audit(db, user=user, company_id=row.company_id, branch_id=row.branch_id, action="closing_closed", entity_type="business_day_closure", entity_id=row.id, notes="Business day closed.")
    db.commit(); db.refresh(row)
    return row


def reopen_day(db: Session, *, scope: ScopeContext, user: User, row_id: int, payload: ClosingReopen) -> BusinessDayClosure:
    row = db.get(BusinessDayClosure, row_id)
    if row is None: raise_not_found()
    _scope_company(scope, row.company_id); _scope_branch(scope, row.branch_id)
    if row.status != ClosingStatus.CLOSED: raise_conflict("Only a closed day can be reopened.")
    row.status = ClosingStatus.REOPENED; row.reopened_by = user.id; row.reopened_reason = payload.reason
    _audit(db, user=user, company_id=row.company_id, branch_id=row.branch_id, action="closing_reopened", entity_type="business_day_closure", entity_id=row.id, notes=payload.reason)
    db.commit(); db.refresh(row)
    return row


def void_invoice(db: Session, *, scope: ScopeContext, user: User, invoice_id: int, payload: VoidInvoiceRequest) -> FinancialReversal:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None: raise_not_found()
    _scope_company(scope, invoice.company_id); _scope_branch(scope, invoice.branch_id)
    existing = db.scalar(select(FinancialReversal).where(FinancialReversal.idempotency_key == payload.idempotency_key))
    if existing: return existing
    if invoice.status in {InvoiceStatus.CANCELLED, InvoiceStatus.RETURNED}:
        raise_conflict("Invoice is already voided or returned.")
    reversal = FinancialReversal(
        company_id=invoice.company_id, branch_id=invoice.branch_id, invoice_id=invoice.id,
        reversal_type=ReversalType.VOID, amount=_money(invoice.grand_total),
        reason=payload.reason, idempotency_key=payload.idempotency_key, actor_id=user.id,
        compensation_json={"payment_amount": str(_money(invoice.paid_amount)), "stock_compensation_required": True},
    )
    old={"status": invoice.status.value, "grand_total": str(invoice.grand_total)}
    invoice.status = InvoiceStatus.CANCELLED
    invoice.cancelled_at = datetime.now(UTC)
    invoice.cancellation_reason = payload.reason
    invoice.balance_due = Decimal("0.00")
    db.add(reversal)
    _audit(db, user=user, company_id=invoice.company_id, branch_id=invoice.branch_id, action="invoice_voided", entity_type="invoice", entity_id=invoice.id, notes=payload.reason, old=old, new={"status": "cancelled", "reversal_type": "void"})
    db.commit(); db.refresh(reversal)
    return reversal


def grant_step_up(db: Session, *, user: User, payload: StepUpRequest) -> datetime:
    if not verify_password(payload.password, user.password_hash):
        raise_forbidden("Step-up authentication failed.")
    now = datetime.now(UTC)
    user.last_step_up_at = now
    db.commit()
    return now


def _step_up_valid(user: User) -> bool:
    return user.last_step_up_at is not None and datetime.now(UTC) - user.last_step_up_at <= timedelta(minutes=10)


def _purge_scope(db: Session, scope: ScopeContext, entity_type: str, entity_id: int) -> tuple[int, int | None, dict]:
    allowed = {"demo_cafe_order"}
    if entity_type not in allowed: raise_bad_request("The requested purge entity is not allowlisted.")
    order = db.get(CafeOrder, entity_id)
    if order is None: raise_not_found()
    _scope_company(scope, order.company_id); _scope_branch(scope, order.branch_id)
    company = db.get(Company, order.company_id)
    if company is None or not company.is_demo: raise_forbidden("Only demo-company records can be purged.")
    dependency = {
        "entity_type": entity_type, "entity_id": entity_id,
        "order_items": int(db.scalar(select(func.count()).select_from(CafeOrderItem).where(CafeOrderItem.cafe_order_id == entity_id)) or 0),
        "billed": bool(order.billed_invoice_id),
        "has_table_session": bool(order.table_session_id),
    }
    if dependency["billed"] or dependency["has_table_session"]:
        raise_conflict("The dependency graph is not safe for controlled purge.")
    return order.company_id, order.branch_id, dependency


def request_purge(db: Session, *, scope: ScopeContext, user: User, payload: PurgeCreate) -> PurgeRequest:
    if user.role != UserRole.SUPER_ADMIN: raise_forbidden("Only Final Super Admin may request a purge.")
    company_id, branch_id, dependency = _purge_scope(db, scope, payload.entity_type, payload.entity_id)
    row = PurgeRequest(company_id=company_id, branch_id=branch_id, entity_type=payload.entity_type, entity_id=payload.entity_id, reason=payload.reason, backup_reference=payload.backup_reference, dependency_report=dependency, requested_by=user.id)
    db.add(row)
    _audit(db, user=user, company_id=company_id, branch_id=branch_id, action="purge_requested", entity_type=payload.entity_type, entity_id=payload.entity_id, notes=payload.reason)
    db.commit(); db.refresh(row)
    return row


def approve_purge(db: Session, *, scope: ScopeContext, user: User, row_id: int, payload: PurgeApprove) -> PurgeRequest:
    if user.role != UserRole.SUPER_ADMIN: raise_forbidden()
    if not _step_up_valid(user): raise_forbidden("A recent step-up grant is required.")
    row = db.get(PurgeRequest, row_id)
    if row is None: raise_not_found()
    if row.status != PurgeStatus.REQUESTED: raise_conflict("Purge request is not awaiting approval.")
    if row.requested_by == user.id: raise_forbidden("Requester cannot approve their own purge.")
    if payload.second_approval:
        row.second_approved_by = user.id
    else:
        row.approved_by = user.id
    row.status = PurgeStatus.APPROVED
    db.commit(); db.refresh(row)
    return row


def execute_purge(db: Session, *, scope: ScopeContext, user: User, row_id: int, payload: PurgeExecute) -> PurgeRequest:
    if user.role != UserRole.SUPER_ADMIN: raise_forbidden()
    if not _step_up_valid(user): raise_forbidden("A recent step-up grant is required.")
    row = db.get(PurgeRequest, row_id)
    if row is None: raise_not_found()
    if row.status != PurgeStatus.APPROVED: raise_conflict("Purge request is not approved.")
    expected = f"PURGE-{row.id}"
    if payload.typed_confirmation != expected: raise_bad_request("Typed confirmation does not match the purge request.")
    order = db.get(CafeOrder, row.entity_id)
    if order is None: raise_not_found()
    evidence = {"order_number": order.order_number, "public_id": order.public_id, "status": order.status.value}
    before_hash = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
    row.status = PurgeStatus.EXECUTING
    db.add(RecordTombstone(company_id=row.company_id, branch_id=row.branch_id, entity_type=row.entity_type, entity_id=row.entity_id, before_hash=before_hash, evidence_json=evidence, reason=row.reason, actor_id=user.id))
    db.execute(delete(CafeOrderItem).where(CafeOrderItem.cafe_order_id == row.entity_id))
    db.delete(order)
    row.status = PurgeStatus.COMPLETED; row.executed_at = datetime.now(UTC)
    _audit(db, user=user, company_id=row.company_id, branch_id=row.branch_id, action="purge_completed", entity_type=row.entity_type, entity_id=row.entity_id, notes="Controlled demo purge completed.")
    db.commit(); db.refresh(row)
    return row
