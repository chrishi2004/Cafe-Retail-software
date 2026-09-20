from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_scope_context, require_any_permission
from app.core.scope import ScopeContext
from app.db.session import get_db
from app.models import User
from app.schemas.cash_register import (
    RegisterCount,
    RegisterMovementCreate,
    RegisterMovementRead,
    RegisterSessionCreate,
    RegisterSummary,
)
from app.services.cash_register import (
    close_session,
    count_session,
    open_session,
    record_movement,
    summary,
)

router = APIRouter(
    prefix="/cash-register",
    tags=["cash-register"],
    dependencies=[Depends(require_any_permission("billing.read", "reports.read"))],
)


@router.post("/sessions", response_model=RegisterSummary)
def create_session(
    payload: RegisterSessionCreate,
    user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    session = open_session(db, scope=scope, user=user, payload=payload)
    return summary(db, scope=scope, session_id=session.id)


@router.get("/sessions/{session_id}", response_model=RegisterSummary)
def read_session(
    session_id: int,
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return summary(db, scope=scope, session_id=session_id)


@router.post("/sessions/{session_id}/movements", response_model=RegisterMovementRead)
def add_movement(
    session_id: int,
    payload: RegisterMovementCreate,
    user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> object:
    return record_movement(db, scope=scope, user=user, session_id=session_id, payload=payload)


@router.post("/sessions/{session_id}/count", response_model=RegisterSummary)
def count(
    session_id: int,
    payload: RegisterCount,
    user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return count_session(db, scope=scope, user=user, session_id=session_id, counted_cash=payload.counted_cash)


@router.post("/sessions/{session_id}/close", response_model=RegisterSummary)
def close(
    session_id: int,
    user: Annotated[User, Depends(get_current_user)],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return close_session(db, scope=scope, user=user, session_id=session_id)
