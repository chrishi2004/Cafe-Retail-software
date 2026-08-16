from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_scope_context, require_roles
from app.core.config import settings
from app.core.scope import ScopeContext
from app.db.session import get_db
from app.models import (
    ContinuityMode,
    ContinuityState,
    SyncDeadLetter,
    SyncDeadLetterStatus,
    SyncDevice,
    SyncInbox,
    SyncInboxStatus,
    SyncOutbox,
    SyncOutboxStatus,
    User,
    UserRole,
)
from app.schemas.hc3 import SyncStatusRead
from app.services.continuity import latest_reconciliation, scope_key_from_scope

router = APIRouter(prefix="/sync", tags=["sync-status"])
Database = Annotated[Session, Depends(get_db)]
Scope = Annotated[ScopeContext, Depends(get_scope_context)]
SyncViewer = Annotated[
    User,
    Depends(require_roles(UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.ANALYST)),
]


def _scope_filters(model, scope: ScopeContext):
    filters = [model.business_group_id == str(scope.business_group_id)]
    if not scope.all_companies and scope.company_id is not None:
        filters.append(model.company_id == str(scope.company_id))
    if scope.branch_ids:
        filters.append(model.branch_id.in_([str(value) for value in scope.branch_ids]))
    return filters


def _dead_letter_in_scope(row: SyncDeadLetter, scope: ScopeContext) -> bool:
    envelope = row.event_envelope_json or {}
    if str(envelope.get("business_group_id")) != str(scope.business_group_id):
        return False
    if not scope.all_companies and scope.company_id is not None:
        if str(envelope.get("company_id")) != str(scope.company_id):
            return False
    if scope.branch_ids and str(envelope.get("branch_id")) not in {str(value) for value in scope.branch_ids}:
        return False
    return True


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _apply_stale_state(state: ContinuityState | None) -> bool:
    if state is None or state.mode not in {
        ContinuityMode.LIVE,
        ContinuityMode.SYNCHRONIZING,
        ContinuityMode.CLOUD_CONTINUITY,
    }:
        return False
    now = datetime.now(UTC)
    stale_cutoff = now - timedelta(seconds=settings.continuity_stale_after_seconds)
    heartbeat = _utc(state.last_heartbeat_at)
    lease_expiry = _utc(state.lease_expires_at)
    heartbeat_stale = heartbeat is None or heartbeat < stale_cutoff
    lease_stale = lease_expiry is not None and lease_expiry <= now
    if not heartbeat_stale and not lease_stale:
        return False
    state.mode = ContinuityMode.STALE
    state.stale_since = state.stale_since or now
    state.attention_message = (
        "Writer lease expired before continuity recovery completed."
        if lease_stale
        else "Local Hub heartbeat is stale."
    )
    return True


@router.get("/status", response_model=SyncStatusRead)
def sync_status(db: Database, scope: Scope, _viewer: SyncViewer) -> SyncStatusRead:
    inbox_filters = _scope_filters(SyncInbox, scope)
    outbox_filters = _scope_filters(SyncOutbox, scope)
    pending_inbox = db.scalar(
        select(func.count(SyncInbox.id)).where(
            *inbox_filters,
            SyncInbox.status.in_([SyncInboxStatus.PENDING, SyncInboxStatus.RETRY, SyncInboxStatus.BLOCKED]),
        )
    ) or 0
    pending_outbox = db.scalar(
        select(func.count(SyncOutbox.id)).where(
            *outbox_filters,
            SyncOutbox.status.in_([SyncOutboxStatus.PENDING, SyncOutboxStatus.RETRY]),
        )
    ) or 0
    oldest_inbox = db.scalar(
        select(func.min(SyncInbox.created_at)).where(
            *inbox_filters,
            SyncInbox.status.in_([SyncInboxStatus.PENDING, SyncInboxStatus.RETRY, SyncInboxStatus.BLOCKED]),
        )
    )
    oldest_outbox = db.scalar(
        select(func.min(SyncOutbox.created_at)).where(
            *outbox_filters,
            SyncOutbox.status.in_([SyncOutboxStatus.PENDING, SyncOutboxStatus.RETRY]),
        )
    )
    oldest = min(
        [value for value in (_utc(oldest_inbox), _utc(oldest_outbox)) if value is not None],
        default=None,
    )
    last_inbound = db.scalar(select(func.max(SyncInbox.processed_at)).where(*inbox_filters))
    last_outbound = db.scalar(select(func.max(SyncOutbox.sent_at)).where(*outbox_filters))
    dead_letters = [
        row
        for row in db.scalars(
            select(SyncDeadLetter).where(
                SyncDeadLetter.status.in_([SyncDeadLetterStatus.OPEN, SyncDeadLetterStatus.RETRY_PENDING])
            )
        ).all()
        if _dead_letter_in_scope(row, scope)
    ]
    device_last_seen = db.scalar(select(func.max(SyncDevice.last_seen_at)))
    age = None if oldest is None else max(0, int((datetime.now(UTC) - oldest).total_seconds()))
    continuity = db.scalar(
        select(ContinuityState).where(ContinuityState.scope_key == scope_key_from_scope(scope))
    )
    if _apply_stale_state(continuity):
        db.commit()
    reconciliation = latest_reconciliation(db, scope)
    return SyncStatusRead(
        company_id=None if scope.all_companies else scope.company_id,
        branch_ids=list(scope.branch_ids),
        pending_inbox=int(pending_inbox),
        pending_outbox=int(pending_outbox),
        dead_letters=len(dead_letters),
        oldest_pending_age_seconds=age,
        last_inbound_sync_at=last_inbound,
        last_outbound_sync_at=last_outbound,
        local_device_last_seen_at=device_last_seen,
        continuity_mode=continuity.mode.value if continuity else None,
        fencing_epoch=continuity.fencing_epoch if continuity else 0,
        lease_expires_at=continuity.lease_expires_at if continuity else None,
        last_heartbeat_at=continuity.last_heartbeat_at if continuity else None,
        last_cloud_contact_at=continuity.last_cloud_contact_at if continuity else None,
        last_reconciled_at=continuity.last_reconciled_at if continuity else None,
        last_queue_drain_at=continuity.last_queue_drain_at if continuity else None,
        reconciliation_status=reconciliation.status.value if reconciliation else None,
        attention_message=continuity.attention_message if continuity else None,
    )
