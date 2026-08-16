from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

# When executed as `python scripts/verify_hc4_backup_restore.py`, Python places
# backend/scripts on sys.path. Add the backend root explicitly so application
# modules are imported from the same tree that migrations/tests just verified.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    ContinuityMode,
    ContinuityReconciliation,
    ContinuityReconciliationStatus,
    ContinuityState,
    SyncCheckpoint,
    SyncDevice,
    SyncDeviceStatus,
    SyncOutbox,
)
from app.schemas.sync import EventEnvelope, EventSource
from app.sync.service import enqueue_outbox_event

MARKER = "hc4-backup-restore-proof"
RECONCILIATION_REFERENCE = "00000000-0000-0000-0000-00000000c404"


def _factory() -> sessionmaker[Session]:
    url = (
        os.environ.get("HC4_BACKUP_DATABASE_URL")
        or os.environ.get("LOCAL_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
    )
    if not url:
        raise RuntimeError("HC4_BACKUP_DATABASE_URL or LOCAL_DATABASE_URL is required.")
    engine = create_engine(url, pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False)


def seed(factory: sessionmaker[Session]) -> None:
    with factory() as db:
        with db.begin():
            # Use a release-specific marker and require a clean slot. CI starts
            # from a fresh database; encountering an existing marker should fail
            # visibly instead of mutating evidence left by another rehearsal.
            assert db.scalar(select(SyncOutbox).where(SyncOutbox.aggregate_id == MARKER)) is None
            assert db.scalar(select(SyncCheckpoint).where(SyncCheckpoint.stream_name == MARKER)) is None
            assert db.scalar(select(SyncDevice).where(SyncDevice.device_id == MARKER)) is None
            assert db.scalar(select(ContinuityState).where(ContinuityState.scope_key == MARKER)) is None
            assert db.scalar(
                select(ContinuityReconciliation).where(
                    ContinuityReconciliation.reconciliation_reference == RECONCILIATION_REFERENCE
                )
            ) is None

            event = EventEnvelope(
                event_id=uuid4(),
                event_type="hc4.backup.pending",
                source=EventSource.LOCAL_HUB,
                source_device_id=MARKER,
                business_group_id="1",
                company_id="2",
                branch_id="3",
                aggregate_type="hc4_backup",
                aggregate_id=MARKER,
                aggregate_version=1,
                payload={"marker": MARKER},
            )
            enqueue_outbox_event(db, event)
            db.add(
                SyncCheckpoint(
                    stream_name=MARKER,
                    checkpoint_value="42",
                    last_event_id=str(event.event_id),
                    last_success_at=datetime.now(UTC),
                )
            )
            db.add(
                SyncDevice(
                    device_id=MARKER,
                    display_name="HC4 Backup Proof Device",
                    status=SyncDeviceStatus.ACTIVE,
                    credential_ref="env:HC4_TEST_SECRET",
                    last_started_at=datetime.now(UTC),
                )
            )
            db.add(
                ContinuityState(
                    scope_key=MARKER,
                    business_group_id="1",
                    company_id="2",
                    branch_id="3",
                    mode=ContinuityMode.SYNCHRONIZING,
                    fencing_epoch=9,
                    pending_outbox=1,
                )
            )
            db.add(
                ContinuityReconciliation(
                    reconciliation_reference=RECONCILIATION_REFERENCE,
                    scope_key=MARKER,
                    business_group_id="1",
                    company_id="2",
                    branch_id="3",
                    fencing_epoch=9,
                    status=ContinuityReconciliationStatus.PENDING,
                    pending_outbox_before=1,
                    details_json={"marker": MARKER},
                )
            )


def verify(factory: sessionmaker[Session]) -> None:
    with factory() as db:
        outbox = db.scalar(select(SyncOutbox).where(SyncOutbox.aggregate_id == MARKER))
        checkpoint = db.scalar(select(SyncCheckpoint).where(SyncCheckpoint.stream_name == MARKER))
        device = db.scalar(select(SyncDevice).where(SyncDevice.device_id == MARKER))
        state = db.scalar(select(ContinuityState).where(ContinuityState.scope_key == MARKER))
        reconciliation = db.scalar(
            select(ContinuityReconciliation).where(
                ContinuityReconciliation.reconciliation_reference == RECONCILIATION_REFERENCE
            )
        )
        assert outbox is not None and outbox.status.value == "pending"
        assert checkpoint is not None and checkpoint.checkpoint_value == "42"
        assert device is not None and device.status == SyncDeviceStatus.ACTIVE
        assert state is not None and state.fencing_epoch == 9 and state.pending_outbox == 1
        assert reconciliation is not None and reconciliation.status == ContinuityReconciliationStatus.PENDING
        assert reconciliation.details_json == {"marker": MARKER}
    print(
        "HC4 backup/restore verification passed: queue, checkpoint, device, "
        "continuity, and reconciliation state survived."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["seed", "verify"])
    args = parser.parse_args()
    factory = _factory()
    if args.mode == "seed":
        seed(factory)
        print("HC4 backup proof rows seeded.")
    else:
        verify(factory)


if __name__ == "__main__":
    main()
