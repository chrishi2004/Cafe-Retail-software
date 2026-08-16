from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.scope import ScopeContext
from app.models import (
    CafeOrder,
    CafeOrderStatus,
    ContinuityMode,
    ContinuityReconciliation,
    ContinuityReconciliationStatus,
    ContinuityState,
    ContinuityTransactionReceipt,
    ContinuityTransactionStatus,
    Invoice,
    InvoicePaymentStatus,
    StockMovement,
    SyncDeadLetter,
    SyncDeadLetterStatus,
    SyncInbox,
    SyncInboxStatus,
    SyncOutbox,
    SyncOutboxStatus,
    TableSession,
    TableSessionStatus,
)
from app.schemas.hc4 import ContinuityStateRead, ReconciliationRead
from app.schemas.sync import EventEnvelope
from app.sync.service import PermanentSyncError

CAFE_SOURCE_TYPES = {"cafe_table_session", "cafe_takeaway"}


def scope_key(*, business_group_id: str, company_id: str | None, branch_id: str | None) -> str:
    return f"group:{business_group_id}:company:{company_id or '*'}:branch:{branch_id or '*'}"


def scope_key_from_scope(scope: ScopeContext) -> str:
    company = None if scope.all_companies else (str(scope.company_id) if scope.company_id is not None else None)
    branch = str(scope.branch_ids[0]) if len(scope.branch_ids) == 1 else None
    return scope_key(
        business_group_id=str(scope.business_group_id),
        company_id=company,
        branch_id=branch,
    )


def _record_filters(model, scope: ScopeContext):
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


def queue_metrics(db: Session, scope: ScopeContext) -> dict[str, int | datetime | None]:
    inbox_filters = _record_filters(SyncInbox, scope)
    outbox_filters = _record_filters(SyncOutbox, scope)
    inbox_statuses = [SyncInboxStatus.PENDING, SyncInboxStatus.RETRY, SyncInboxStatus.BLOCKED]
    outbox_statuses = [SyncOutboxStatus.PENDING, SyncOutboxStatus.RETRY]
    pending_inbox = db.scalar(
        select(func.count(SyncInbox.id)).where(*inbox_filters, SyncInbox.status.in_(inbox_statuses))
    ) or 0
    pending_outbox = db.scalar(
        select(func.count(SyncOutbox.id)).where(*outbox_filters, SyncOutbox.status.in_(outbox_statuses))
    ) or 0
    oldest_inbox = db.scalar(
        select(func.min(SyncInbox.created_at)).where(*inbox_filters, SyncInbox.status.in_(inbox_statuses))
    )
    oldest_outbox = db.scalar(
        select(func.min(SyncOutbox.created_at)).where(*outbox_filters, SyncOutbox.status.in_(outbox_statuses))
    )
    dead_letters = [
        row
        for row in db.scalars(
            select(SyncDeadLetter).where(
                SyncDeadLetter.status.in_([SyncDeadLetterStatus.OPEN, SyncDeadLetterStatus.RETRY_PENDING])
            )
        ).all()
        if _dead_letter_in_scope(row, scope)
    ]
    oldest = min([value for value in (oldest_inbox, oldest_outbox) if value is not None], default=None)
    return {
        "pending_inbox": int(pending_inbox),
        "pending_outbox": int(pending_outbox),
        "dead_letters": len(dead_letters),
        "oldest_pending_at": oldest,
        "last_inbound_sync_at": db.scalar(select(func.max(SyncInbox.processed_at)).where(*inbox_filters)),
        "last_outbound_sync_at": db.scalar(select(func.max(SyncOutbox.sent_at)).where(*outbox_filters)),
    }


def get_or_create_state(
    db: Session,
    *,
    business_group_id: str,
    company_id: str | None,
    branch_id: str | None,
) -> ContinuityState:
    key = scope_key(
        business_group_id=business_group_id,
        company_id=company_id,
        branch_id=branch_id,
    )
    row = db.scalar(select(ContinuityState).where(ContinuityState.scope_key == key).with_for_update())
    if row is None:
        row = ContinuityState(
            scope_key=key,
            business_group_id=business_group_id,
            company_id=company_id,
            branch_id=branch_id,
            mode=ContinuityMode.SYNCHRONIZING,
        )
        db.add(row)
        db.flush()
    return row


def state_for_scope(db: Session, scope: ScopeContext) -> ContinuityState:
    key = scope_key_from_scope(scope)
    row = db.scalar(select(ContinuityState).where(ContinuityState.scope_key == key))
    if row is not None:
        return row
    company = None if scope.all_companies else (str(scope.company_id) if scope.company_id is not None else None)
    branch = str(scope.branch_ids[0]) if len(scope.branch_ids) == 1 else None
    return get_or_create_state(
        db,
        business_group_id=str(scope.business_group_id),
        company_id=company,
        branch_id=branch,
    )


def refresh_state_metrics(
    db: Session,
    *,
    state: ContinuityState,
    metrics: dict[str, int | datetime | None],
    mode: ContinuityMode | None = None,
    attention_message: str | None = None,
    now: datetime | None = None,
) -> ContinuityState:
    current = now or datetime.now(UTC)
    state.pending_inbox = int(metrics["pending_inbox"] or 0)
    state.pending_outbox = int(metrics["pending_outbox"] or 0)
    state.dead_letter_count = int(metrics["dead_letters"] or 0)
    if mode is not None:
        state.mode = mode
    if state.dead_letter_count > 0:
        state.mode = ContinuityMode.ATTENTION_REQUIRED
        state.attention_message = attention_message or "Synchronization has unresolved dead-letter records."
    elif attention_message is not None:
        state.attention_message = attention_message
    elif state.mode != ContinuityMode.ATTENTION_REQUIRED:
        state.attention_message = None
    if state.pending_inbox == 0 and state.pending_outbox == 0:
        state.last_queue_drain_at = current
    db.flush()
    return state


def continuity_state_read(row: ContinuityState) -> ContinuityStateRead:
    return ContinuityStateRead(
        scope_key=row.scope_key,
        company_id=int(row.company_id) if row.company_id and row.company_id.isdigit() else None,
        branch_id=int(row.branch_id) if row.branch_id and row.branch_id.isdigit() else None,
        mode=row.mode,
        fencing_epoch=row.fencing_epoch,
        lease_owner_device_id=row.lease_owner_device_id,
        lease_expires_at=row.lease_expires_at,
        last_heartbeat_at=row.last_heartbeat_at,
        last_cloud_contact_at=row.last_cloud_contact_at,
        last_reconciled_at=row.last_reconciled_at,
        last_queue_drain_at=row.last_queue_drain_at,
        snapshot_at=row.snapshot_at,
        pending_inbox=row.pending_inbox,
        pending_outbox=row.pending_outbox,
        dead_letter_count=row.dead_letter_count,
        attention_message=row.attention_message,
    )


def _invoice_scope_statement(scope: ScopeContext):
    statement = select(Invoice).where(Invoice.source_type.in_(list(CAFE_SOURCE_TYPES)))
    if not scope.all_companies and scope.company_id is not None:
        statement = statement.where(Invoice.company_id == scope.company_id)
    if scope.branch_ids:
        statement = statement.where(Invoice.branch_id.in_(scope.branch_ids))
    return statement.options(selectinload(Invoice.items), selectinload(Invoice.payments))


def run_reconciliation(
    db: Session,
    *,
    scope: ScopeContext,
    created_by: int | None = None,
    state: ContinuityState | None = None,
) -> ContinuityReconciliation:
    now = datetime.now(UTC)
    metrics_before = queue_metrics(db, scope)
    continuity = state or state_for_scope(db, scope)
    report = ContinuityReconciliation(
        reconciliation_reference=str(uuid4()),
        scope_key=continuity.scope_key,
        business_group_id=str(scope.business_group_id),
        company_id=None if scope.all_companies else (str(scope.company_id) if scope.company_id is not None else None),
        branch_id=str(scope.branch_ids[0]) if len(scope.branch_ids) == 1 else None,
        fencing_epoch=continuity.fencing_epoch,
        status=ContinuityReconciliationStatus.PENDING,
        pending_inbox_before=int(metrics_before["pending_inbox"] or 0),
        pending_outbox_before=int(metrics_before["pending_outbox"] or 0),
        created_by=created_by,
        started_at=now,
    )
    db.add(report)
    db.flush()

    invoices = list(db.scalars(_invoice_scope_statement(scope)).unique().all())
    invoice_by_id = {invoice.id: invoice for invoice in invoices}
    invoice_ids = list(invoice_by_id)

    invoice_mismatches: list[int] = []
    payment_mismatches: list[int] = []
    stock_mismatches: list[int] = []
    for invoice in invoices:
        expected_balance = Decimal(invoice.paid_amount) + Decimal(invoice.balance_due)
        if expected_balance != Decimal(invoice.grand_total):
            invoice_mismatches.append(invoice.id)
        cash_paid = sum(
            (Decimal(payment.amount) for payment in invoice.payments if not payment.is_credit_marker),
            Decimal("0.00"),
        )
        if cash_paid != Decimal(invoice.paid_amount):
            payment_mismatches.append(invoice.id)
        linked_items = [item for item in invoice.items if item.product_id is not None]
        if linked_items:
            movements = list(
                db.scalars(
                    select(StockMovement).where(
                        StockMovement.company_id == invoice.company_id,
                        StockMovement.branch_id == invoice.branch_id,
                        StockMovement.reference_type == "invoice",
                        StockMovement.reference_id == invoice.id,
                    )
                ).all()
            )
            movement_products = {movement.product_id for movement in movements}
            if any(item.product_id not in movement_products for item in linked_items):
                stock_mismatches.append(invoice.id)

    order_statement = select(CafeOrder)
    if not scope.all_companies and scope.company_id is not None:
        order_statement = order_statement.where(CafeOrder.company_id == scope.company_id)
    if scope.branch_ids:
        order_statement = order_statement.where(CafeOrder.branch_id.in_(scope.branch_ids))
    orders = list(db.scalars(order_statement).all())
    order_mismatches = [
        order.id
        for order in orders
        if order.status in {CafeOrderStatus.BILLED, CafeOrderStatus.CLOSED} and order.billed_invoice_id is None
    ]

    session_statement = select(TableSession)
    if not scope.all_companies and scope.company_id is not None:
        session_statement = session_statement.where(TableSession.company_id == scope.company_id)
    if scope.branch_ids:
        session_statement = session_statement.where(TableSession.branch_id.in_(scope.branch_ids))
    sessions = list(db.scalars(session_statement).all())
    closing_mismatches: list[int] = []
    for session in sessions:
        if session.status != TableSessionStatus.CLOSED or session.billed_invoice_id is None:
            continue
        invoice = invoice_by_id.get(session.billed_invoice_id)
        if invoice is None or Decimal(invoice.balance_due) != Decimal("0.00") or invoice.payment_status != InvoicePaymentStatus.PAID:
            closing_mismatches.append(session.id)

    metrics_after = queue_metrics(db, scope)
    unresolved_dead_letters = int(metrics_after["dead_letters"] or 0)
    receipt_mismatches = 0
    mismatch_total = (
        len(order_mismatches)
        + len(invoice_mismatches)
        + len(payment_mismatches)
        + len(stock_mismatches)
        + receipt_mismatches
        + len(closing_mismatches)
        + unresolved_dead_letters
    )
    report.order_mismatch_count = len(order_mismatches)
    report.invoice_mismatch_count = len(invoice_mismatches)
    report.payment_mismatch_count = len(payment_mismatches)
    report.stock_mismatch_count = len(stock_mismatches)
    report.queue_receipt_mismatch_count = receipt_mismatches
    report.closing_mismatch_count = len(closing_mismatches)
    report.dead_letter_count = unresolved_dead_letters
    report.pending_inbox_after = int(metrics_after["pending_inbox"] or 0)
    report.pending_outbox_after = int(metrics_after["pending_outbox"] or 0)
    report.status = (
        ContinuityReconciliationStatus.CLEAN
        if mismatch_total == 0
        else ContinuityReconciliationStatus.ATTENTION_REQUIRED
    )
    report.details_json = {
        "order_ids": order_mismatches,
        "invoice_ids": invoice_mismatches,
        "payment_invoice_ids": payment_mismatches,
        "stock_invoice_ids": stock_mismatches,
        "closing_session_ids": closing_mismatches,
        "checked_invoice_count": len(invoices),
        "checked_order_count": len(orders),
        "checked_session_count": len(sessions),
    }
    report.completed_at = now
    continuity.last_reconciled_at = now
    continuity.snapshot_at = now
    refresh_state_metrics(
        db,
        state=continuity,
        metrics=metrics_after,
        mode=(ContinuityMode.LIVE if report.status == ContinuityReconciliationStatus.CLEAN else ContinuityMode.ATTENTION_REQUIRED),
        attention_message=(None if report.status == ContinuityReconciliationStatus.CLEAN else "Continuity reconciliation requires attention."),
        now=now,
    )
    db.flush()
    return report


def reconciliation_read(row: ContinuityReconciliation) -> ReconciliationRead:
    return ReconciliationRead(
        reconciliation_reference=row.reconciliation_reference,
        scope_key=row.scope_key,
        fencing_epoch=row.fencing_epoch,
        status=row.status,
        pending_inbox_before=row.pending_inbox_before,
        pending_outbox_before=row.pending_outbox_before,
        pending_inbox_after=row.pending_inbox_after,
        pending_outbox_after=row.pending_outbox_after,
        order_mismatch_count=row.order_mismatch_count,
        invoice_mismatch_count=row.invoice_mismatch_count,
        payment_mismatch_count=row.payment_mismatch_count,
        stock_mismatch_count=row.stock_mismatch_count,
        queue_receipt_mismatch_count=row.queue_receipt_mismatch_count,
        closing_mismatch_count=row.closing_mismatch_count,
        dead_letter_count=row.dead_letter_count,
        details=row.details_json or {},
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def latest_reconciliation(db: Session, scope: ScopeContext) -> ContinuityReconciliation | None:
    key = scope_key_from_scope(scope)
    return db.scalar(
        select(ContinuityReconciliation)
        .where(ContinuityReconciliation.scope_key == key)
        .order_by(ContinuityReconciliation.created_at.desc(), ContinuityReconciliation.id.desc())
        .limit(1)
    )


def make_continuity_reference_handler(device_id: str):
    def handle(db: Session, event: EventEnvelope) -> dict[str, object]:
        payload = event.payload or {}
        reference = str(payload.get("continuity_reference", ""))
        if not reference:
            raise PermanentSyncError("Continuity reference is missing.", code="continuity_reference_missing")
        epoch = int(payload.get("fencing_epoch", -1))
        key = str(payload.get("scope_key", ""))
        state = db.scalar(select(ContinuityState).where(ContinuityState.scope_key == key).with_for_update())
        if state is None:
            state = ContinuityState(
                scope_key=key,
                business_group_id=str(event.business_group_id or ""),
                company_id=str(event.company_id) if event.company_id is not None else None,
                branch_id=str(event.branch_id) if event.branch_id is not None else None,
                mode=ContinuityMode.SYNCHRONIZING,
                fencing_epoch=epoch,
            )
            db.add(state)
            db.flush()
        if epoch != state.fencing_epoch:
            raise PermanentSyncError(
                f"Continuity fencing epoch {epoch} is stale; current epoch is {state.fencing_epoch}.",
                code="stale_fencing_epoch",
            )
        canonical_payload = payload.get("payload") or {}
        payload_hash = hashlib.sha256(
            json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()
        existing = db.scalar(
            select(ContinuityTransactionReceipt).where(
                ContinuityTransactionReceipt.continuity_reference == reference
            )
        )
        if existing is not None:
            if existing.payload_hash != payload_hash or existing.fencing_epoch != epoch:
                raise PermanentSyncError(
                    "Continuity reference was replayed with different content.",
                    code="continuity_reference_conflict",
                )
            return {"continuity_reference": reference, "status": existing.status.value, "duplicate": True}
        receipt = ContinuityTransactionReceipt(
            continuity_reference=reference,
            scope_key=key,
            business_group_id=str(event.business_group_id or ""),
            company_id=str(event.company_id) if event.company_id is not None else None,
            branch_id=str(event.branch_id) if event.branch_id is not None else None,
            purpose=str(payload.get("purpose", "unknown"))[:80],
            fencing_epoch=epoch,
            status=ContinuityTransactionStatus.PENDING_RECONCILIATION,
            source_device_id=device_id,
            payload_hash=payload_hash,
            details_json={"cloud_event_id": str(event.event_id)},
        )
        db.add(receipt)
        db.flush()
        return {"continuity_reference": reference, "status": receipt.status.value, "duplicate": False}

    return handle
