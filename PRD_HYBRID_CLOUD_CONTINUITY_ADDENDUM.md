# Product Requirements Addendum: Hybrid Cloud Continuity

## Document Status

- Version: 1.0
- Status: Approved architecture addendum; implementation not started
- Last updated: 2026-08-11
- Applies to: Retail, Cafe, customer QR ordering, remote administration, billing, and synchronization

## 1. Purpose And Precedence

This addendum changes the deployment model from local-only data access through a tunnel to an approved Vercel, Supabase, and local PostgreSQL hybrid. It adds automatic continuity and recovery requirements for internet loss, local device restart, and local power loss.

Future implementation agents must read this document after the existing product PRDs and before the hybrid technical requirements. Where an older document requires one deployment or prohibits a second database, this approved addendum controls. Existing venture isolation, billing, stock, ledger, audit, tax, and AI integrity rules remain mandatory.

This addendum does not make Supabase a second inventory or accounting authority.

## 2. Approved Product Decision

The product will use one codebase with two controlled runtime profiles:

1. A Local Business Hub runs the complete operational FastAPI service, local PostgreSQL, synchronization worker, local web build, and backup jobs.
2. Vercel hosts the public React application and a limited cloud FastAPI gateway.
3. Supabase PostgreSQL stores cloud coordination records, published read models, durable customer order intake, continuity events, and synchronization state.
4. A secure tunnel may expose selected authenticated Local Hub APIs for live remote operations.
5. The local PostgreSQL database remains the system of record for inventory, invoices, payments, ledgers, stock movements, closing, and complete audit history.

One shared React codebase may be built for both the Vercel portal and the local operational portal. A native Windows, Android, or iOS application is not required for the MVP.

## 3. Product Goals

- Keep local POS and operational work available during internet loss.
- Keep customer QR order intake and cloud-safe staff workflows available during Local Hub power or device loss when internet access remains available.
- Automatically resume synchronization from the last durable checkpoint after power or connectivity returns.
- Never duplicate an order, invoice, payment, stock movement, or ledger effect because of retries.
- Never allow local and cloud systems to become competing financial writers.
- Show users whether data is live, queued, awaiting Cafe confirmation, synchronizing, or stale.
- Preserve venture, company, branch, role, and customer isolation in both databases.

## 4. Data Authority

| Data or action | Authority | Cloud behavior |
| --- | --- | --- |
| Products, prices, menu availability | Local Hub | Published versioned snapshot |
| Customer QR submission | Cloud gateway until imported | Durable queued order |
| Staff acceptance and preparation | Local Hub in normal mode | Status mirror |
| Final invoice and invoice number | Local Hub | Sanitized reference or snapshot |
| Payment and customer ledger | Local Hub | Continuity event only until reconciled |
| Inventory and stock movement | Local Hub | Last-synchronized availability snapshot |
| Purchase and supplier records | Local Hub | Optional reporting snapshot |
| Dashboard summaries | Local Hub calculations | Timestamped cloud read model |
| Synchronization status | Shared protocol | Stored on both sides |

Supabase must not directly increase or decrease authoritative inventory. A cloud order does not reduce stock. Stock changes occur only when the Local Hub executes the existing invoice, sale, purchase receiving, return, or adjustment rules.

## 5. Functional Requirements

### 5.1 Durable Queue And Resume

- `HC-FR-001`: Every cloud-to-local and local-to-cloud write must receive a globally unique event ID.
- `HC-FR-002`: A producer must persist an event before reporting it as queued.
- `HC-FR-003`: A consumer must acknowledge an event only after its database transaction commits.
- `HC-FR-004`: Unacknowledged events must be retried automatically after network or process recovery.
- `HC-FR-005`: The Local Hub must resume from its last durable checkpoint after application, operating-system, or power restart.
- `HC-FR-006`: Re-delivering the same event must return the previous result or no-op without duplicating business effects.
- `HC-FR-007`: Events for the same order, table session, invoice, or other aggregate must be applied in valid sequence.
- `HC-FR-008`: Repeated failures must move an event to a visible dead-letter state without silently discarding it.
- `HC-FR-009`: Authorized users must be able to inspect failed synchronization records and request a safe retry.
- `HC-FR-010`: Queue depth, oldest pending age, last successful synchronization, and Local Hub heartbeat must be visible to authorized users.

### 5.2 Internet Outage

- `HC-FR-011`: The Local Hub must continue local login, POS, staff order entry, billing, inventory, and printing-capable workflows when the internet is unavailable.
- `HC-FR-012`: Local changes made during an outage must be recorded in a transactional outbox.
- `HC-FR-013`: When connectivity returns, the synchronization worker must automatically upload pending events without requiring manual export or restart.
- `HC-FR-014`: The worker must use bounded exponential retry with jitter and must not overload the cloud service after reconnection.
- `HC-FR-015`: Remote users must see a clear last-synchronized timestamp instead of mistaking stale data for live data.

### 5.3 Local Power Or Device Outage

- `HC-FR-016`: Public QR menu and customer order submission must remain available through Vercel and Supabase while the Local Hub is offline.
- `HC-FR-017`: Cloud orders created while the Local Hub is offline must show `awaiting_cafe_confirmation` until a permitted Cafe user or Local Hub accepts them.
- `HC-FR-018`: Cloud-safe order queue and kitchen views may continue on powered phones, tablets, or other devices when configured for continuity mode.
- `HC-FR-019`: The cloud must not claim that stock is guaranteed when its inventory snapshot is stale.
- `HC-FR-020`: Payment or emergency receipt capture during continuity mode must use unique continuity references and remain pending reconciliation until committed locally.
- `HC-FR-021`: Final financial, stock, and ledger effects must be reconciled through the Local Hub exactly once.
- `HC-FR-022`: The Local Hub services must start automatically after the host operating system restarts.
- `HC-FR-023`: After restart, the Local Hub must recover its database, read its checkpoints, pull pending cloud events, push local outbox events, and continue without resetting queues.

### 5.4 Writer Safety And Recovery

- `HC-FR-024`: Normal and continuity processing must use an active-writer lease or fencing epoch to prevent split-brain financial writes.
- `HC-FR-025`: A recovered Local Hub must not resume authoritative writes until it validates its lease and required reconciliation state.
- `HC-FR-026`: A stale device or worker must be unable to overwrite a newer order or synchronization state.
- `HC-FR-027`: Conflict handling must be deterministic, audited, and visible; last-write-wins is not allowed for financial or stock records.
- `HC-FR-028`: Deletes synchronize as controlled tombstones or reversal events, never as silent row removal.
- `HC-FR-029`: Recovery must preserve original actor, business date, source device, event time, and processing time.

### 5.5 User Experience

- `HC-FR-030`: The UI must display `live`, `offline_local`, `cloud_continuity`, `synchronizing`, `stale`, or `attention_required` state where operationally relevant.
- `HC-FR-031`: A customer must receive one durable public order reference after a cloud order commit.
- `HC-FR-032`: Duplicate taps or browser retries must return the same order reference for the same idempotency key.
- `HC-FR-033`: Staff must not see a cloud-queued order as accepted until acceptance is committed.
- `HC-FR-034`: The Final Super Admin and Cafe Partner Admin must see last heartbeat, last sync, queue counts, and reconciliation warnings within their allowed scope.
- `HC-FR-035`: The local device must provide an application-style browser/PWA shortcut and a local address for operation when Vercel is unreachable.

## 6. Local Device Requirement

At least one owner-controlled Local Hub device is required when local PostgreSQL remains the operational system of record. The Local Hub may be a Windows PC, laptop, mini PC, or small server.

The MVP installation must include:

- PostgreSQL;
- the Local Hub FastAPI service;
- the synchronization worker;
- a local build of the React interface;
- automatic service startup;
- scheduled backup and health checks;
- optional printer bridge only when hardware automation is introduced.

The same physical device may also be the billing terminal. A UPS for the Local Hub and network equipment is recommended but does not replace cloud continuity.

## 7. Security Requirements

- React clients must never receive Supabase secret or service-role credentials.
- Cloud database access must go through the cloud backend except for explicitly approved, RLS-protected public data access.
- Every cloud row and event must carry business-group, company, branch, purpose, and schema-version context where applicable.
- Device synchronization uses revocable device credentials, TLS, replay protection, timestamps, and nonce or request-signature validation.
- Supabase policies must fail closed across ventures and branches.
- Public QR data must exclude cost, inventory internals, tax settings, user data, audit details, and customer PII not required for ordering.
- Secrets and raw QR tokens must not be stored in queue payloads or logs.

## 8. Reliability Targets

- The Local Hub should start its services automatically within five minutes of operating-system startup under normal hardware conditions.
- Synchronization should begin within sixty seconds after connectivity and dependencies become healthy.
- A recovered worker must continue from persisted state, not from an empty in-memory queue.
- The normal retry path must require no user intervention.
- Any event that cannot be processed automatically must remain durable and visible until resolved.
- A continuity or recovery test must prove zero duplicate invoices and zero duplicate stock movements.

These are MVP operational targets, not a formal service-level agreement.

## 9. Acceptance Scenarios

### Scenario A: Internet Loss During Local Billing

1. Staff completes local sales while the internet is disconnected.
2. Invoices, payments, stock movements, and outbox events commit locally.
3. Internet returns.
4. The worker starts automatically and publishes all pending events.
5. Cloud dashboards update without duplicate financial effects.

### Scenario B: Local Power Loss With Internet Available

1. The Local Hub heartbeat expires.
2. Vercel continues serving the QR portal.
3. Supabase durably queues customer orders.
4. Customers see `awaiting_cafe_confirmation` until the Cafe can process the order.
5. Powered staff devices may use approved cloud continuity views.
6. No cloud action changes authoritative inventory.

### Scenario C: Automatic Restart And Queue Drain

1. The Local Hub loses power with unprocessed cloud and local queue entries.
2. Power returns and the operating system starts.
3. Local services start automatically.
4. The worker loads its checkpoint, validates writer state, pulls cloud entries, and pushes local entries.
5. Every event is acknowledged only after commit.
6. Queue counts reach zero or a visible attention state without data loss.

### Scenario D: Duplicate Delivery

1. A cloud order or local event is delivered repeatedly because a response was lost.
2. The consumer recognizes its event or idempotency ID.
3. The original committed result is returned.
4. No duplicate order, invoice, payment, ledger entry, or stock movement is created.

## 10. Definition Of Done

The hybrid continuity expansion is complete only when:

- Local PostgreSQL remains the authoritative operational database.
- Vercel and Supabase support public QR and approved cloud continuity workflows.
- The Local Hub restarts automatically and resumes from persisted checkpoints.
- Internet-loss and power-loss tests pass with no lost acknowledged event.
- Duplicate and out-of-order delivery tests pass.
- Venture and branch isolation is enforced in local and cloud paths.
- Users can see synchronization freshness and failures.
- Backup, restore, device replacement, key rotation, and reconciliation are documented and tested.

