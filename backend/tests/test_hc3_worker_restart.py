from __future__ import annotations

from app.core.config import Settings
from app.schemas.sync import EventEnvelope
from app.sync.worker import LocalSyncWorker
from tests.test_hc3_cloud_order_convergence import (
    DEVICE_ID,
    DirectCloudTransport,
    _command_event,
    _publish_local_fixture,
    _submit,
    hc3_cloud_factory,
)


def test_fresh_worker_pulls_and_imports_pending_cloud_order(
    db_session_factory,
    seed_auth_data,
    hc3_cloud_factory,
) -> None:
    ids, publication = _publish_local_fixture(db_session_factory, hc3_cloud_factory)
    cloud_order = _submit(hc3_cloud_factory, publication, ids, key="hc3-restart-001")
    event: EventEnvelope = _command_event(hc3_cloud_factory, cloud_order.public_id)

    worker = LocalSyncWorker(
        session_factory=db_session_factory,
        configured_settings=Settings(
            environment="test",
            sync_device_id=DEVICE_ID,
            sync_batch_size=20,
            sync_retry_jitter_ratio=0,
            _env_file=None,
        ),
        transport=DirectCloudTransport(hc3_cloud_factory),
    )
    worker.initialize()
    worker._command_puller = lambda _limit: [event]
    cycle = worker.run_once()

    assert cycle.inbound.processed == 1
    assert cycle.outbound.processed == 1
