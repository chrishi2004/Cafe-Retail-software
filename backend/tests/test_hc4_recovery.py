from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models import ContinuityMode, ContinuityState, SyncOutbox, SyncOutboxStatus
from app.schemas.hc4 import SignedHeartbeatRead, WriterLeaseRead
from app.schemas.sync import EventEnvelope, EventSource
from app.sync.service import enqueue_outbox_event
from app.sync.worker import LocalSyncWorker


class CollectingTransport:
    def __init__(self) -> None:
        self.events: list[str] = []

    def send(self, event: EventEnvelope) -> dict[str, object]:
        self.events.append(str(event.event_id))
        return {"accepted": True, "event_id": str(event.event_id)}


def _event() -> EventEnvelope:
    return EventEnvelope(
        event_type="hc4.test.local",
        source=EventSource.LOCAL_HUB,
        source_device_id="hc4-worker-device",
        business_group_id="1",
        company_id="2",
        branch_id="3",
        aggregate_type="hc4_test",
        aggregate_id="one",
        aggregate_version=1,
        payload={"value": 1},
    )


def _enqueue(factory: sessionmaker[Session]) -> str:
    event = _event()
    with factory() as db:
        with db.begin():
            enqueue_outbox_event(db, event)
    return str(event.event_id)


def test_cloud_outage_keeps_outbox_durable_and_marks_offline_local(
    db_session_factory: sessionmaker[Session],
) -> None:
    event_id = _enqueue(db_session_factory)
    worker = LocalSyncWorker(
        session_factory=db_session_factory,
        configured_settings=Settings(
            environment="test",
            sync_device_id="hc4-worker-device",
            sync_business_group_id="1",
            sync_company_id="2",
            sync_branch_id="3",
            _env_file=None,
        ),
    )
    cycle = worker.run_once()
    assert cycle.continuity_mode == ContinuityMode.OFFLINE_LOCAL.value
    assert cycle.outbound.attempted == 0
    with db_session_factory() as db:
        outbox = db.scalar(select(SyncOutbox).where(SyncOutbox.event_id == event_id))
        assert outbox is not None
        assert outbox.status == SyncOutboxStatus.PENDING
        state = db.scalar(select(ContinuityState).where(ContinuityState.company_id == "2"))
        assert state is not None
        assert state.mode == ContinuityMode.OFFLINE_LOCAL
        assert state.pending_outbox == 1


def test_recovery_acquires_fenced_lease_drains_queue_and_reconciles(
    db_session_factory: sessionmaker[Session],
) -> None:
    event_id = _enqueue(db_session_factory)
    transport = CollectingTransport()
    worker = LocalSyncWorker(
        session_factory=db_session_factory,
        configured_settings=Settings(
            environment="test",
            cloud_gateway_base_url="https://cloud.example.invalid",
            sync_device_id="hc4-worker-device",
            sync_device_secret=SecretStr("hc4-secret"),
            sync_business_group_id="1",
            sync_company_id="2",
            sync_branch_id="3",
            sync_retry_jitter_ratio=0,
            _env_file=None,
        ),
        transport=transport,
    )
    worker.initialize()
    worker._command_puller = lambda _limit: []
    worker._heartbeat_sender = lambda _payload: SignedHeartbeatRead(
        accepted=True,
        device_id="hc4-worker-device",
        recorded_at=datetime.now(UTC),
        business_group_id="1",
        company_id="2",
        branch_id="3",
        lease=None,
    )
    worker._lease_acquirer = lambda payload: WriterLeaseRead(
        scope_key=payload.scope_key,
        current_mode="recovering",
        lease_owner_device_id="hc4-worker-device",
        fencing_epoch=7,
        lease_expires_at=datetime.now(UTC) + timedelta(seconds=90),
        last_heartbeat_at=datetime.now(UTC),
        recovery_state="recovering",
    )

    cycle = worker.run_once()
    assert cycle.outbound.processed == 1
    assert cycle.continuity_mode == ContinuityMode.LIVE.value
    assert transport.events == [event_id]
    with db_session_factory() as db:
        outbox = db.scalar(select(SyncOutbox).where(SyncOutbox.event_id == event_id))
        assert outbox is not None and outbox.status == SyncOutboxStatus.SENT
        state = db.scalar(select(ContinuityState).where(ContinuityState.company_id == "2"))
        assert state is not None
        assert state.fencing_epoch == 7
        assert state.pending_outbox == 0
        assert state.last_reconciled_at is not None
        assert state.mode == ContinuityMode.LIVE


def test_explicit_direct_transport_keeps_hc3_in_process_transport_contract(
    db_session_factory: sessionmaker[Session],
) -> None:
    _enqueue(db_session_factory)
    transport = CollectingTransport()
    worker = LocalSyncWorker(
        session_factory=db_session_factory,
        configured_settings=Settings(
            environment="test",
            sync_device_id="hc4-direct-device",
            sync_business_group_id="1",
            sync_company_id="2",
            sync_branch_id="3",
            _env_file=None,
        ),
        transport=transport,
    )
    worker.initialize()
    worker._command_puller = lambda _limit: []
    cycle = worker.run_once()
    assert cycle.outbound.processed == 1
    assert len(transport.events) == 1
