from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CafeOrder, CloudRecordLink, TableSession, TableSessionStatus
from app.schemas.sync import EventEnvelope, EventSource
from app.sync.service import PermanentSyncError, RetryableSyncError


def apply_cloud_bill_request(db: Session, event: EventEnvelope) -> dict[str, object]:
    """Apply a durable cloud guest bill request without creating financial effects.

    The cloud command only moves the Local Hub table session to BILL_REQUESTED.
    Invoice/payment/ledger/stock work remains exclusively in the normal Local Hub
    billing transaction. Bill requests use their own aggregate so they cannot
    collide with Cafe order import/status aggregate versions.
    """

    if event.event_type != "cafe.bill.requested" or event.aggregate_type != "cafe_bill_request":
        raise PermanentSyncError("Unsupported Cafe cloud bill request event.", code="unsupported_event")
    if event.source != EventSource.CLOUD_GATEWAY:
        raise PermanentSyncError("Cafe cloud bill request has an invalid source.", code="invalid_source")

    cloud_order_public_id = str(event.payload.get("cloud_order_public_id") or "")
    if not cloud_order_public_id:
        raise PermanentSyncError("Cloud bill request is missing its order reference.", code="order_reference_missing")

    link = db.scalar(
        select(CloudRecordLink).where(
            CloudRecordLink.provider == "cloud_gateway",
            CloudRecordLink.aggregate_type == "cafe_order",
            CloudRecordLink.cloud_record_id == cloud_order_public_id,
        )
    )
    if link is None:
        # The bill request has an independent aggregate and can safely retry
        # until the associated order import has committed its identity link.
        raise RetryableSyncError(
            "Cloud Cafe order has not been imported locally yet.",
            code="order_import_pending",
        )

    order = db.get(CafeOrder, link.local_record_id, execution_options={"scope_bypass": True})
    if order is None:
        raise PermanentSyncError("Linked Local Hub Cafe order is missing.", code="local_order_missing")
    if str(order.company_id) != str(event.company_id) or str(order.branch_id) != str(event.branch_id):
        raise PermanentSyncError("Cloud bill request scope does not match Local Hub order.", code="scope_mismatch")
    if order.table_session_id is None:
        raise PermanentSyncError("Cloud bill request is not attached to a table session.", code="session_missing")

    session = db.scalar(
        select(TableSession)
        .where(TableSession.id == order.table_session_id)
        .with_for_update()
        .execution_options(scope_bypass=True)
    )
    if session is None:
        raise PermanentSyncError("Cafe table session is missing.", code="session_missing")
    if str(session.company_id) != str(event.company_id) or str(session.branch_id) != str(event.branch_id):
        raise PermanentSyncError("Cloud bill request scope does not match table session.", code="scope_mismatch")

    if session.status == TableSessionStatus.BILL_REQUESTED:
        return {
            "status": "already_requested",
            "session_public_id": session.public_id,
            "bill_requested_at": session.bill_requested_at.isoformat() if session.bill_requested_at else None,
        }
    if session.status != TableSessionStatus.OPEN:
        raise PermanentSyncError(
            "This Cafe table session cannot accept a bill request.",
            code="session_not_open",
        )

    now = datetime.now(UTC)
    session.status = TableSessionStatus.BILL_REQUESTED
    session.bill_requested_at = now
    session.version += 1
    db.flush()
    return {
        "status": "bill_requested",
        "session_public_id": session.public_id,
        "bill_requested_at": now.isoformat(),
    }


def make_cloud_bill_request_handler():
    def handler(db: Session, event: EventEnvelope) -> dict[str, object]:
        return apply_cloud_bill_request(db, event)

    return handler
