from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.errors import raise_bad_request, raise_conflict, raise_forbidden, raise_not_found
from app.core.scope import ScopeContext
from app.models import (
    AuditLog,
    CashRegisterMovement,
    CashRegisterMovementType,
    CashRegisterSession,
    CashRegisterSessionStatus,
    FinancialReversal,
    Invoice,
    InvoicePayment,
    InvoiceStatus,
    PaymentMode,
    PaymentModeType,
    ReversalType,
    User,
    UserRole,
)
from app.schemas.cash_register import RegisterMovementCreate, RegisterSessionCreate


OPEN_ROLES = {UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.STAFF, UserRole.ORDER_TAKER}
CLOSE_ROLES = {UserRole.ADMIN, UserRole.STORE_MANAGER}


def _money(value: Decimal | None) -> Decimal:
    return (value or Decimal("0.00")).quantize(Decimal("0.01"))


def _scope(scope: ScopeContext, *, company_id: int, branch_id: int) -> None:
    if scope.company_id is not None and scope.company_id != company_id:
        raise_not_found()
    if scope.branch_ids and branch_id not in scope.branch_ids:
        raise_not_found()


def _write_role(user: User, allowed: set[UserRole]) -> None:
    if user.role != UserRole.SUPER_ADMIN and user.role not in allowed:
        raise_forbidden("You do not have permission to operate the cash register.")


def _audit(db: Session, *, user: User, session: CashRegisterSession, action: str, notes: str) -> None:
    db.add(
        AuditLog(
            user_id=user.id,
            company_id=session.company_id,
            branch_id=session.branch_id,
            action=action,
            entity_type="cash_register_session",
            entity_id=session.id,
            notes=notes,
        )
    )


def _session_or_404(db: Session, *, scope: ScopeContext, session_id: int) -> CashRegisterSession:
    row = db.get(CashRegisterSession, session_id)
    if row is None:
        raise_not_found()
    _scope(scope, company_id=row.company_id, branch_id=row.branch_id)
    return row


def open_session(db: Session, *, scope: ScopeContext, user: User, payload: RegisterSessionCreate) -> CashRegisterSession:
    _write_role(user, OPEN_ROLES)
    if scope.company_id is None:
        raise_bad_request("Select a venture before opening a cash register.")
    if scope.branch_ids and payload.branch_id not in scope.branch_ids:
        raise_not_found()
    existing = db.scalar(
        select(CashRegisterSession).where(
            CashRegisterSession.company_id == scope.company_id,
            CashRegisterSession.branch_id == payload.branch_id,
            CashRegisterSession.status == CashRegisterSessionStatus.OPEN,
        )
    )
    if existing:
        raise_conflict("This branch already has an open cash register session.")
    row = CashRegisterSession(
        company_id=scope.company_id,
        branch_id=payload.branch_id,
        opening_float=_money(payload.opening_float),
        expected_cash=_money(payload.opening_float),
        opened_by=user.id,
        notes=payload.notes,
    )
    db.add(row)
    db.flush()
    _audit(db, user=user, session=row, action="cash_register_opened", notes="Cash register session opened.")
    db.commit()
    db.refresh(row)
    return row


def record_movement(
    db: Session,
    *,
    scope: ScopeContext,
    user: User,
    session_id: int,
    payload: RegisterMovementCreate,
) -> CashRegisterMovement:
    _write_role(user, OPEN_ROLES)
    session = _session_or_404(db, scope=scope, session_id=session_id)
    if session.status != CashRegisterSessionStatus.OPEN:
        raise_conflict("Movements cannot be added to a closed register session.")
    existing = db.scalar(
        select(CashRegisterMovement).where(
            CashRegisterMovement.company_id == session.company_id,
            CashRegisterMovement.idempotency_key == payload.idempotency_key,
        )
    )
    if existing:
        return existing
    movement = CashRegisterMovement(
        company_id=session.company_id,
        branch_id=session.branch_id,
        session_id=session.id,
        movement_type=CashRegisterMovementType(payload.movement_type),
        amount=_money(payload.amount),
        reason=payload.reason,
        reference=payload.reference,
        recorded_by=user.id,
        idempotency_key=payload.idempotency_key,
    )
    db.add(movement)
    db.add(
        AuditLog(
            user_id=user.id,
            company_id=session.company_id,
            branch_id=session.branch_id,
            action="cash_register_movement_recorded",
            entity_type="cash_register_movement",
            entity_id=None,
            notes=payload.reason,
            new_value_json={"movement_type": payload.movement_type, "amount": str(payload.amount)},
        )
    )
    db.commit()
    db.refresh(movement)
    return movement


def _payment_rows(db: Session, *, session: CashRegisterSession, end: datetime):
    return db.execute(
        select(InvoicePayment.amount, InvoicePayment.is_credit_marker, PaymentMode.mode_type)
        .join(Invoice, Invoice.id == InvoicePayment.invoice_id)
        .outerjoin(PaymentMode, PaymentMode.id == InvoicePayment.payment_mode_id)
        .where(
            Invoice.company_id == session.company_id,
            Invoice.branch_id == session.branch_id,
            InvoicePayment.payment_datetime >= session.opened_at,
            InvoicePayment.payment_datetime < end,
            Invoice.status.not_in([InvoiceStatus.CANCELLED, InvoiceStatus.RETURNED]),
        )
    ).all()


def summary(db: Session, *, scope: ScopeContext, session_id: int) -> dict:
    session = _session_or_404(db, scope=scope, session_id=session_id)
    end = session.closed_at or datetime.now(UTC)
    cash = Decimal("0.00")
    non_cash = Decimal("0.00")
    credit = Decimal("0.00")
    mode_totals: dict[str, Decimal] = {}
    for amount, credit_marker, mode_type in _payment_rows(db, session=session, end=end):
        value = _money(amount)
        mode = mode_type.value if isinstance(mode_type, PaymentModeType) else str(mode_type or "other")
        mode_totals[mode] = _money(mode_totals.get(mode, Decimal("0.00")) + value)
        if credit_marker or mode == PaymentModeType.CREDIT.value:
            credit += value
        elif mode == PaymentModeType.CASH.value:
            cash += value
        else:
            non_cash += value

    refunds = _money(
        db.scalar(
            select(func.coalesce(func.sum(FinancialReversal.amount), 0)).where(
                FinancialReversal.company_id == session.company_id,
                FinancialReversal.branch_id == session.branch_id,
                FinancialReversal.reversal_type == ReversalType.REFUND,
                FinancialReversal.created_at >= session.opened_at,
                FinancialReversal.created_at < end,
            )
        )
    )
    movements = list(
        db.scalars(
            select(CashRegisterMovement)
            .where(CashRegisterMovement.session_id == session.id)
            .order_by(CashRegisterMovement.occurred_at, CashRegisterMovement.id)
        )
    )
    cash_in = sum((m.amount for m in movements if m.movement_type == CashRegisterMovementType.CASH_IN), Decimal("0.00"))
    cash_out = sum((m.amount for m in movements if m.movement_type == CashRegisterMovementType.CASH_OUT), Decimal("0.00"))
    expenses = sum((m.amount for m in movements if m.movement_type == CashRegisterMovementType.EXPENSE), Decimal("0.00"))
    adjustments = sum((m.amount for m in movements if m.movement_type == CashRegisterMovementType.ADJUSTMENT), Decimal("0.00"))
    expected = _money(session.opening_float + cash + cash_in + adjustments - cash_out - expenses - refunds)
    session.expected_cash = expected
    return {
        "id": session.id,
        "company_id": session.company_id,
        "branch_id": session.branch_id,
        "status": session.status.value,
        "opening_float": _money(session.opening_float),
        "opened_at": session.opened_at,
        "closed_at": session.closed_at,
        "expected_cash": expected,
        "counted_cash": _money(session.counted_cash) if session.counted_cash is not None else None,
        "variance": _money(session.variance) if session.variance is not None else None,
        "cash_collections": _money(cash),
        "cash_refunds": refunds,
        "cash_in": _money(cash_in),
        "cash_out": _money(cash_out),
        "expenses": _money(expenses),
        "non_cash_total": _money(non_cash),
        "credit_total": _money(credit),
        "mode_totals": [{"mode": key, "amount": _money(value)} for key, value in sorted(mode_totals.items())],
        "movements": [
            {
                "id": movement.id,
                "movement_type": movement.movement_type.value,
                "amount": _money(movement.amount),
                "reason": movement.reason,
                "reference": movement.reference,
                "recorded_by": movement.recorded_by,
                "occurred_at": movement.occurred_at,
            }
            for movement in movements
        ],
    }


def count_session(db: Session, *, scope: ScopeContext, user: User, session_id: int, counted_cash: Decimal) -> dict:
    _write_role(user, CLOSE_ROLES)
    session = _session_or_404(db, scope=scope, session_id=session_id)
    if session.status != CashRegisterSessionStatus.OPEN:
        raise_conflict("Only an open register session can be counted.")
    session.counted_cash = _money(counted_cash)
    data = summary(db, scope=scope, session_id=session.id)
    session.variance = _money(session.counted_cash - data["expected_cash"])
    db.commit()
    return summary(db, scope=scope, session_id=session.id)


def close_session(db: Session, *, scope: ScopeContext, user: User, session_id: int) -> dict:
    _write_role(user, CLOSE_ROLES)
    session = _session_or_404(db, scope=scope, session_id=session_id)
    if session.status != CashRegisterSessionStatus.OPEN:
        raise_conflict("Register session is already closed.")
    if session.counted_cash is None:
        raise_conflict("Counted cash is required before closing the register.")
    session.closed_at = datetime.now(UTC)
    session.closed_by = user.id
    session.status = CashRegisterSessionStatus.CLOSED
    data = summary(db, scope=scope, session_id=session.id)
    session.variance = _money(session.counted_cash - data["expected_cash"])
    _audit(db, user=user, session=session, action="cash_register_closed", notes=f"Cash variance: {session.variance}.")
    db.commit()
    return summary(db, scope=scope, session_id=session.id)
