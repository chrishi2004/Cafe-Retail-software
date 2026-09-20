from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.expense import ExpenseCategoryCreate, ExpenseCategoryRead, ExpenseCreate, ExpenseRead, ExpenseSummaryRead
from app.services.expense import create_category, create_expense, expense_summary, list_categories

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("/categories", response_model=list[ExpenseCategoryRead])
def categories(_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> list[ExpenseCategoryRead]:
    return list_categories(db)


@router.post("/categories", response_model=ExpenseCategoryRead, status_code=status.HTTP_201_CREATED)
def add_category(payload: ExpenseCategoryCreate, user: Annotated[User, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN))], db: Annotated[Session, Depends(get_db)]) -> ExpenseCategoryRead:
    return create_category(db, user=user, payload=payload)


@router.post("", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
def add_expense(payload: ExpenseCreate, user: Annotated[User, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.STORE_MANAGER))], db: Annotated[Session, Depends(get_db)]) -> ExpenseRead:
    return create_expense(db, user=user, payload=payload)


@router.get("/summary", response_model=ExpenseSummaryRead)
def summary(start_date: date, end_date: date, _user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> ExpenseSummaryRead:
    return expense_summary(db, start_date=start_date, end_date=end_date)
