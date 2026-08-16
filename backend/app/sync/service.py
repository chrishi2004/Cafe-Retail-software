from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Protocol

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.sync import (
    SyncAggregateVersion,
    SyncCheckpoint,
    SyncDeadLetter,
    SyncDeadLetterStatus,
    SyncDirection,
    SyncInbox,
    SyncInboxStatus,
    SyncOutbox,
    SyncOutboxStatus,
)
from app.schemas.sync import CURRENT_EVENT_SCHEMA_VERSION, EventEnvelope
from app.services.audit import write_audit_log


class SyncHandler(Protocol):
    def __call__(self, db: Session, event: EventEnvelope) -> dict[str, Any] | None:
        ...


class SyncTransport(Protocol):
    def send(self, event: EventEnvelope) -> dict[str, Any] | None:
        ...


class SyncProcessingError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        retryable: bool,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


class RetryableSyncError(SyncProcessingError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "retryable_error",
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            retryable=True,
            retry_after_seconds=retry_after_seconds,
        )


class PermanentSyncError(SyncProcessingError):
    def __init__(self, message: str, *, code: str = "permanent_error") -> None:
        super().__init__(message, code=code, retryable=False)


class AggregateVersionGap(RetryableSyncError):
    def __init__(self, current_version: int, received_version: int) -> None:
        super().__init__(
            f"Aggregate is at version {current_version}; received future version {received_version}.",
            code="aggregate_version_gap",
        )
        self.current_version = current_version
        self.received_version = received_version


@dataclass(frozen=True)
class ConsumeResult:
    event_id: str
    status: str
    result: dict[str, Any] | None = None
    duplicate: bool = False


@dataclass(frozen=True)
class BatchResult:
    attempted: int = 0
    processed: int = 0
    retried: int = 0
    blocked: int = 0
    dead_lettered: int = 0


def hash_idempotency_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def parse_retry_after(value: str | None, *, now: datetime | None = None) -> float | None:
    """Parse Retry-After seconds or an HTTP date into a non-negative delay."""
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.isdigit():
        return max(0.0, float(cleaned))
    try:
        target = parsedate_to_datetime(cleaned)
    except (TypeError, ValueError, OverflowError):
        return None
    if target.tzinfo is None:
        target = target.replace(tzinfo=UTC)
    current = now or datetime.now(UTC)
    return max(0.0, (target.astimezone(UTC) - current.astimezone(UTC)).total_seconds())


def retry_delay_seconds(
    attempt_number: int,
    *,
    base_delay_seconds: float,
    max_delay_seconds: float,
    jitter_ratio: float,
    retry_after_seconds: float | None = None,
) -> float:
    if retry_after_seconds is not None:
        return min(max_delay_seconds, max(0.0, retry_after_seconds))
    exponent = max(0, attempt_number - 1)
    bounded = min(max_delay_seconds, base_delay_seconds * (2**exponent))
    jitter = bounded * max(0.0, jitter_ratio)
    if jitter == 0:
        return bounded
    return max(0.0, min(max_delay_seconds, bounded + random.uniform(-jitter, jitter)))


def _event_values(event: EventEnvelope) -> dict[str, Any]:
    return {
        "event_id": str(event.event_id),
        "event_type": event.event_type,
        "schema_version": event.schema_version,
        "source": event.source.value,
        "source_device_id": event.source_device_id,
        "business_group_id": str(event.business_group_id) if event.business_group_id is not None else None,
        "company_id": str(event.company_id) if event.company_id is not None else None,
        "branch_id": str(event.branch_id) if event.branch_id is not None else None,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "aggregate_version": event.aggregate_version,
        "idempotency_key_hash": event.idempotency_key_hash,
        "occurred_at": event.occurred_at,
        "recorded_at": event.recorded_at,
        "correlation_id": str(event.correlation_id),
        "causation_id": str(event.causation_id) if event.causation_id is not None else None,
        "payload_json": event.payload,
    }


def _event_from_record(record: SyncInbox | SyncOutbox) -> EventEnvelope:
    return EventEnvelope(
        event_id=record.event_id,
        event_type=record.event_type,
        schema_version=record.schema_version,
        source=record.source,
        source_device_id=record.source_device_id,
        business_group_id=record.business_group_id,
        company_id=record.company_id,
        branch_id=record.branch_id,
        aggregate_type=record.aggregate_type,
        aggregate_id=record.aggregate_id,
        aggregate_version=record.aggregate_version,
        idempotency_key_hash=record.idempotency_key_hash,
        occurred_at=record.occurred_at,
        recorded_at=record.recorded_at,
        correlation_id=record.correlation_id,
        causation_id=record.causation_id,
        payload=record.payload_json or {},
    )


def enqueue_outbox_event(db: Session, event: EventEnvelope) -> SyncOutbox:
    """Insert an outbox row in the caller's transaction. This function never commits."""
    event_id = str(event.event_id)
    existing = db.scalar(select(SyncOutbox).where(SyncOutbox.event_id == event_id))
    if existing is not None:
        return existing
    row = SyncOutbox(**_event_values(event), status=SyncOutboxStatus.PENDING)
    db.add(row)
    db.flush()
    return row


def stage_inbox_event(db: Session, event: EventEnvelope) -> SyncInbox:
    """Durably stage an inbound envelope in the caller's transaction without applying effects."""
    event_id = str(event.event_id)
    existing = db.scalar(select(SyncInbox).where(SyncInbox.event_id == event_id))
    if existing is not None:
        return existing
    row = SyncInbox(**_event_values(event), status=SyncInboxStatus.PENDING)
    db.add(row)
    db.flush()
    return row


def _update_checkpoint(
    db: Session,
    *,
    stream_name: str,
    checkpoint_value: str,
    event_id: str,
    now: datetime,
) -> SyncCheckpoint:
    checkpoint = db.scalar(
        select(SyncCheckpoint).where(SyncCheckpoint.stream_name == stream_name).with_for_update()
    )
    if checkpoint is None:
        checkpoint = SyncCheckpoint(stream_name=stream_name)
        db.add(checkpoint)
    checkpoint.checkpoint_value = checkpoint_value
    checkpoint.last_event_id = event_id
    checkpoint.last_success_at = now
    db.flush()
    return checkpoint


def _upsert_dead_letter(
    db: Session,
    *,
    direction: SyncDirection,
    record: SyncInbox | SyncOutbox,
    error: SyncProcessingError,
    now: datetime,
) -> SyncDeadLetter:
    dead_letter = db.scalar(
        select(SyncDeadLetter)
        .where(
            SyncDeadLetter.direction == direction,
            SyncDeadLetter.event_id == record.event_id,
        )
        .with_for_update()
    )
    envelope = _event_from_record(record)
    if dead_letter is None:
        dead_letter = SyncDeadLetter(
            direction=direction,
            event_id=record.event_id,
            correlation_id=record.correlation_id,
            event_envelope_json=envelope.storage_payload(),
            error_code=error.code,
            error_message=str(error),
            retryable=error.retryable,
            status=SyncDeadLetterStatus.OPEN,
            last_failed_at=now,
        )
        db.add(dead_letter)
    else:
        dead_letter.event_envelope_json = envelope.storage_payload()
        dead_letter.error_code = error.code
        dead_letter.error_message = str(error)
        dead_letter.retryable = error.retryable
        dead_letter.status = SyncDeadLetterStatus.OPEN
        dead_letter.last_failed_at = now
        dead_letter.resolved_at = None
    db.flush()
    return dead_letter


def _schedule_inbox_failure(
    db: Session,
    record: SyncInbox,
    error: SyncProcessingError,
    *,
    now: datetime,
    max_attempts: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    jitter_ratio: float,
    blocked: bool = False,
) -> str:
    record.attempt_count += 1
    record.last_error_code = error.code
    record.last_error_message = str(error)

    if not error.retryable or record.attempt_count >= max_attempts:
        record.status = SyncInboxStatus.DEAD_LETTER
        record.next_attempt_at = None
        _upsert_dead_letter(
            db,
            direction=SyncDirection.INBOUND,
            record=record,
            error=error,
            now=now,
        )
        return SyncInboxStatus.DEAD_LETTER.value

    delay = retry_delay_seconds(
        record.attempt_count,
        base_delay_seconds=base_delay_seconds,
        max_delay_seconds=max_delay_seconds,
        jitter_ratio=jitter_ratio,
        retry_after_seconds=error.retry_after_seconds,
    )
    record.status = SyncInboxStatus.BLOCKED if blocked else SyncInboxStatus.RETRY
    record.next_attempt_at = now + timedelta(seconds=delay)
    db.flush()
    return record.status.value


def _schedule_outbox_failure(
    db: Session,
    record: SyncOutbox,
    error: SyncProcessingError,
    *,
    now: datetime,
    max_attempts: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    jitter_ratio: float,
) -> str:
    record.attempt_count += 1
    record.last_error_code = error.code
    record.last_error_message = str(error)

    if not error.retryable or record.attempt_count >= max_attempts:
        record.status = SyncOutboxStatus.DEAD_LETTER
        record.next_attempt_at = None
        _upsert_dead_letter(
            db,
            direction=SyncDirection.OUTBOUND,
            record=record,
            error=error,
            now=now,
        )
        return SyncOutboxStatus.DEAD_LETTER.value

    delay = retry_delay_seconds(
        record.attempt_count,
        base_delay_seconds=base_delay_seconds,
        max_delay_seconds=max_delay_seconds,
        jitter_ratio=jitter_ratio,
        retry_after_seconds=error.retry_after_seconds,
    )
    record.status = SyncOutboxStatus.RETRY
    record.next_attempt_at = now + timedelta(seconds=delay)
    db.flush()
    return record.status.value


def _apply_inbox_record(
    db: Session,
    record: SyncInbox,
    handler: SyncHandler | None,
    *,
    now: datetime,
    max_attempts: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    jitter_ratio: float,
) -> ConsumeResult:
    if record.status == SyncInboxStatus.PROCESSED:
        return ConsumeResult(
            event_id=record.event_id,
            status=SyncInboxStatus.PROCESSED.value,
            result=record.result_json,
            duplicate=True,
        )
    if record.status == SyncInboxStatus.DEAD_LETTER:
        return ConsumeResult(event_id=record.event_id, status=SyncInboxStatus.DEAD_LETTER.value)

    if record.schema_version != CURRENT_EVENT_SCHEMA_VERSION:
        error = PermanentSyncError(
            f"Unsupported event schema version {record.schema_version}.",
            code="unsupported_schema_version",
        )
        _schedule_inbox_failure(
            db,
            record,
            error,
            now=now,
            max_attempts=max_attempts,
            base_delay_seconds=base_delay_seconds,
            max_delay_seconds=max_delay_seconds,
            jitter_ratio=jitter_ratio,
        )
        return ConsumeResult(event_id=record.event_id, status=record.status.value)

    if handler is None:
        error = PermanentSyncError(
            f"No local handler is registered for event type {record.event_type!r}.",
            code="handler_not_registered",
        )
        _schedule_inbox_failure(
            db,
            record,
            error,
            now=now,
            max_attempts=max_attempts,
            base_delay_seconds=base_delay_seconds,
            max_delay_seconds=max_delay_seconds,
            jitter_ratio=jitter_ratio,
        )
        return ConsumeResult(event_id=record.event_id, status=record.status.value)

    aggregate = db.scalar(
        select(SyncAggregateVersion)
        .where(
            SyncAggregateVersion.aggregate_type == record.aggregate_type,
            SyncAggregateVersion.aggregate_id == record.aggregate_id,
        )
        .with_for_update()
    )
    if aggregate is None:
        aggregate = SyncAggregateVersion(
            aggregate_type=record.aggregate_type,
            aggregate_id=record.aggregate_id,
            last_applied_version=0,
        )
        db.add(aggregate)
        db.flush()

    current_version = aggregate.last_applied_version
    if record.aggregate_version > current_version + 1:
        error = AggregateVersionGap(current_version, record.aggregate_version)
        _schedule_inbox_failure(
            db,
            record,
            error,
            now=now,
            max_attempts=max_attempts,
            base_delay_seconds=base_delay_seconds,
            max_delay_seconds=max_delay_seconds,
            jitter_ratio=jitter_ratio,
            blocked=True,
        )
        return ConsumeResult(event_id=record.event_id, status=record.status.value)

    if record.aggregate_version == current_version:
        if aggregate.last_event_id == record.event_id:
            record.status = SyncInboxStatus.PROCESSED
            record.processed_at = now
            record.result_json = record.result_json or {"status": "already_applied"}
            record.next_attempt_at = None
            db.flush()
            return ConsumeResult(
                event_id=record.event_id,
                status=SyncInboxStatus.PROCESSED.value,
                result=record.result_json,
                duplicate=True,
            )
        error = PermanentSyncError(
            "A different event already committed this aggregate version.",
            code="aggregate_version_conflict",
        )
        _schedule_inbox_failure(
            db,
            record,
            error,
            now=now,
            max_attempts=max_attempts,
            base_delay_seconds=base_delay_seconds,
            max_delay_seconds=max_delay_seconds,
            jitter_ratio=jitter_ratio,
        )
        return ConsumeResult(event_id=record.event_id, status=record.status.value)

    if record.aggregate_version < current_version:
        record.status = SyncInboxStatus.PROCESSED
        record.processed_at = now
        record.result_json = {
            "status": "superseded",
            "last_applied_version": current_version,
        }
        record.next_attempt_at = None
        db.flush()
        return ConsumeResult(
            event_id=record.event_id,
            status=SyncInboxStatus.PROCESSED.value,
            result=record.result_json,
        )

    event = _event_from_record(record)
    try:
        # Handler effects must either commit together with the inbox receipt or
        # disappear completely. The savepoint lets the outer transaction retain
        # the durable retry/dead-letter state after a handler failure.
        with db.begin_nested():
            result = handler(db, event) or {}
    except SyncProcessingError as error:
        _schedule_inbox_failure(
            db,
            record,
            error,
            now=now,
            max_attempts=max_attempts,
            base_delay_seconds=base_delay_seconds,
            max_delay_seconds=max_delay_seconds,
            jitter_ratio=jitter_ratio,
        )
        return ConsumeResult(event_id=record.event_id, status=record.status.value)
    except Exception as exc:  # defensive boundary: unknown handler failures remain durable
        error = RetryableSyncError(str(exc), code="handler_exception")
        _schedule_inbox_failure(
            db,
            record,
            error,
            now=now,
            max_attempts=max_attempts,
            base_delay_seconds=base_delay_seconds,
            max_delay_seconds=max_delay_seconds,
            jitter_ratio=jitter_ratio,
        )
        return ConsumeResult(event_id=record.event_id, status=record.status.value)

    aggregate.last_applied_version = record.aggregate_version
    aggregate.last_event_id = record.event_id
    record.status = SyncInboxStatus.PROCESSED
    record.result_json = result
    record.processed_at = now
    record.next_attempt_at = None
    record.last_error_code = None
    record.last_error_message = None
    db.flush()
    return ConsumeResult(
        event_id=record.event_id,
        status=SyncInboxStatus.PROCESSED.value,
        result=result,
    )


def consume_incoming_event(
    session_factory: sessionmaker[Session],
    event: EventEnvelope,
    handler: SyncHandler,
    *,
    stream_name: str = "inbound",
    max_attempts: int = 8,
    base_delay_seconds: float = 1.0,
    max_delay_seconds: float = 300.0,
    jitter_ratio: float = 0.2,
) -> ConsumeResult:
    """Stage and apply one event atomically. A repeated event returns the durable prior receipt."""
    now = datetime.now(UTC)
    with session_factory() as db:
        with db.begin():
            record = stage_inbox_event(db, event)
            record = db.scalar(
                select(SyncInbox).where(SyncInbox.id == record.id).with_for_update()
            ) or record
            result = _apply_inbox_record(
                db,
                record,
                handler,
                now=now,
                max_attempts=max_attempts,
                base_delay_seconds=base_delay_seconds,
                max_delay_seconds=max_delay_seconds,
                jitter_ratio=jitter_ratio,
            )
            if result.status == SyncInboxStatus.PROCESSED.value:
                _update_checkpoint(
                    db,
                    stream_name=stream_name,
                    checkpoint_value=str(record.id),
                    event_id=record.event_id,
                    now=now,
                )
            return result


def process_inbox_batch(
    session_factory: sessionmaker[Session],
    handlers: dict[str, SyncHandler],
    *,
    limit: int,
    stream_name: str = "inbound",
    max_attempts: int = 8,
    base_delay_seconds: float = 1.0,
    max_delay_seconds: float = 300.0,
    jitter_ratio: float = 0.2,
    now: datetime | None = None,
) -> BatchResult:
    current = now or datetime.now(UTC)
    with session_factory() as db:
        ids = list(
            db.scalars(
                select(SyncInbox.id)
                .where(
                    SyncInbox.status.in_(
                        [SyncInboxStatus.PENDING, SyncInboxStatus.RETRY, SyncInboxStatus.BLOCKED]
                    ),
                    or_(SyncInbox.next_attempt_at.is_(None), SyncInbox.next_attempt_at <= current),
                )
                .order_by(SyncInbox.id.asc())
                .limit(max(1, limit))
            )
        )

    totals = {"processed": 0, "retried": 0, "blocked": 0, "dead_lettered": 0}
    for inbox_id in ids:
        with session_factory() as db:
            with db.begin():
                record = db.scalar(
                    select(SyncInbox).where(SyncInbox.id == inbox_id).with_for_update()
                )
                if record is None:
                    continue
                result = _apply_inbox_record(
                    db,
                    record,
                    handlers.get(record.event_type),
                    now=current,
                    max_attempts=max_attempts,
                    base_delay_seconds=base_delay_seconds,
                    max_delay_seconds=max_delay_seconds,
                    jitter_ratio=jitter_ratio,
                )
                if result.status == SyncInboxStatus.PROCESSED.value:
                    totals["processed"] += 1
                    _update_checkpoint(
                        db,
                        stream_name=stream_name,
                        checkpoint_value=str(record.id),
                        event_id=record.event_id,
                        now=current,
                    )
                elif result.status == SyncInboxStatus.RETRY.value:
                    totals["retried"] += 1
                elif result.status == SyncInboxStatus.BLOCKED.value:
                    totals["blocked"] += 1
                elif result.status == SyncInboxStatus.DEAD_LETTER.value:
                    totals["dead_lettered"] += 1

    return BatchResult(attempted=len(ids), **totals)


def process_outbox_batch(
    session_factory: sessionmaker[Session],
    transport: SyncTransport,
    *,
    limit: int,
    stream_name: str = "outbound",
    max_attempts: int = 8,
    base_delay_seconds: float = 1.0,
    max_delay_seconds: float = 300.0,
    jitter_ratio: float = 0.2,
    now: datetime | None = None,
) -> BatchResult:
    current = now or datetime.now(UTC)
    with session_factory() as db:
        ids = list(
            db.scalars(
                select(SyncOutbox.id)
                .where(
                    SyncOutbox.status.in_([SyncOutboxStatus.PENDING, SyncOutboxStatus.RETRY]),
                    or_(SyncOutbox.next_attempt_at.is_(None), SyncOutbox.next_attempt_at <= current),
                )
                .order_by(SyncOutbox.id.asc())
                .limit(max(1, limit))
            )
        )

    totals = {"processed": 0, "retried": 0, "blocked": 0, "dead_lettered": 0}
    for outbox_id in ids:
        with session_factory() as db:
            with db.begin():
                record = db.scalar(
                    select(SyncOutbox).where(SyncOutbox.id == outbox_id).with_for_update()
                )
                if record is None or record.status == SyncOutboxStatus.SENT:
                    continue
                if record.schema_version != CURRENT_EVENT_SCHEMA_VERSION:
                    status = _schedule_outbox_failure(
                        db,
                        record,
                        PermanentSyncError(
                            f"Unsupported event schema version {record.schema_version}.",
                            code="unsupported_schema_version",
                        ),
                        now=current,
                        max_attempts=max_attempts,
                        base_delay_seconds=base_delay_seconds,
                        max_delay_seconds=max_delay_seconds,
                        jitter_ratio=jitter_ratio,
                    )
                else:
                    try:
                        transport.send(_event_from_record(record))
                    except SyncProcessingError as error:
                        status = _schedule_outbox_failure(
                            db,
                            record,
                            error,
                            now=current,
                            max_attempts=max_attempts,
                            base_delay_seconds=base_delay_seconds,
                            max_delay_seconds=max_delay_seconds,
                            jitter_ratio=jitter_ratio,
                        )
                    except Exception as exc:
                        status = _schedule_outbox_failure(
                            db,
                            record,
                            RetryableSyncError(str(exc), code="transport_exception"),
                            now=current,
                            max_attempts=max_attempts,
                            base_delay_seconds=base_delay_seconds,
                            max_delay_seconds=max_delay_seconds,
                            jitter_ratio=jitter_ratio,
                        )
                    else:
                        record.status = SyncOutboxStatus.SENT
                        record.sent_at = current
                        record.next_attempt_at = None
                        record.last_error_code = None
                        record.last_error_message = None
                        db.flush()
                        status = SyncOutboxStatus.SENT.value
                        _update_checkpoint(
                            db,
                            stream_name=stream_name,
                            checkpoint_value=str(record.id),
                            event_id=record.event_id,
                            now=current,
                        )

                if status == SyncOutboxStatus.SENT.value:
                    totals["processed"] += 1
                elif status == SyncOutboxStatus.RETRY.value:
                    totals["retried"] += 1
                elif status == SyncOutboxStatus.DEAD_LETTER.value:
                    totals["dead_lettered"] += 1

    return BatchResult(attempted=len(ids), **totals)


def retry_dead_letter(
    db: Session,
    dead_letter_id: int,
    *,
    user_id: int | None = None,
) -> SyncDeadLetter:
    """Request a durable manual retry and record that decision in the existing audit ledger."""
    dead_letter = db.scalar(
        select(SyncDeadLetter).where(SyncDeadLetter.id == dead_letter_id).with_for_update()
    )
    if dead_letter is None:
        raise ValueError(f"Dead letter {dead_letter_id} does not exist.")

    if dead_letter.direction == SyncDirection.INBOUND:
        record = db.scalar(select(SyncInbox).where(SyncInbox.event_id == dead_letter.event_id))
        if record is None:
            raise ValueError("Dead-lettered inbound event is missing from the durable inbox.")
        record.status = SyncInboxStatus.PENDING
    else:
        record = db.scalar(select(SyncOutbox).where(SyncOutbox.event_id == dead_letter.event_id))
        if record is None:
            raise ValueError("Dead-lettered outbound event is missing from the durable outbox.")
        record.status = SyncOutboxStatus.RETRY

    record.next_attempt_at = None
    record.last_error_code = None
    record.last_error_message = None
    dead_letter.status = SyncDeadLetterStatus.RETRY_PENDING
    dead_letter.retry_count += 1
    dead_letter.last_failed_at = datetime.now(UTC)
    dead_letter.resolved_at = None

    write_audit_log(
        db,
        action="sync.dead_letter.retry",
        entity_type="sync_dead_letter",
        entity_id=dead_letter.id,
        user_id=user_id,
        new_value_json={
            "event_id": dead_letter.event_id,
            "direction": dead_letter.direction.value,
            "retry_count": dead_letter.retry_count,
        },
        notes="Manual synchronization retry requested.",
        commit=False,
    )
    db.flush()
    return dead_letter
