from __future__ import annotations

from sqlalchemy import func, select

from app.models import SyncCheckpoint, SyncDeadLetter
from app.schemas.sync import EventEnvelope, EventSource
from app.sync.service import PermanentSyncError, consume_incoming_event


def test_handler_rejection_keeps_failure_record_without_partial_checkpoint(
    db_session_factory,
) -> None:
    event = EventEnvelope(
        event_type="sync.transaction.probe",
        source=EventSource.CLOUD_GATEWAY,
        business_group_id="1",
        company_id="1",
        branch_id="1",
        aggregate_type="transaction_probe",
        aggregate_id="probe-1",
        aggregate_version=1,
        payload={"probe": True},
    )

    def rejecting_handler(db, _event):
        db.add(
            SyncCheckpoint(
                stream_name="temporary-handler-checkpoint",
                checkpoint_value="temporary",
            )
        )
        db.flush()
        raise PermanentSyncError("handler rejected event", code="probe_rejected")

    result = consume_incoming_event(db_session_factory, event, rejecting_handler)
    assert result.status == "dead_letter"

    with db_session_factory() as db:
        partial_count = db.scalar(
            select(func.count(SyncCheckpoint.id)).where(
                SyncCheckpoint.stream_name == "temporary-handler-checkpoint"
            )
        )
        failure_count = db.scalar(
            select(func.count(SyncDeadLetter.id)).where(
                SyncDeadLetter.event_id == str(event.event_id)
            )
        )
        assert partial_count == 0
        assert failure_count == 1
