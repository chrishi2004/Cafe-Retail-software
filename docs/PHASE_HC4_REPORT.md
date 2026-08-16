# HC4 Phase Report

Status: Complete

## Verified Git State

- Source phase: HC4 - Automatic Continuity, Reconciliation, And Recovery
- Base state: P8-complete `main` at `13ec7fe55ddbc0d02bdb33114e5d05a03d038ff8`
- Tested HC4 head: `d00fa9dbf7f767e6e6bf01a8de050feaf91b53dc`
- Pull request: #13 `HC4 automatic continuity, reconciliation, and recovery`
- Merge commit: `1488f36454661bcb4304a39378c176f1d0122009`

## Migration Boundary

HC4 advances both independent migration histories while preserving the Local Hub/cloud authority boundary.

### Local Hub

- Previous head: `20260814_0015` (P8)
- HC4 head: `20260814_0016`
- Adds durable local continuity state, reconciliation reports, and continuity-reference receipts.

### Cloud coordination

- Previous head: `20260813_cloud_0001` (HC2/HC3 coordination foundation)
- HC4 head: `20260814_cloud_0002`
- Adds replay-protection nonce persistence for signed device requests and writer-lease recovery indexing.
- Row-level security remains enabled for the new coordination nonce relation.

The local and cloud histories remain separate. Cloud coordination is not promoted to financial or stock authority.

## HC4 Delivery

### Signed device heartbeat and replay protection

The Local Hub continuity client now sends signed heartbeats containing device identity, timestamp, nonce, canonical payload digest, software/schema version, fencing epoch, and queue counts.

The cloud gateway:
- authenticates the registered device and installation proof;
- validates allowed device purpose;
- validates timestamp freshness;
- validates HMAC-SHA256 over device/timestamp/nonce/payload digest;
- records a `(device_id, nonce)` replay-protection receipt;
- rejects reused nonces;
- rejects stale or invalid signatures;
- keeps revoked-device behavior fail-closed;
- returns the server-registered business-group/company/branch scope rather than trusting browser-provided scope.

No plaintext device secret is persisted in cloud coordination or exposed to the frontend bundle.

### Writer lease and fencing

HC4 activates the existing cloud writer-lease concept as an enforced recovery boundary.

Behavior:
- first acquisition begins at fencing epoch 1;
- an active lease cannot be displaced by another device;
- renewal requires the exact active owner and current epoch;
- an expired lease must be reacquired;
- takeover/reacquisition after expiry increments the fencing epoch monotonically;
- stale epochs fail closed;
- the Local Hub persists its currently observed epoch and lease expiry in continuity state.

The fencing token is used to prevent a stale/recovered device from acting as a competing financial writer.

### Continuity references

Cloud continuity may durably capture only explicitly approved continuity references such as emergency payment references or order notes.

A continuity reference:
- requires current authorized device scope;
- requires the current fencing epoch;
- is idempotent by continuity reference + normalized payload;
- rejects replay with changed content;
- is stored as `pending_reconciliation`;
- emits a durable synchronization command for Local Hub processing.

The cloud path does **not** create or mutate authoritative invoices, customer-ledger entries, stock movements, inventory, or financial closing state. Final business effects remain Local PostgreSQL authority.

### Automatic recovery worker

The Local Hub synchronization worker now performs the HC4 recovery sequence automatically:

1. load/create persisted device identity;
2. retry Local PostgreSQL dependency startup if temporarily unavailable;
3. send signed heartbeat when cloud coordination is configured;
4. validate or acquire the scoped writer lease/fencing epoch;
5. persist `synchronizing` recovery state;
6. pull cloud commands and commit them to the durable local inbox;
7. process inbound commands idempotently;
8. push durable local outbox events;
9. preserve retryable failures in the queue;
10. move permanent/exhausted failures to durable dead letters;
11. when the queues reach a drain point, run reconciliation;
12. report `live` only after fresh cloud contact, valid fencing, empty drainable queues, and clean reconciliation.

If cloud coordination is unreachable, the Local Hub remains `offline_local`; committed outbound work stays durable and Local PostgreSQL continues as business authority.

Explicit direct/in-process transport remains supported for the inherited HC1-HC3 test/runtime contract without weakening real configured-gateway fencing.

### Continuity states

Persisted and operator-visible states:
- `live`
- `offline_local`
- `cloud_continuity`
- `synchronizing`
- `stale`
- `attention_required`

`stale` is derived from real heartbeat freshness and lease expiry, with timezone-normalized comparisons across PostgreSQL/SQLite test environments.

A clean manual Local Hub reconciliation without a fresh successful cloud heartbeat remains `offline_local`, not falsely `live`.

### Reconciliation

HC4 reconciliation persists an auditable report and checks authorized scope for:
- Cafe billed/closed order-to-invoice linkage;
- invoice arithmetic (`paid + balance = grand total`);
- payment rows against invoice paid amount;
- linked-product invoice items against stock movements;
- closed table sessions against fully settled invoices;
- pending inbound/outbound queue counts;
- unresolved dead-letter records;
- continuity/reference evidence available to Local Hub.

A clean report may return a freshly connected and fenced worker to `live`. Any financial/stock/closing mismatch or unresolved durable failure produces `attention_required` instead of being silently overwritten.

No last-write-wins behavior is introduced for financial or stock state.

### Dead-letter visibility and audited retry

Authorized Local Hub users can inspect scoped dead letters and, for permitted roles, invoke the existing HC1 durable retry path.

Manual retry:
- preserves the original event identity;
- returns the event to durable retry state;
- increments retry evidence;
- records the existing `sync.dead_letter.retry` audit event;
- remains company/branch scoped.

The generic SQLAlchemy scope guard was extended for string-valued synchronization/continuity scope identifiers instead of bypassing venture isolation.

### Operator visibility

The Cafe continuity dashboard exposes:
- current continuity mode;
- inbound/outbound pending counts;
- dead-letter count;
- fencing epoch;
- lease expiry;
- last heartbeat;
- last cloud contact;
- last inbound/outbound sync;
- last queue drain;
- last reconciliation result;
- attention reason;
- scoped dead-letter review and permitted retry.

Admin/store-manager roles may run reconciliation/retry; analyst access remains read-only. Kitchen and unrelated portal boundaries remain unchanged.

## Backup And Restore Proof

HC4 includes `backend/scripts/verify_hc4_backup_restore.py` and a release workflow that performs a real PostgreSQL recovery rehearsal.

The workflow:
1. seeds a pending outbox event;
2. seeds a persisted checkpoint;
3. seeds persisted device identity;
4. seeds continuity state and fencing epoch;
5. seeds a reconciliation record;
6. runs `pg_dump` in PostgreSQL custom format;
7. creates a new empty PostgreSQL database;
8. restores the dump with `pg_restore`;
9. connects to the restored database;
10. verifies the pending queue row, checkpoint, device identity, continuity state, and reconciliation evidence all survived with their expected values.

The final tested head passed the entire seed/dump/restore/verification chain.

The runbook `docs/HC4_CONTINUITY_RUNBOOK.md` documents the required backup scope, startup order, writer-fencing behavior, recovery sequence, restore rehearsal, and failure-handling rules.

## Verification

All twelve verification workflows passed on the exact tested HC4 head `d00fa9dbf7f767e6e6bf01a8de050feaf91b53dc`:

- HC1
- P1
- P2
- P3
- P4
- P5
- P6
- P7
- P8
- HC2
- HC3
- HC4

HC4 workflow results:
- HC4 release-blocking continuity tests: **12 passed**
- inherited outage/idempotency/financial-safety tests: **23 passed**
- complete backend regression: **222 passed, 11 skipped**
- backend/application/script compile: passed
- local PostgreSQL migration rehearsal through `20260814_0016`: passed
- cloud PostgreSQL migration rehearsal through `20260814_cloud_0002`: passed
- independent local/cloud migration-head check: passed
- HC4 frontend boundary verifier: passed
- authenticated portal-boundary verifier: passed
- browser server-secret scan: passed
- TypeScript typecheck: passed
- production frontend build: passed
- backup-proof seed: passed
- PostgreSQL `pg_dump`: passed
- restore into fresh PostgreSQL database: passed
- restored queue/checkpoint/device/continuity/reconciliation verification: passed

### Failure cases exercised

Automated HC4 coverage includes:
- valid signed heartbeat accepted once;
- heartbeat nonce replay rejected;
- stale signed heartbeat rejected;
- expired writer lease reacquisition increments fencing epoch;
- stale lease renewal rejected;
- stale continuity-reference epoch rejected;
- same continuity reference + same payload is idempotent;
- same continuity reference + changed payload is rejected;
- cloud outage leaves Local Hub outbox pending and durable;
- cloud outage reports `offline_local`;
- recovery obtains fencing, drains durable outbox, and reconciles;
- explicit inherited HC3 transport contract remains functional;
- clean financial/stock/table reconciliation;
- expired/stale heartbeat state becomes visibly `stale`;
- injected financial mismatch becomes `attention_required`;
- permanent synchronization failure becomes a visible dead letter;
- manual dead-letter retry remains audited;
- backup/restore preserves pending continuity state.

## Compatibility Gate Repairs

HC4 legitimately advances both migration histories and adds three explicitly approved cloud continuity endpoints. Several older workflows had historical assertions that treated the then-current migration head or cloud route set as permanently final.

Those gates were made forward-compatible without removing their functional test suites:
- P6/P7/P8 and HC2/HC3 now verify their required historical revisions remain in migration history while local/cloud heads stay separate;
- the cloud deployment allowlist remains exact and now includes only the three HC4 continuity endpoints;
- the legacy `DATABASE_URL` fallback unit test explicitly clears `LOCAL_DATABASE_URL` so CI environment variables cannot alter the condition it claims to test.

No inherited functional release suite was removed to make HC4 pass.

## Exit Gate

HC4 is complete when outage/restart recovery can preserve acknowledged work, enforce single-writer fencing, drain durable queues, surface permanent failures, reconcile authoritative business effects, and restore queue/checkpoint/device/recovery evidence from backup without creating duplicate invoice or stock effects.

That exit gate passed on the exact tested head above.

HC4 did not start P9 or later reporting/governance/security phases. The next phase must be selected from the current repository dependency order before any further implementation begins.
