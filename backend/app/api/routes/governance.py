from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_scope_context, require_admin, require_roles
from app.core.scope import ScopeContext
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.governance import (
    ClosingCreate, ClosingRead, ClosingReopen, ClosingSubmit, PurgeApprove,
    PurgeCreate, PurgeExecute, PurgeRead, ReversalRead, StepUpRequest,
    VoidInvoiceRequest,
)
from app.services.governance import (
    approve_purge, close_day, execute_purge, get_or_create_closing,
    grant_step_up, reopen_day, request_purge, submit_closing, void_invoice,
)

router = APIRouter(prefix="/governance", tags=["governance"])


@router.post("/step-up")
def step_up(
    payload: StepUpRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    granted = grant_step_up(db, user=user, payload=payload)
    return {"status": "granted", "expires_at": granted.isoformat()}


@router.post("/closings", response_model=ClosingRead)
def create_closing(
    payload: ClosingCreate,
    user: Annotated[User, Depends(require_admin)],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ClosingRead:
    return get_or_create_closing(db, scope=scope, user=user, payload=payload)


@router.post("/closings/{closing_id}/submit", response_model=ClosingRead)
def submit(
    closing_id: int,
    payload: ClosingSubmit,
    user: Annotated[User, Depends(require_admin)],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ClosingRead:
    return submit_closing(db, scope=scope, user=user, row_id=closing_id, payload=payload)


@router.post("/closings/{closing_id}/close", response_model=ClosingRead)
def close(
    closing_id: int,
    user: Annotated[User, Depends(require_admin)],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ClosingRead:
    return close_day(db, scope=scope, user=user, row_id=closing_id)


@router.post("/closings/{closing_id}/reopen", response_model=ClosingRead)
def reopen(
    closing_id: int,
    payload: ClosingReopen,
    user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ClosingRead:
    return reopen_day(db, scope=scope, user=user, row_id=closing_id, payload=payload)


@router.post("/voids/invoices/{invoice_id}", response_model=ReversalRead)
def void(
    invoice_id: int,
    payload: VoidInvoiceRequest,
    user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.STORE_MANAGER))],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ReversalRead:
    return void_invoice(db, scope=scope, user=user, invoice_id=invoice_id, payload=payload)


@router.post("/purges", response_model=PurgeRead)
def create_purge(
    payload: PurgeCreate,
    user: Annotated[User, Depends(require_roles(UserRole.SUPER_ADMIN))],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> PurgeRead:
    return request_purge(db, scope=scope, user=user, payload=payload)


@router.post("/purges/{purge_id}/approve", response_model=PurgeRead)
def approve(
    purge_id: int,
    payload: PurgeApprove,
    user: Annotated[User, Depends(require_roles(UserRole.SUPER_ADMIN))],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> PurgeRead:
    return approve_purge(db, scope=scope, user=user, row_id=purge_id, payload=payload)


@router.post("/purges/{purge_id}/execute", response_model=PurgeRead)
def execute(
    purge_id: int,
    payload: PurgeExecute,
    user: Annotated[User, Depends(require_roles(UserRole.SUPER_ADMIN))],
    scope: Annotated[ScopeContext, Depends(get_scope_context)],
    db: Annotated[Session, Depends(get_db)],
) -> PurgeRead:
    return execute_purge(db, scope=scope, user=user, row_id=purge_id, payload=payload)
