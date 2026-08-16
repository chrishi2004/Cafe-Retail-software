from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models import AuditLog, Branch
from app.models.sync import (
    SyncCheckpoint,
    SyncDeadLetter,
    SyncDeadLetterStatus,
    SyncDevice,
    SyncInbox,
    SyncInboxStatus,
    SyncOutbox,
)
from app.schemas.sync import EventEnvelope, EventSource
from app.sync.device import DeviceIdentityStore
from app.sync.service import (
    PermanentSyncError,
    consume_incoming_event,
    enqueue_outbox_event,
    process_inbox_batch,
    retry_dead_letter,
    retry_delay_seconds,
    stage_inbox_event,
)
from app.sync.worker import LocalSyncWorker


def make_event(
    *,
    event_type: str = "test.aggregate.changed",
    aggregate_id: str = "aggregate-1",
    aggregate_version: int = 1,
    schema_version: int = 1,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid4(),
        event_type=event_type,
        schema_version=schema_version,
        source=EventSource.CLOUD_GATEWAY,
        aggregate_type="test_aggregate",
        aggregate_id=aggregate_id,
        aggregate_version=aggregate_version,
        payload={"value": aggregate_version},
    )


def audit_effect_handler(db: Session, event: EventEnvelope) -> dict[str, int]:
    row = AuditLog(
        action="sync.test.business_effect",
        entity_type="sync_test",
        new_value_json={"event_id": str(event.event_id), "version": event.aggregate_version},
    )
    db.add(row)
    db.flush()
    return {"audit_log_id": row.id}


def test_outbox_record_commits_with_domain_change(
    db_session_factory: sessionmaker[Session],
) -> None:
    event = EventEnvelope(
        event_type="branch.created",
        source=EventSource.LOCAL_HUB,
        aggregate_type="branch",
        aggregate_id="central",
        aggregate_version=1,
        payload={"name": "Central"},
    )

    with db_session_factory() as db:
        with db.begin():
            db.add(Branch(name="Central"))
            enqueue_outbox_event(db, event)

    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Branch)) == 1
        assert db.scalar(select(func.count()).select_from(SyncOutbox)) == 1


def test_domain_rollback_also_rolls_back_outbox(
    db_session_factory: sessionmaker[Session],
) -> None:
    event = EventEnvelope(
        event_type="branch.created",
        source=EventSource.LOCAL_HUB,
        aggregate_type="branch",
        aggregate_id="rolled-back",
        aggregate_version=1,
        payload={"name": "Rolled Back"},
    )

    with db_session_factory() as db:
        db.add(Branch(name="Rolled Back"))
        enqueue_outbox_event(db, event)
        db.rollback()

    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Branch)) == 0
        assert db.scalar(select(func.count()).select_from(SyncOutbox)) == 0


def test_duplicate_delivery_creates_one_business_effect(
    db_session_factory: sessionmaker[Session],
) -> None:
    event = make_event()

    first = consume_incoming_event(
        db_session_factory,
        event,
        audit_effect_handler,
        jitter_ratio=0,
    )
    second = consume_incoming_event(
        db_session_factory,
        event,
        audit_effect_handler,
        jitter_ratio=0,
    )

    assert first.status == SyncInboxStatus.PROCESSED.value
    assert second.status == SyncInboxStatus.PROCESSED.value
    assert second.duplicate is True
    assert second.result == first.result

    with db_session_factory() as db:
        effect_count = db.scalar(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.action == "sync.test.business_effect"
            )
        )
        assert effect_count == 1


def test_lost_acknowledgment_redelivery_returns_durable_receipt(
    db_session_factory: sessionmaker[Session],
) -> None:
    event = make_event(aggregate_id="lost-ack")

    committed_result = consume_incoming_event(
        db_session_factory,
        event,
        audit_effect_handler,
        jitter_ratio=0,
    )
    # Simulate the response being lost after the database commit. The producer sends the same event again.
    redelivered = consume_incoming_event(
        db_session_factory,
        event,
        audit_effect_handler,
        jitter_ratio=0,
    )

    assert redelivered.duplicate is True
    assert redelivered.result == committed_result.result
    with db_session_factory() as db:
        assert db.scalar(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.action == "sync.test.business_effect"
            )
        ) == 1


def test_restart_resumes_from_persisted_checkpoint(
    db_session_factory: sessionmaker[Session],
) -> None:
    first_event = make_event(aggregate_id="restart-a")
    second_event = make_event(aggregate_id="restart-b")
    with db_session_factory() as db:
        with db.begin():
            stage_inbox_event(db, first_event)
            stage_inbox_event(db, second_event)

    worker_settings = Settings(
        _env_file=None,
        sync_batch_size=1,
        sync_poll_interval_seconds=0.1,
        sync_retry_jitter_ratio=0,
    )
    worker_one = LocalSyncWorker(
        session_factory=db_session_factory,
        configured_settings=worker_settings,
        handlers={"test.aggregate.changed": audit_effect_handler},
    )
    first_device_id = worker_one.initialize()
    first_cycle = worker_one.run_once()
    assert first_cycle.inbound.processed == 1

    with db_session_factory() as db:
        checkpoint = db.scalar(
            select(SyncCheckpoint).where(SyncCheckpoint.stream_name == "inbound")
        )
        assert checkpoint is not None
        first_checkpoint = checkpoint.checkpoint_value

    # New process object, same database. It must reuse device identity and continue the pending queue.
    worker_two = LocalSyncWorker(
        session_factory=db_session_factory,
        configured_settings=worker_settings,
        handlers={"test.aggregate.changed": audit_effect_handler},
    )
    second_device_id = worker_two.initialize()
    second_cycle = worker_two.run_once()
    assert second_cycle.inbound.processed == 1
    assert second_device_id == first_device_id

    with db_session_factory() as db:
        checkpoint = db.scalar(
            select(SyncCheckpoint).where(SyncCheckpoint.stream_name == "inbound")
        )
        assert checkpoint is not None
        assert checkpoint.checkpoint_value != first_checkpoint
        assert db.scalar(select(func.count()).select_from(SyncInbox).where(
            SyncInbox.status == SyncInboxStatus.PROCESSED
        )) == 2


def test_future_aggregate_version_waits_then_applies_after_missing_version(
    db_session_factory: sessionmaker[Session],
) -> None:
    future_event = make_event(aggregate_id="ordered", aggregate_version=2)
    with db_session_factory() as db:
        with db.begin():
            stage_inbox_event(db, future_event)

    first_batch = process_inbox_batch(
        db_session_factory,
        {"test.aggregate.changed": audit_effect_handler},
        limit=10,
        base_delay_seconds=1,
        max_delay_seconds=5,
        jitter_ratio=0,
    )
    assert first_batch.blocked == 1

    with db_session_factory() as db:
        blocked = db.scalar(select(SyncInbox).where(SyncInbox.event_id == str(future_event.event_id)))
        assert blocked is not None
        assert blocked.status == SyncInboxStatus.BLOCKED
        assert blocked.last_error_code == "aggregate_version_gap"

    missing_event = make_event(aggregate_id="ordered", aggregate_version=1)
    missing_result = consume_incoming_event(
        db_session_factory,
        missing_event,
        audit_effect_handler,
        jitter_ratio=0,
    )
    assert missing_result.status == SyncInboxStatus.PROCESSED.value

    later = datetime.now(UTC) + timedelta(seconds=10)
    final_batch = process_inbox_batch(
        db_session_factory,
        {"test.aggregate.changed": audit_effect_handler},
        limit=10,
        base_delay_seconds=1,
        max_delay_seconds=5,
        jitter_ratio=0,
        now=later,
    )
    assert final_batch.processed == 1

    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "sync.test.business_effect"
        )) == 2


def test_dead_letter_retry_is_audited(
    db_session_factory: sessionmaker[Session],
) -> None:
    event = make_event(aggregate_id="dead-letter")

    def fail_permanently(_db: Session, _event: EventEnvelope) -> dict[str, int]:
        raise PermanentSyncError("invalid scope", code="invalid_scope")

    result = consume_incoming_event(
        db_session_factory,
        event,
        fail_permanently,
        jitter_ratio=0,
    )
    assert result.status == SyncInboxStatus.DEAD_LETTER.value

    with db_session_factory() as db:
        dead_letter = db.scalar(select(SyncDeadLetter))
        assert dead_letter is not None
        dead_letter_id = dead_letter.id

    with db_session_factory() as db:
        with db.begin():
            retried = retry_dead_letter(db, dead_letter_id)
            assert retried.status == SyncDeadLetterStatus.RETRY_PENDING

    with db_session_factory() as db:
        dead_letter = db.get(SyncDeadLetter, dead_letter_id)
        inbox = db.scalar(select(SyncInbox).where(SyncInbox.event_id == str(event.event_id)))
        audit = db.scalar(
            select(AuditLog).where(AuditLog.action == "sync.dead_letter.retry")
        )
        assert dead_letter is not None and dead_letter.retry_count == 1
        assert inbox is not None and inbox.status == SyncInboxStatus.PENDING
        assert audit is not None
        assert audit.new_value_json["event_id"] == str(event.event_id)


def test_unknown_future_schema_fails_visibly(
    db_session_factory: sessionmaker[Session],
) -> None:
    event = make_event(aggregate_id="future-schema", schema_version=2)
    result = consume_incoming_event(
        db_session_factory,
        event,
        audit_effect_handler,
        jitter_ratio=0,
    )
    assert result.status == SyncInboxStatus.DEAD_LETTER.value

    with db_session_factory() as db:
        dead_letter = db.scalar(select(SyncDeadLetter))
        assert dead_letter is not None
        assert dead_letter.error_code == "unsupported_schema_version"


def test_device_secret_is_not_persisted(
    db_session_factory: sessionmaker[Session],
) -> None:
    configured = Settings(
        _env_file=None,
        sync_device_secret=SecretStr("top-secret-device-value"),
        sync_device_credential_ref="env:SYNC_DEVICE_SECRET",
    )
    store = DeviceIdentityStore(configured)

    with db_session_factory() as db:
        with db.begin():
            identity = store.get_or_create(db)

    with db_session_factory() as db:
        device = db.scalar(select(SyncDevice).where(SyncDevice.device_id == identity.device_id))
        assert device is not None
        assert device.credential_ref == "env:SYNC_DEVICE_SECRET"
        assert "top-secret-device-value" not in repr(device.__dict__)


def test_retry_backoff_is_bounded_and_honors_retry_after() -> None:
    assert retry_delay_seconds(
        1,
        base_delay_seconds=2,
        max_delay_seconds=30,
        jitter_ratio=0,
    ) == 2
    assert retry_delay_seconds(
        10,
        base_delay_seconds=2,
        max_delay_seconds=30,
        jitter_ratio=0,
    ) == 30
    assert retry_delay_seconds(
        1,
        base_delay_seconds=2,
        max_delay_seconds=30,
        jitter_ratio=0.5,
        retry_after_seconds=12,
    ) == 12
