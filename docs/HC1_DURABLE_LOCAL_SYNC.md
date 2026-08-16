# HC1 Durable Local Synchronization Foundation

## Scope

HC1 adds the crash-safe Local Business Hub synchronization substrate only. It does **not** add Supabase QR order intake, cloud financial writes, Cafe order import, writer leases, or continuity-mode billing.

The Local PostgreSQL database remains authoritative for inventory, invoices, payments, ledgers, stock movements, closing, and audit history.

## Durable Tables

The local Alembic revision `20260811_0007` adds:

- `sync_devices`: persistent installation identity and a credential reference, never the raw credential.
- `sync_outbox`: local events committed in the same transaction as their domain change.
- `sync_inbox`: durable inbound events plus their processing receipt/result.
- `sync_checkpoints`: last successful inbound/outbound processing markers.
- `sync_dead_letters`: visible permanent/exhausted failures with safe diagnostics.
- `sync_aggregate_versions`: monotonic per-aggregate version state used to reject or defer out-of-order effects.

## Transaction Rules

### Outbox producer

`app.sync.service.enqueue_outbox_event(db, event)` deliberately does **not** commit. Call it inside the same SQLAlchemy transaction that applies the domain change:

```python
with db.begin():
    # Apply domain mutation.
    ...
    enqueue_outbox_event(db, event)
```

If the domain transaction rolls back, its outbox row rolls back with it. Publishing an event before the originating transaction commits is forbidden.

### Inbox consumer

`consume_incoming_event(...)` stages the event, checks schema and aggregate version, applies the registered business handler, advances aggregate version, writes the durable receipt, and updates the checkpoint transactionally.

If a response/acknowledgment is lost after commit, re-delivery of the same `event_id` returns the durable prior receipt and does not re-run the business effect.

### Aggregate ordering

Aggregate versions start at `1` and increase monotonically per `(aggregate_type, aggregate_id)`.

- next version: apply normally;
- same already-committed event: return prior result/no-op;
- conflicting event for an already-used version: dead-letter;
- older version: acknowledge as superseded only after newer committed aggregate state proves prior progress;
- future version with a gap: remain visibly `blocked` and retry with bounded backoff; repeated unresolved gaps eventually enter the dead-letter queue.

There is no last-write-wins behavior for financial or stock events.

## Retry Policy

HC1 provides bounded exponential backoff with jitter and optional `Retry-After` support.

Defaults:

```text
SYNC_BATCH_SIZE=50
SYNC_POLL_INTERVAL_SECONDS=5
SYNC_MAX_ATTEMPTS=8
SYNC_BASE_RETRY_DELAY_SECONDS=1
SYNC_MAX_RETRY_DELAY_SECONDS=300
SYNC_RETRY_JITTER_RATIO=0.2
```

Retryable transport/handler failures remain durable. Permanent errors such as unsupported schema versions, invalid scope, or unregistered handlers fail visibly instead of looping forever.

Manual dead-letter retry uses `retry_dead_letter(...)`, reuses the original event ID, and writes `sync.dead_letter.retry` into the existing audit log.

## Device Identity And Credentials

The worker persists one stable `device_id` in `sync_devices`. If `SYNC_DEVICE_ID` is not configured, the first start generates a UUID and later restarts reuse it from PostgreSQL.

Only a reference such as `env:SYNC_DEVICE_SECRET` may be persisted. Raw device credentials remain in server-side configuration:

```text
SYNC_DEVICE_SECRET=<real secret outside source control>
SYNC_DEVICE_CREDENTIAL_REF=env:SYNC_DEVICE_SECRET
```

Never put device secrets in `VITE_*` variables, queue payloads, logs, committed `.env` files, or database rows.

## Running The Worker

After applying the local migration:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
python -m app.sync.worker
```

The worker processes durable inbox rows immediately. HC1 intentionally has no cloud transport, so existing outbox rows remain pending until a later approved phase supplies a transport.

### Development automatic restart

From the repository root:

```powershell
.\scripts\run_sync_worker_dev.ps1
```

The supervisor restarts the worker after non-zero exits. Ctrl+C requests graceful worker shutdown.

## Production Service Policy

Run PostgreSQL, the Local Hub API, sync worker, local frontend, and backup monitor under operating-system managed startup/restart policies.

Recommended startup sequence:

1. Start PostgreSQL and wait for database health.
2. Run approved local Alembic migrations as a controlled deployment step.
3. Start the Local Hub FastAPI service.
4. Start `python -m app.sync.worker` from the `backend` working directory.
5. Start/serve the local React build and backup monitor.

On Windows, install the worker through the organization's approved service wrapper/process manager (for example WinSW or NSSM) with:

- executable: `backend\.venv\Scripts\python.exe`;
- arguments: `-m app.sync.worker`;
- working directory: `backend`;
- start mode: automatic;
- restart after non-zero process exit;
- service dependency/startup ordering after PostgreSQL health;
- stdout/stderr directed to protected operational logs without secrets.

A development reloader is not a production durability mechanism. Queue safety comes from committed PostgreSQL state; the service manager only ensures the process starts again.

## Crash And Power Recovery Semantics

No queue state or checkpoint depends solely on process memory.

If the process dies:

- before its database transaction commits, the transaction rolls back and the event remains available for retry;
- after commit but before acknowledgment reaches the producer, the producer may re-deliver and the inbox receipt prevents duplicate effects;
- while an outbound event is being sent, a restart may send the same `event_id` again, so later cloud consumers must remain idempotent.

A restarted worker reads the same `sync_inbox`, `sync_outbox`, `sync_checkpoints`, aggregate versions, and device identity from PostgreSQL.

## HC1 Exit Gate

**No QR order may be accepted through Supabase in HC1.**

The next cloud-facing phase remains blocked until automated evidence proves:

- domain + outbox atomic commit/rollback;
- duplicate delivery creates one business effect;
- lost acknowledgment is safe;
- restart resumes pending work from persisted state;
- aggregate gaps do not apply out of order;
- dead-letter retry is audited.
