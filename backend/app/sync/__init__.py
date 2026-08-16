"""Durable local synchronization primitives for the Local Business Hub."""

from app.sync.device import DeviceIdentity, DeviceIdentityStore, SettingsCredentialStore
from app.sync.service import (
    AggregateVersionGap,
    PermanentSyncError,
    RetryableSyncError,
    SyncHandler,
    SyncTransport,
    consume_incoming_event,
    enqueue_outbox_event,
    hash_idempotency_key,
    process_inbox_batch,
    process_outbox_batch,
    retry_dead_letter,
    stage_inbox_event,
)

__all__ = [
    "AggregateVersionGap",
    "DeviceIdentity",
    "DeviceIdentityStore",
    "PermanentSyncError",
    "RetryableSyncError",
    "SettingsCredentialStore",
    "SyncHandler",
    "SyncTransport",
    "consume_incoming_event",
    "enqueue_outbox_event",
    "hash_idempotency_key",
    "process_inbox_batch",
    "process_outbox_batch",
    "retry_dead_letter",
    "stage_inbox_event",
]
