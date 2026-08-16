# HC1 Phase Report: Durable Local Synchronization Foundation

## Status

- Phase: HC1
- Status: Complete
- Date: 2026-08-11
- Base: HC0 commit `70068c6`
- Merge commit: `259577831590390659888cc0df807c24a06aee5d`
- Local Alembic revision: `20260811_0007`
- Cloud Alembic history: unchanged and separate

## Scope Implemented

HC1 establishes the crash-safe Local Business Hub synchronization substrate. It intentionally does not implement Supabase QR order acceptance, cloud business tables, Cafe order intake, writer leases, continuity financial processing, or HC2+ behavior.

Implemented:

- durable local `sync_devices`, `sync_outbox`, `sync_inbox`, `sync_checkpoints`, `sync_dead_letters`, and `sync_aggregate_versions` tables;
- versioned event envelopes with event, correlation, causation, scope, aggregate, idempotency, and UTC timestamp metadata;
- transactional outbox helper that never commits independently;
- durable inbox receipts and idempotent redelivery behavior;
- per-aggregate monotonic version checks with visible blocked/dead-letter states;
- persisted inbound/outbound checkpoints;
- bounded batch processing;
- exponential retry with jitter, maximum delay, and `Retry-After` support;
- graceful worker shutdown and disposable process-memory design;
- persistent device identity with credential-reference storage only;
- development restart supervisor and documented production service policy;
- audited dead-letter retry using the existing audit ledger;
- release-blocking HC1 and HC0 regression tests;
- GitHub Actions verification using PostgreSQL 16 plus frontend regression checks.

## Failure And Recovery Evidence

Automated tests cover:

1. Domain change and outbox event commit together.
2. Domain rollback removes the outbox row with the domain change.
3. Duplicate delivery creates exactly one business effect.
4. Lost acknowledgment followed by redelivery returns the durable prior receipt.
5. Worker recreation against the same database resumes pending inbox work and advances the persisted checkpoint.
6. Future aggregate versions remain visibly blocked until the missing version commits.
7. Dead-letter retry is durable and writes an audit record.
8. Unknown future event schema versions remain durable and visible.
9. Raw device secret values are not persisted.
10. Retry delay is bounded and honors explicit `Retry-After` values.

## Queue And Checkpoint State In Tests

The HC1 tests use isolated database fixtures. Each test begins with no synchronization rows and tears down its database after verification, so no persistent CI queue, dead-letter, or reconciliation state remains after the suite. Restart tests explicitly verify checkpoint persistence across new worker instances using the same test database.

## Security Boundary

- Local PostgreSQL remains the operational system of record.
- No raw device secret is stored in PostgreSQL or committed environment templates.
- No Supabase service-role key or cloud credential was added.
- No public/cloud QR write route was added.
- HC0 cloud fail-closed route registration remains part of the required regression suite.
- RLS is not applicable in HC1 because the Supabase coordination schema is an HC2 deliverable.

## Verification

GitHub Actions workflow `HC1 Verification`, run `31483717272`, completed successfully against the PR merge candidate containing current `main` plus the HC1 branch.

Verified:

- PostgreSQL 16 service startup: passed;
- local Alembic upgrade through `20260811_0007`: passed;
- local migration head: `20260811_0007`;
- cloud migration history remained separate and unchanged;
- HC1 + deployment targeted suite: **18 passed**;
- complete backend regression: **111 passed**;
- backend `compileall`: passed;
- frontend dependency install: passed;
- frontend typecheck: passed;
- frontend production build: passed.

An earlier workflow run exposed CI environment-variable leakage into an HC0 settings-isolation test. Commit `7be4863` corrected the workflow so PostgreSQL connection variables are scoped only to Alembic steps. The clean rerun then passed all gates.

## Exit Gate

**HC1 exit gate passed.** The local consumer now has automated evidence for idempotent crash/restart recovery and safe redelivery.

This does **not** authorize Supabase QR order acceptance yet. QR acceptance remains blocked until HC2 completes the Supabase coordination schema, RLS/security boundary, limited cloud gateway, publication integrity, and its own exit gate.

## Known Deferred Work

- Supabase coordination schema and RLS: HC2.
- Vercel cloud sync/QR gateway: HC2.
- Cloud order intake and local convergence: HC3.
- Heartbeats, writer leases, fencing, automatic continuity reconciliation: HC4.
- Venture/Cafe feature work continues according to the integrated dependency order rather than being pulled into HC1.
