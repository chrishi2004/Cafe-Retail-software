from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import ensure_branch_access
from app.api.errors import raise_bad_request, raise_conflict, raise_forbidden, raise_not_found
from app.models import ExpenseCategory, ExpenseEntry, User, UserRole
from app.schemas.expense import ExpenseCategoryCreate, ExpenseCategoryRead, ExpenseCreate, ExpenseRead, ExpenseSummaryRead
from app.services.audit import write_audit_log

MONEY = Decimal("0.01")


def _money(value: Decimal | int | str | None) -> Decimal:
    return Decimal(str(value or "0")).quantize(MONEY, rounding=ROUND_HALF_UP)


def _write_user(user: User, branch_id: int) -> None:
    if user.role not in {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.STORE_MANAGER}:
        raise_forbidden("Only an admin or store manager can post expenses.")
    ensure_branch_access(user, branch_id)


def create_category(db: Session, *, user: User, payload: ExpenseCategoryCreate) -> ExpenseCategoryRead:
    if user.role not in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        raise_forbidden("Only an admin can manage expense categories.")
    existing = db.scalar(select(ExpenseCategory).where(ExpenseCategory.name == payload.name.strip()))
    if existing is not None:
        return ExpenseCategoryRead.model_validate(existing)
    row = ExpenseCategory(company_id=user.company_id, name=payload.name.strip())
    db.add(row); db.flush(); write_audit_log(db, action="expense_category.created", entity_type="expense_category", entity_id=row.id, user=user, new_value_json={"name": row.name}); db.commit(); db.refresh(row)
    return ExpenseCategoryRead.model_validate(row)


def list_categories(db: Session) -> list[ExpenseCategoryRead]:
    return [ExpenseCategoryRead.model_validate(row) for row in db.scalars(select(ExpenseCategory).where(ExpenseCategory.is_active.is_(True)).order_by(ExpenseCategory.name)).all()]


def create_expense(db: Session, *, user: User, payload: ExpenseCreate) -> ExpenseRead:
    _write_user(user, payload.branch_id)
    existing = db.scalar(select(ExpenseEntry).where(ExpenseEntry.company_id == user.company_id, ExpenseEntry.idempotency_key == payload.idempotency_key))
    if existing is not None:
        return ExpenseRead.model_validate(existing)
    category = db.get(ExpenseCategory, payload.category_id)
    if category is None or not category.is_active:
        raise_not_found("Expense category not found or inactive.")
    row = ExpenseEntry(company_id=user.company_id, branch_id=payload.branch_id, category_id=category.id, expense_date=payload.expense_date, amount=_money(payload.amount), payment_mode=payload.payment_mode.strip().lower(), vendor_name=payload.vendor_name, reason=payload.reason, idempotency_key=payload.idempotency_key, created_by=user.id)
    db.add(row); db.flush(); write_audit_log(db, action="expense.created", entity_type="expense_entry", entity_id=row.id, user=user, new_value_json={"amount": str(row.amount), "category_id": row.category_id}, notes=row.reason); db.commit(); db.refresh(row)
    return ExpenseRead.model_validate(row)


def expense_summary(db: Session, *, start_date: date, end_date: date) -> ExpenseSummaryRead:
    if end_date < start_date:
        raise_bad_request("End date cannot be before start date.")
    rows = db.scalars(select(ExpenseEntry).where(ExpenseEntry.expense_date >= start_date, ExpenseEntry.expense_date <= end_date)).all()
    category_ids = {row.category_id for row in rows}
    names = {row.id: row.name for row in db.scalars(select(ExpenseCategory).where(ExpenseCategory.id.in_(category_ids))).all()} if category_ids else {}
    by_category: dict[str, Decimal] = {}; by_payment: dict[str, Decimal] = {}
    for row in rows:
        by_category[names.get(row.category_id, str(row.category_id))] = _money(by_category.get(names.get(row.category_id, str(row.category_id)), Decimal("0")) + row.amount)
        by_payment[row.payment_mode] = _money(by_payment.get(row.payment_mode, Decimal("0")) + row.amount)
    return ExpenseSummaryRead(start_date=start_date, end_date=end_date, total_amount=_money(sum((row.amount for row in rows), Decimal("0"))), by_category=by_category, by_payment_mode=by_payment)
