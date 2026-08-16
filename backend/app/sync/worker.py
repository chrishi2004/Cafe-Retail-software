from __future__ import annotations

import logging
import signal
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, settings
from app.core.scope import ScopeContext
from app.db.session import SessionLocal
from app.models import BusinessGroup, ContinuityMode, ContinuityReconciliationStatus, UserRole
from app.schemas.hc4 import SignedHeartbeatInput, SignedHeartbeatRead, WriterLeaseInput, WriterLeaseRead
from app.services.cloud_transport import (
    CloudGatewaySyncTransport,
    acquire_writer_lease,
    pull_cloud_commands,
    send_signed_heartbeat,
)
from app.services.continuity import (
    get_or_create_state,
    make_continuity_reference_handler,
    queue_metrics,
    refresh_state_metrics,
    run_reconciliation,
    scope_key,
)
from app.sync.cafe_orders import make_cloud_order_handler
from app.sync.device import DeviceIdentityStore, SettingsCredentialStore
from app.sync.service import (
    BatchResult,
    RetryableSyncError,
    SyncHandler,
    SyncProcessingError,
    SyncTransport,
    process_inbox_batch,
    process_outbox_batch,
    stage_inbox_event,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerCycleResult:
    inbound: BatchResult
    outbound: BatchResult
    continuity_mode: str | None = None


class LocalSyncWorker:
    """Durable Local Hub worker with HC4 automatic recovery orchestration."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] = SessionLocal,
        configured_settings: Settings = settings,
        handlers: dict[str, SyncHandler] | None = None,
        transport: SyncTransport | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.settings = configured_settings
        self.handlers = handlers or {}
        self.transport = transport
        self.device_store = DeviceIdentityStore(configured_settings)
        self.credential_store = SettingsCredentialStore(configured_settings)
        self._command_puller: Callable[[int], list] | None = None
        self._heartbeat_sender: Callable[[SignedHeartbeatInput], SignedHeartbeatRead] | None = None
        self._lease_acquirer: Callable[[WriterLeaseInput], WriterLeaseRead] | None = None
        self._stop_event = threading.Event()
        self.device_id: str | None = None
        self.business_group_id: str | None = configured_settings.sync_business_group_id
        self.company_id: str | None = configured_settings.sync_company_id
        self.branch_id: str | None = configured_settings.sync_branch_id
        self.fencing_epoch: int = 0
        self.lease_expires_at: datetime | None = None

    def _ensure_local_scope_identity(self) -> None:
        if self.business_group_id is not None:
            return
        with self.session_factory() as db:
            group_id = db.scalar(select(BusinessGroup.id).order_by(BusinessGroup.id).limit(1))
        if group_id is not None:
            self.business_group_id = str(group_id)

    def _scope_context(self) -> ScopeContext | None:
        if self.business_group_id is None or not self.business_group_id.isdigit():
            return None
        if self.company_id is not None and not self.company_id.isdigit():
            return None
        if self.branch_id is not None and not self.branch_id.isdigit():
            return None
        return ScopeContext(
            user_id=0,
            role=UserRole.SUPER_ADMIN,
            business_group_id=int(self.business_group_id),
            company_id=int(self.company_id) if self.company_id is not None else None,
            all_companies=self.company_id is None,
            branch_ids=(int(self.branch_id),) if self.branch_id is not None else (),
            permissions=frozenset({"*"}),
        )

    def initialize(self) -> str:
        with self.session_factory() as db:
            with db.begin():
                identity = self.device_store.get_or_create(db)
                self.device_id = identity.device_id
        self._ensure_local_scope_identity()
        assert self.device_id is not None
        self.handlers.setdefault("cafe.order.submitted", make_cloud_order_handler(self.device_id))
        self.handlers.setdefault(
            "continuity.reference.created",
            make_continuity_reference_handler(self.device_id),
        )
        gateway = (self.settings.cloud_gateway_base_url or "").strip()
        proof = self.credential_store.get_secret()
        if gateway and proof:
            if self.transport is None:
                self.transport = CloudGatewaySyncTransport(
                    gateway_base_url=gateway,
                    device_id=self.device_id,
                    installation_proof=proof,
                )
            if self._command_puller is None:
                self._command_puller = lambda limit: pull_cloud_commands(
                    gateway_base_url=gateway,
                    device_id=self.device_id or "",
                    installation_proof=proof,
                    limit=limit,
                )
            if self._heartbeat_sender is None:
                self._heartbeat_sender = lambda payload: send_signed_heartbeat(
                    gateway_base_url=gateway,
                    device_id=self.device_id or "",
                    installation_proof=proof,
                    payload=payload,
                )
            if self._lease_acquirer is None:
                self._lease_acquirer = lambda payload: acquire_writer_lease(
                    gateway_base_url=gateway,
                    device_id=self.device_id or "",
                    installation_proof=proof,
                    payload=payload,
                )
        logger.info("Local sync worker initialized for device %s", self.device_id)
        return self.device_id

    def _metrics(self) -> dict[str, int | datetime | None]:
        scope = self._scope_context()
        if scope is None:
            return {
                "pending_inbox": 0,
                "pending_outbox": 0,
                "dead_letters": 0,
                "oldest_pending_at": None,
                "last_inbound_sync_at": None,
                "last_outbound_sync_at": None,
            }
        with self.session_factory() as db:
            return queue_metrics(db, scope)

    def _persist_state(
        self,
        *,
        mode: ContinuityMode,
        metrics: dict[str, int | datetime | None] | None = None,
        cloud_contact: bool = False,
        attention_message: str | None = None,
    ) -> None:
        if self.business_group_id is None:
            return
        now = datetime.now(UTC)
        with self.session_factory() as db:
            with db.begin():
                state = get_or_create_state(
                    db,
                    business_group_id=self.business_group_id,
                    company_id=self.company_id,
                    branch_id=self.branch_id,
                )
                state.fencing_epoch = self.fencing_epoch
                state.lease_owner_device_id = self.device_id
                state.lease_expires_at = self.lease_expires_at
                if cloud_contact:
                    state.last_cloud_contact_at = now
                    state.last_heartbeat_at = now
                if mode == ContinuityMode.SYNCHRONIZING and state.recovery_started_at is None:
                    state.recovery_started_at = now
                refresh_state_metrics(
                    db,
                    state=state,
                    metrics=metrics or self._metrics(),
                    mode=mode,
                    attention_message=attention_message,
                    now=now,
                )

    def _heartbeat_and_lease(self, metrics: dict[str, int | datetime | None]) -> bool:
        if self._heartbeat_sender is None or self._lease_acquirer is None or self.device_id is None:
            # HC1-HC3 tests and embedded integrations can inject a direct transport
            # without a configured HTTP gateway. Preserve that explicit transport
            # contract while requiring heartbeat/fencing for real configured gateways.
            if (
                self.device_id is not None
                and self.transport is not None
                and not (self.settings.cloud_gateway_base_url or "").strip()
            ):
                return True
            self._persist_state(mode=ContinuityMode.OFFLINE_LOCAL, metrics=metrics)
            return False
        try:
            heartbeat = self._heartbeat_sender(
                SignedHeartbeatInput(
                    mode="recovering" if self.fencing_epoch == 0 else "local_writer",
                    fencing_epoch=self.fencing_epoch,
                    software_version=self.settings.sync_software_version,
                    event_schema_version=1,
                    pending_inbox=int(metrics["pending_inbox"] or 0),
                    pending_outbox=int(metrics["pending_outbox"] or 0),
                )
            )
            self.business_group_id = heartbeat.business_group_id
            self.company_id = heartbeat.company_id
            self.branch_id = heartbeat.branch_id
            now = datetime.now(UTC)
            lease = heartbeat.lease
            lease_active = (
                lease is not None
                and lease.lease_owner_device_id == self.device_id
                and lease.lease_expires_at is not None
                and lease.lease_expires_at > now
            )
            if not lease_active:
                lease = self._lease_acquirer(
                    WriterLeaseInput(
                        scope_key=scope_key(
                            business_group_id=self.business_group_id,
                            company_id=self.company_id,
                            branch_id=self.branch_id,
                        ),
                        business_group_id=self.business_group_id,
                        company_id=self.company_id,
                        branch_id=self.branch_id,
                        requested_mode="recovering",
                        fencing_epoch=self.fencing_epoch or None,
                    )
                )
            self.fencing_epoch = lease.fencing_epoch
            self.lease_expires_at = lease.lease_expires_at
            self._persist_state(
                mode=ContinuityMode.SYNCHRONIZING,
                metrics=metrics,
                cloud_contact=True,
            )
            return True
        except RetryableSyncError as exc:
            logger.warning("Cloud continuity contact deferred: %s", exc)
            self._persist_state(
                mode=ContinuityMode.OFFLINE_LOCAL,
                metrics=metrics,
                attention_message=None,
            )
            return False
        except SyncProcessingError as exc:
            logger.error("Cloud continuity authorization/fencing failed: %s", exc)
            self._persist_state(
                mode=ContinuityMode.ATTENTION_REQUIRED,
                metrics=metrics,
                attention_message=str(exc),
            )
            return False

    def _pull_and_stage_commands(self) -> int:
        if self._command_puller is None:
            return 0
        try:
            events = self._command_puller(self.settings.sync_batch_size)
        except SyncProcessingError as exc:
            logger.warning("Cloud command pull deferred: %s", exc)
            return 0
        if not events:
            return 0
        with self.session_factory() as db:
            with db.begin():
                for event in events:
                    stage_inbox_event(db, event)
        return len(events)

    def _automatic_reconcile(self) -> ContinuityMode:
        scope = self._scope_context()
        if scope is None:
            self._persist_state(
                mode=ContinuityMode.ATTENTION_REQUIRED,
                attention_message="Continuity device scope cannot be mapped to Local Hub identifiers.",
            )
            return ContinuityMode.ATTENTION_REQUIRED
        with self.session_factory() as db:
            with db.begin():
                state = get_or_create_state(
                    db,
                    business_group_id=self.business_group_id or "",
                    company_id=self.company_id,
                    branch_id=self.branch_id,
                )
                state.fencing_epoch = self.fencing_epoch
                state.lease_owner_device_id = self.device_id
                state.lease_expires_at = self.lease_expires_at
                report = run_reconciliation(db, scope=scope, state=state)
                return (
                    ContinuityMode.LIVE
                    if report.status == ContinuityReconciliationStatus.CLEAN
                    else ContinuityMode.ATTENTION_REQUIRED
                )

    def run_once(self) -> WorkerCycleResult:
        if self.device_id is None:
            self.initialize()
        before = self._metrics()
        cloud_ready = self._heartbeat_and_lease(before)

        pulled = self._pull_and_stage_commands() if cloud_ready else 0
        if pulled:
            logger.info("Staged %s cloud synchronization command(s).", pulled)

        inbound = process_inbox_batch(
            self.session_factory,
            self.handlers,
            limit=self.settings.sync_batch_size,
            max_attempts=self.settings.sync_max_attempts,
            base_delay_seconds=self.settings.sync_base_retry_delay_seconds,
            max_delay_seconds=self.settings.sync_max_retry_delay_seconds,
            jitter_ratio=self.settings.sync_retry_jitter_ratio,
        )
        if not cloud_ready or self.transport is None:
            outbound = BatchResult()
        else:
            outbound = process_outbox_batch(
                self.session_factory,
                self.transport,
                limit=self.settings.sync_batch_size,
                max_attempts=self.settings.sync_max_attempts,
                base_delay_seconds=self.settings.sync_base_retry_delay_seconds,
                max_delay_seconds=self.settings.sync_max_retry_delay_seconds,
                jitter_ratio=self.settings.sync_retry_jitter_ratio,
            )

        after = self._metrics()
        if cloud_ready:
            if int(after["dead_letters"] or 0) > 0:
                final_mode = ContinuityMode.ATTENTION_REQUIRED
                self._persist_state(
                    mode=final_mode,
                    metrics=after,
                    cloud_contact=True,
                    attention_message="Synchronization has unresolved dead-letter records.",
                )
            elif int(after["pending_inbox"] or 0) == 0 and int(after["pending_outbox"] or 0) == 0:
                final_mode = self._automatic_reconcile()
            else:
                final_mode = ContinuityMode.SYNCHRONIZING
                self._persist_state(mode=final_mode, metrics=after, cloud_contact=True)
        else:
            final_mode = ContinuityMode.OFFLINE_LOCAL

        if self.device_id is not None:
            with self.session_factory() as db:
                with db.begin():
                    self.device_store.touch(db, self.device_id)
        return WorkerCycleResult(
            inbound=inbound,
            outbound=outbound,
            continuity_mode=final_mode.value,
        )

    def stop(self) -> None:
        self._stop_event.set()

    def run_forever(self) -> None:
        logger.info("Local sync worker starting; PostgreSQL and durable queues are required dependencies.")
        while not self._stop_event.is_set() and self.device_id is None:
            try:
                self.initialize()
            except Exception:
                logger.exception("Local Hub dependency startup failed; worker will retry without losing queue state.")
                self._stop_event.wait(self.settings.sync_poll_interval_seconds)
        while not self._stop_event.is_set():
            try:
                cycle = self.run_once()
                if cycle.inbound.attempted or cycle.outbound.attempted:
                    logger.info("Sync cycle inbound=%s outbound=%s mode=%s", cycle.inbound, cycle.outbound, cycle.continuity_mode)
            except Exception:
                logger.exception("Synchronization cycle failed; committed queue state remains durable.")
            self._stop_event.wait(self.settings.sync_poll_interval_seconds)
        logger.info("Local sync worker stopped gracefully.")


def _install_signal_handlers(worker: LocalSyncWorker) -> None:
    def request_shutdown(signum: int, _frame: object) -> None:
        logger.info("Received signal %s; requesting graceful worker shutdown.", signum)
        worker.stop()

    for signal_name in ("SIGINT", "SIGTERM"):
        signal_value = getattr(signal, signal_name, None)
        if signal_value is not None:
            signal.signal(signal_value, request_shutdown)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    worker = LocalSyncWorker()
    _install_signal_handlers(worker)
    worker.run_forever()


if __name__ == "__main__":
    main()
