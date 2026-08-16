# HC4 Continuity And Recovery Runbook

## Authority boundary

Local PostgreSQL remains authoritative for invoices, payments, customer ledger, stock, inventory, financial closing, and audit records. Cloud coordination may keep public QR order intake and explicitly approved continuity references durable while the Local Hub is unavailable, but it does not apply final financial or stock effects.

## Normal startup order

1. Start PostgreSQL and wait for a successful readiness check.
2. Apply the approved Local Hub Alembic migration history.
3. Start the Local Hub API.
4. Load the persisted synchronization device identity and checkpoints.
5. Validate cloud reachability with a signed heartbeat and obtain/validate the writer lease and fencing epoch.
6. Start the inbound/outbound synchronization worker.
7. Pull and durably stage cloud commands, then drain bounded inbound/outbound batches.
8. Run continuity reconciliation when the queue reaches a clean drain point.
9. Report `live` only after the Local API, durable queues, writer fencing, and reconciliation are healthy.

`LocalSyncWorker.run_forever()` retries initialization when PostgreSQL is temporarily unavailable. A process restart therefore does not require an operator to recreate in-memory queue state. The durable inbox/outbox/checkpoints are the source of restart progress.

## Continuity states

- `live`: Local Hub and cloud coordination have reconciled successfully.
- `offline_local`: cloud coordination is unavailable; Local Hub remains the financial/stock authority and outbound work remains durably queued.
- `cloud_continuity`: cloud public intake/approved continuity capture is operating while Local Hub is unavailable. This state does not grant cloud financial authority.
- `synchronizing`: Local Hub has reconnected, holds the current fencing epoch, and queues/reconciliation are still draining.
- `stale`: heartbeat/snapshot freshness is outside the accepted window.
- `attention_required`: dead letters, fencing/auth failures, or reconciliation mismatches require review.

## Signed device heartbeat

The Local Hub sends `X-Device-Id`, installation proof, timestamp, nonce, and HMAC-SHA256 signature. The signature covers:

```text
<device id>\n<unix timestamp>\n<nonce>\n<sha256(canonical JSON payload)>
```

The HMAC key is the SHA-256 digest of the installation proof. The cloud stores only the digest, not the plaintext installation proof. Timestamps outside the accepted skew fail closed and a `(device_id, nonce)` pair can be accepted only once.

## Writer lease and fencing

Writer leases are scoped by business group/company/branch. Acquisition behavior:

- first acquisition starts fencing epoch 1;
- renewal by the same active owner requires the exact current epoch and does not increment it;
- an expired lease must be acquired again;
- takeover after expiry increments the epoch monotonically;
- another active owner cannot be displaced;
- stale epochs fail closed.

A cloud continuity reference must carry the current fencing epoch. It is stored as `pending_reconciliation` and emits a durable sync command. It does not create an invoice, payment ledger entry, stock movement, or closing effect in the cloud.

## Recovery sequence

After connectivity returns:

1. Signed heartbeat succeeds.
2. Local Hub validates or reacquires the writer lease/fencing epoch.
3. State becomes `synchronizing`.
4. Cloud commands are pulled and committed to the local inbox before application.
5. Inbox handlers apply effects idempotently with their durable receipts.
6. Local outbox events are pushed; lost acknowledgements are safely retried.
7. Retryable failures remain queued. Permanent/exhausted failures become dead letters.
8. Once inbound/outbound work reaches a drain point, reconciliation checks order, invoice, payment, stock, queue/dead-letter, and closing consistency.
9. Clean reconciliation returns the scope to `live`; mismatches return `attention_required`.

## Dead-letter operation

Use the authenticated continuity dashboard or Local Hub endpoints:

- `GET /api/sync/dead-letters`
- `POST /api/sync/dead-letters/{id}/retry`

Manual retry uses the existing HC1 durable retry implementation and records `sync.dead_letter.retry` in the audit log. Retrying does not invent a new event identifier.

## Backup scope

A Local Hub backup used for continuity recovery must include the entire PostgreSQL database. In particular, do not omit these durable continuity tables:

- `sync_devices`
- `sync_outbox`
- `sync_inbox`
- `sync_checkpoints`
- `sync_dead_letters`
- `sync_aggregate_versions`
- `cloud_record_links`
- `continuity_states`
- `continuity_reconciliations`
- `continuity_transaction_receipts`

The backup must also include all authoritative business tables because queue/checkpoint state without the business transaction it references is not a valid recovery point.

## PostgreSQL backup

Example using a custom-format dump:

```bash
pg_dump --format=custom --file=local-hub.dump "$LOCAL_DATABASE_URL"
```

Keep the dump outside the Local Hub machine according to the deployment backup policy. Do not place database dumps or credentials in the Git repository.

## Restore rehearsal

Restore into a fresh database first:

```bash
createdb hybrid_retail_bi_restore
pg_restore --no-owner --no-privileges --dbname=hybrid_retail_bi_restore local-hub.dump
```

Before production cutover verify:

1. Local Alembic revision matches the approved release.
2. Pending inbox/outbox rows are present.
3. Checkpoints and persisted device identity are present.
4. Dead-letter records and audit history are present.
5. Continuity state/reconciliation records are present.
6. Business tables referenced by queued events are present.
7. Start the worker in recovery mode and confirm queues drain without duplicate invoice or stock effects.
8. Run reconciliation and require a clean report before declaring the restored hub `live`.

`backend/scripts/verify_hc4_backup_restore.py` is the release-test proof used by CI. It seeds a pending outbox event, checkpoint, device identity, continuity state, and reconciliation marker before `pg_dump`; the workflow restores that dump into a new PostgreSQL database and verifies the same durable records.

## Failure handling

- Internet/Supabase unavailable: stay `offline_local`, do not clear queues, continue Local Hub authoritative operation.
- Local PostgreSQL unavailable on startup: worker retries initialization; no memory-only queue is used.
- Process/power loss after local commit: committed inbox/outbox/business state is recovered from PostgreSQL.
- Lost cloud acknowledgement: outbound retry uses the original event identity; cloud/local receipts make the business effect idempotent.
- Duplicate/out-of-order event: HC1 aggregate-version and inbox rules prevent duplicate/out-of-order application.
- Expired/stale writer lease: reacquire a new fenced epoch before recovery; stale epoch commands fail.
- Permanent sync failure: durable dead letter plus visible `attention_required` state and audited retry.

## Release gate

HC4 is continuity-ready only after the release workflow proves that outage/restart scenarios preserve acknowledged work, drain durable queues, reject stale fencing, surface dead letters, restore pending queue/checkpoint state from backup, and produce no duplicate invoice or stock effect.
