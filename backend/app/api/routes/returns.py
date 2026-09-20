from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_scope_context, require_roles
from app.core.scope import ScopeContext
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.returns import SalesReturnCreate, SalesReturnRead
from app.services.returns import create_sales_return, get_sales_return

router = APIRouter(prefix="/returns", tags=["returns"])
WRITE_ROLES = (UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.STAFF)


@router.post("/invoices/{invoice_id}", response_model=SalesReturnRead, status_code=status.HTTP_201_CREATED)
def create_return(
    invoice_id: int,
    payload: SalesReturnCreate,
    user: Annotated[User, Depends(require_roles(*WRITE_ROLES))],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> SalesReturnRead:
    return create_sales_return(db, scope=scope, user=user, invoice_id=invoice_id, payload=payload)


@router.get("/{return_id}", response_model=SalesReturnRead)
def read_return(
    return_id: int,
    user: Annotated[User, Depends(require_roles(*WRITE_ROLES, UserRole.ANALYST))],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> SalesReturnRead:
    return get_sales_return(db, scope=scope, user=user, return_id=return_id)
