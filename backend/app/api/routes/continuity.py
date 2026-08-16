from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_scope_context, require_roles
from app.api.errors import raise_not_found
from app.core.config import settings
from app.core.scope import ScopeContext
from app.db.session import get_db
from app.models import ContinuityMode, ContinuityState, SyncDeadLetter, User, UserRole
from app.schemas.hc4 import (
    ContinuityStateRead,
    DeadLetterRead,
    DeadLetterRetryRead,
    ReconciliationRead,
)
from app.services.continuity import (
    _dead_letter_in_scope,
    continuity_state_read,
    latest_reconciliation,
    queue_metrics,
    reconciliation_read,
    refresh_state_metrics,
    run_reconciliation,
    state_for_scope,
)
from app.sync.service import retry_dead_letter

router = APIRouter(prefix="/sync", tags=["hc4-continuity"])
Database = Annotated[Session, Depends(get_db)]
Scope = Annotated[ScopeContext, Depends(get_scope_context)]
Viewer = Annotated[
    User,
    Depends(require_roles(UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.ANALYST)),
]
Operator = Annotated[
    User,
    Depends(require_roles(UserRole.ADMIN, UserRole.STORE_MANAGER)),
]


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _apply_stale_state(state: ContinuityState) -> None:
    if state.mode not in {
        ContinuityMode.LIVE,
        ContinuityMode.SYNCHRONIZING,
        ContinuityMode.CLOUD_CONTINUITY,
    }:
        return
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=settings.continuity_stale_after_seconds)
    heartbeat = _utc(state.last_heartbeat_at)
    lease_expiry = _utc(state.lease_expires_at)
    heartbeat_stale = heartbeat is None or heartbeat < cutoff
    lease_stale = lease_expiry is not None and lease_expiry <= now
    if heartbeat_stale or lease_stale:
        state.mode = ContinuityMode.STALE
        state.stale_since = state.stale_since or now
        state.attention_message = (
            "Writer lease expired before continuity recovery completed."
            if lease_stale
            else "Local Hub heartbeat is stale."
        )


@router.get("/continuity", response_model=ContinuityStateRead)
def continuity_state(db: Database, scope: Scope, _viewer: Viewer) -> ContinuityStateRead:
    state = state_for_scope(db, scope)
    refresh_state_metrics(db, state=state, metrics=queue_metrics(db, scope))
    _apply_stale_state(state)
    db.commit()
    return continuity_state_read(state)


@router.get("/reconciliation", response_model=ReconciliationRead)
def read_reconciliation(db: Database, scope: Scope, _viewer: Viewer) -> ReconciliationRead:
    report = latest_reconciliation(db, scope)
    if report is None:
        raise_not_found("No continuity reconciliation report exists for this scope.")
    return reconciliation_read(report)


@router.post("/reconcile", response_model=ReconciliationRead)
def reconcile(db: Database, scope: Scope, operator: Operator) -> ReconciliationRead:
    state = state_for_scope(db, scope)
    report = run_reconciliation(db, scope=scope, created_by=operator.id, state=state)
    if report.status.value == "clean" and state.last_heartbeat_at is None:
        state.mode = ContinuityMode.OFFLINE_LOCAL
        state.attention_message = None
    db.commit()
    return reconciliation_read(report)


@router.get("/dead-letters", response_model=list[DeadLetterRead])
def list_dead_letters(db: Database, scope: Scope, _viewer: Viewer) -> list[DeadLetterRead]:
    rows = [
        row
        for row in db.scalars(select(SyncDeadLetter).order_by(SyncDeadLetter.id.desc())).all()
        if _dead_letter_in_scope(row, scope)
    ]
    return [
        DeadLetterRead(
            id=row.id,
            direction=row.direction.value,
            event_id=row.event_id,
            correlation_id=row.correlation_id,
            error_code=row.error_code,
            error_message=row.error_message,
            retryable=row.retryable,
            retry_count=row.retry_count,
            status=row.status.value,
            first_failed_at=row.first_failed_at,
            last_failed_at=row.last_failed_at,
        )
        for row in rows
    ]


@router.post("/dead-letters/{dead_letter_id}/retry", response_model=DeadLetterRetryRead)
def retry_failed_sync(
    dead_letter_id: int,
    db: Database,
    scope: Scope,
    operator: Operator,
) -> DeadLetterRetryRead:
    row = db.get(SyncDeadLetter, dead_letter_id)
    if row is None or not _dead_letter_in_scope(row, scope):
        raise_not_found("Synchronization dead letter not found.")
    retried = retry_dead_letter(db, dead_letter_id, user_id=operator.id)
    db.commit()
    return DeadLetterRetryRead(
        id=retried.id,
        event_id=retried.event_id,
        status=retried.status.value,
        retry_count=retried.retry_count,
    )
