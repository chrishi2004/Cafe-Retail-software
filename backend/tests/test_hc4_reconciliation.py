from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    AuditLog,
    ContinuityMode,
    ContinuityReconciliationStatus,
    ContinuityState,
    Invoice,
    SyncDeadLetter,
    SyncOutbox,
)
from app.schemas.sync import EventEnvelope, EventSource
from app.services.continuity import scope_key
from app.sync.service import PermanentSyncError, enqueue_outbox_event, process_outbox_batch
from tests.p7_fixtures import cafe_headers
from tests.p8_fixtures import create_mixed_served_table_orders, seed_p8


class RejectingTransport:
    def send(self, _event):
        raise PermanentSyncError("invalid downstream command", code="hc4_permanent_test")


def _bill_clean_table(client, db_session_factory: sessionmaker[Session]):
    ids = seed_p8(db_session_factory)
    create_mixed_served_table_orders(client, ids)
    headers = cafe_headers(client, "order_taker")
    quote = client.get(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/quote",
        headers=headers,
    )
    assert quote.status_code == 200, quote.text
    body = quote.json()
    billed = client.post(
        f"/api/cafe/billing/table-sessions/{ids['table_session_public_id']}/bill",
        headers={**headers, "Idempotency-Key": "hc4-clean-bill-0001"},
        json={
            "expected_version": body["source_version"],
            "payments": [{"payment_mode_id": ids["cash_mode"], "amount": body["grand_total"]}],
        },
    )
    assert billed.status_code == 200, billed.text
    return ids, billed.json()


def test_clean_recovery_reconciliation_covers_billing_payment_stock_and_close(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    _ids, _ = _bill_clean_table(client, db_session_factory)
    response = client.post("/api/sync/reconcile", headers=cafe_headers(client, "manager"))
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["status"] == ContinuityReconciliationStatus.CLEAN.value
    assert report["order_mismatch_count"] == 0
    assert report["invoice_mismatch_count"] == 0
    assert report["payment_mismatch_count"] == 0
    assert report["stock_mismatch_count"] == 0
    assert report["closing_mismatch_count"] == 0
    assert report["dead_letter_count"] == 0

    status = client.get("/api/sync/status", headers=cafe_headers(client, "manager"))
    assert status.status_code == 200
    assert status.json()["continuity_mode"] == ContinuityMode.OFFLINE_LOCAL.value
    assert status.json()["reconciliation_status"] == "clean"


def test_stale_heartbeat_or_expired_lease_is_reported_visibly(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p8(db_session_factory)
    key = scope_key(
        business_group_id="1",
        company_id=str(ids["cafe_company"]),
        branch_id=str(ids["cafe_branch"]),
    )
    with db_session_factory() as db:
        db.add(
            ContinuityState(
                scope_key=key,
                business_group_id="1",
                company_id=str(ids["cafe_company"]),
                branch_id=str(ids["cafe_branch"]),
                mode=ContinuityMode.LIVE,
                fencing_epoch=4,
                last_heartbeat_at=datetime.now(UTC) - timedelta(hours=1),
                lease_expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        db.commit()

    headers = cafe_headers(client, "manager")
    status = client.get("/api/sync/status", headers=headers)
    assert status.status_code == 200, status.text
    assert status.json()["continuity_mode"] == ContinuityMode.STALE.value
    assert status.json()["attention_message"]

    detail = client.get("/api/sync/continuity", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["mode"] == ContinuityMode.STALE.value


def test_injected_financial_mismatch_is_visible_attention_required(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    _ids, billed = _bill_clean_table(client, db_session_factory)
    invoice_id = billed["receipt"]["invoice_id"]
    with db_session_factory() as db:
        invoice = db.get(Invoice, invoice_id)
        assert invoice is not None
        invoice.paid_amount = Decimal("1.00")
        db.commit()

    response = client.post("/api/sync/reconcile", headers=cafe_headers(client, "manager"))
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["status"] == "attention_required"
    assert report["invoice_mismatch_count"] >= 1
    assert report["payment_mismatch_count"] >= 1

    state = client.get("/api/sync/continuity", headers=cafe_headers(client, "manager"))
    assert state.status_code == 200
    assert state.json()["mode"] == "attention_required"
    assert state.json()["attention_message"]


def test_dead_letter_is_visible_and_manual_retry_is_audited(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    ids = seed_p8(db_session_factory)
    event = EventEnvelope(
        event_type="hc4.permanent.failure",
        source=EventSource.LOCAL_HUB,
        source_device_id="hc4-device",
        business_group_id="1",
        company_id=str(ids["cafe_company"]),
        branch_id=str(ids["cafe_branch"]),
        aggregate_type="hc4_test",
        aggregate_id="dead-letter-1",
        aggregate_version=1,
        payload={"safe": True},
    )
    with db_session_factory() as db:
        with db.begin():
            enqueue_outbox_event(db, event)
    result = process_outbox_batch(
        db_session_factory,
        RejectingTransport(),
        limit=10,
        max_attempts=1,
        jitter_ratio=0,
    )
    assert result.dead_lettered == 1

    headers = cafe_headers(client, "manager")
    listed = client.get("/api/sync/dead-letters", headers=headers)
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1
    dead_letter_id = listed.json()[0]["id"]

    retried = client.post(f"/api/sync/dead-letters/{dead_letter_id}/retry", headers=headers)
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "retry_pending"

    with db_session_factory() as db:
        dead = db.get(SyncDeadLetter, dead_letter_id)
        assert dead is not None and dead.retry_count == 1
        outbox = db.scalar(select(SyncOutbox).where(SyncOutbox.event_id == str(event.event_id)))
        assert outbox is not None and outbox.status.value == "retry"
        audit = db.scalar(
            select(AuditLog).where(AuditLog.action == "sync.dead_letter.retry").order_by(AuditLog.id.desc())
        )
        assert audit is not None
