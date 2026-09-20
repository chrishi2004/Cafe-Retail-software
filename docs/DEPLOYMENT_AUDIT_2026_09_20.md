# Deployment audit and completion plan — 20 September 2026

## Decision

**NO-GO for public users. The core application is substantially implemented, but the product is not proven complete end to end.**

This audit starts from `main` commit `c574fdf6946bb01b8d9ae65d990cb3423c6ccfb7`. Release PR #10 is merged. The subsequent open draft PR #11 adds only the pause handoff and operational requirements documents; it contains no additional application implementation. Do not restart P1–P11 or HC0–HC4 as if they were unimplemented.

The final operating model fixes deployment routing; it does not prove that every feature in the older 21-phase Hitech expansion has been delivered. A finished core Retail/Cafe release and the full competitive expansion are different completion claims.

## Evidence and limits

- Inspected the complete recursive repository inventory (511 entries), retrieved all 468 non-binary files, and reviewed release documents, CI workflows, configuration, user-facing routes, security, billing, synchronization, deployment scripts and relevant tests. The historical PDF playbook and raster assets were excluded from executable verification. This is a risk-focused audit, not a claim that every code path has been exercised.
- GitHub Release Readiness run [32485293956](https://github.com/chrishi2004/Cafe-Retail-software/actions/runs/32485293956) passed on 21 August. Logs show **45 targeted tests passed** and **255 full-regression tests passed**, successful migrations, dependency audits, build and disposable backup restore.
- That run checked out PR merge `af3af4d` for documentation head `a187148ff917634bf8f5729239c11261266f22f2`, not the exact current main SHA. GitHub compare confirms only two documentation files differ from main. This supports the application baseline, but does not replace release evidence for the final deployment commit.
- Latest status attached to main: frontend Vercel check succeeded; API Vercel check failed with “Deployment rate limited — retry in 24 hours.” This is an August status record, not proof the quota is still exhausted today.
- Current Vercel account inspection returned no teams and a 403 for the repository-linked `rishichaudhari` scope. Production URLs, environment values, database state and current deployment readiness remain unverified.
- `main` is currently reported as **unprotected** by GitHub.
- P3 Ready Gate [32485840468](https://github.com/chrishi2004/Cafe-Retail-software/actions/runs/32485840468) failed because `markPullRequestReadyForReview` returned “Resource not accessible by integration.” This is a PR-management permission failure, not a failed P3 application suite. Do not weaken application tests to make this administrative check green.
- The original browser suite uses mocked HTTP responses for two smoke tests. It does not start the operational API, cloud API, sync worker or PostgreSQL. It cannot establish a real QR → kitchen → invoice → payment → stock journey.
- Many backend tests use in-memory SQLite (`tests/conftest.py`). Separate cloud/PostgreSQL checks exist, but SQLite success alone does not demonstrate production locking and concurrency.

## Gate matrix

| Gate | Evidence/status at audited main | Required before go-live |
| --- | --- | --- |
| Core Retail/Cafe implementation | Substantial implementation with historical regression success | Apply reviewed fixes; rerun release gates |
| Hosted customer bill request | **Defect found:** cloud customer button hidden | Merge and verify this audit's fix |
| Environment bootstrap | **Defect found:** empty optional MFA boolean in supplied template | Verify corrected settings behavior |
| Exact deployment commit CI | No unified release run attached to main; trigger only covered old release branch/PRs | Run all gates on release SHA; retain evidence |
| Browser business journeys | Mocked smoke only | Real services + PostgreSQL + sync-worker E2E and device acceptance |
| Hosted frontend | Historical success | Verify final domain, release SHA and API routing |
| Cloud gateway | Historical quota failure; current account access denied | Authorized provider inspection; production Ready + readiness response |
| Local/cloud production migrations | No current environment evidence | Local `20260821_0019`; cloud `20260821_cloud_0003` on intended distinct DBs |
| Local Hub boot/runtime | Handoff says final machine not installed | Install services; reboot; prove automatic recovery |
| Device registration/menu publication | Handoff says incomplete | Register trusted device; publish safe menu; verify timers and queue drain |
| Production security | MFA/security code present; environment not verified | Enroll admins; rotate demo secrets; private DB; HTTPS; edge limits; protect main |
| Backup/recovery | Historical CI restore success | Independent backup plus restored business totals/queues on real equipment |
| Monitoring | Operational requirements exist; delivery not proven | Working alerts and tested delivery to the designated operator |
| Physical user acceptance | No signed/current evidence | Phones, POS, waiter, kitchen, owner, printer/scanner, outages and UPS |

## Defects corrected by this audit change set

1. **Customer cannot request a bill:** `CafeOrderStatus.tsx` rendered the button only for `continuityMode === "local"`, while the hosted route always opens a cloud session. Expose the existing safe cloud command and keep its confirmed request state in the current session. Failed requests retain the retry key; payment remains a staff operation. Refreshing the browser may show the request action again, but the same stored key keeps that retry idempotent.
2. **False outage message:** the customer page treated cloud routing as proof the Hub was unreachable. Cloud is the normal route. Replace this with customer-facing order-confirmation guidance.
3. **Premature confirmation:** a queued `awaiting_cafe_confirmation` order was shown as “confirmed.” Show that it is waiting for staff confirmation.
4. **Copied configuration can fail startup:** ignore empty environment values so blank optional MFA configuration uses the existing environment-dependent default; non-empty invalid boolean values still fail validation. Added regression coverage.
5. **Release evidence gap:** run Release Readiness on main pushes and retain JUnit/browser reports with the run SHA. No existing test or deployment gate is disabled.
6. **Weak customer smoke assertion:** replace a fixed delay/zero-call-only assertion with visible invalid-QR state and positive cloud request evidence. Add a cloud ordering → failed bill request → same-key retry → confirmation browser regression. This remains a mocked contract test and is not labelled full-stack E2E.
7. **Concurrent MFA recovery-code reuse risk:** login read and consumed recovery codes without locking the user row. Serialize login consumption with PostgreSQL row locking and add a two-request PostgreSQL regression in a disposable schema. This gate must execute successfully in release CI; a local skip is not proof.

## Implementation coverage

| Area | Repository evidence | Assessment |
| --- | --- | --- |
| Users, ventures, roles and branch scope | auth/ventures routes, scoping, cross-venture tests | Implemented; production accounts/MFA still required |
| Products, customers, stock and ledgers | product/customer/inventory services and pages | Implemented core flows |
| Retail POS and invoices | POSPage, invoices routes/service, checkout tests | Implemented core billing; full print/return expansion not established |
| Purchase orders and receiving | purchase_orders service and tests | Implemented; not equivalent to purchase-bill/supplier-ledger accounting |
| Cafe tables/menu/QR/orders/kitchen/billing | Cafe pages/services, P5–P8 tests | Implemented; customer bill-action defect corrected here |
| Reporting, forecasting and AI | reporting/dashboard/export/forecast/AI services | Implemented baseline; advanced copilot is separate |
| Governance | closing/void/purge/audit services and tests | Implemented; void is not a complete item-level return/refund/credit-note module |
| Hybrid continuity | cloud coordination, sync worker, HC1–HC4 suites | Implemented; actual hosted/local recovery still needs acceptance |
| Linux runtime | systemd units, backup and publisher scripts | Packaged; not installed on the actual Hub in this session |
| Installed/offline PWA | locally served React app; no service-worker/manifest found | LAN serving supports internet-loss operation while Hub stays up; do not promise cached autonomous operation or an installable PWA without further implementation |

## Completion phases

### Phase A — finish and verify the release candidate

Owner: development/repository maintainer.

- Review this patch and preserve the operational handoff from PR #11.
- Run complete backend, cloud/PostgreSQL migrations, frontend build, browser regression and dependency checks on the exact final commit. Do not substitute old green checks.
- Run a real full-stack browser journey with seeded disposable local/cloud databases and the sync worker: customer QR/order → import → staff acceptance → kitchen preparation → service → bill request → invoice/payment → receipt → stock/ledger/report totals. Add Retail checkout, credit collection and PO receiving journeys.
- Prove real concurrent last-stock sale and duplicate billing on PostgreSQL; sequential stale-version tests are not equivalent to parallel transactions.
- Verify the new concurrent recovery-code test against PostgreSQL, including the one-success/one-rejection result. Do not accept a skipped test as evidence of one-time consumption.
- Protect main with PR/release requirements using authorized repository settings. Resolve the P3 Ready Gate integration permission explicitly, or replace automatic PR-state mutation through a reviewed governance decision; do not silently swallow failure.

Exit: exact candidate has green CI, real business-journey evidence, and no unresolved security/financial-integrity defect.

### Phase B — install the production Local Hub

Owner: Hub operator with access to the physical machine.

- Follow `LOCAL_HUB_LINUX_DEPLOYMENT.md`: OS dependencies, service account, protected environment file, local PostgreSQL role/database, migration, separate LAN frontend build, API/sync/frontend services and backup/publication timers.
- Set stable LAN address, timezone/NTP, firewall, log retention, storage thresholds and UPS behavior.
- Initialize real company/branch/menu/tables/users and opening inventory; do not use demo seed data for live sales.
- Validate tax mode, business details, invoice numbering and actual receipt layout with the business operator.

Exit: services start without desktop login after reboot, local operations work with internet disconnected, database is not public, business data is reconciled.

### Phase C — complete cloud and remote connectivity

Owner: authorized Vercel/Supabase administrator and Hub operator.

- Restore access to the correct Vercel scope; inspect current API deployment rather than assuming August's quota condition persists.
- Configure the intended Supabase coordination database, protected runtime/migration credentials and separate cloud migration history.
- Verify frontend and gateway production deployments for the chosen release; check `/api/cloud/readiness` and absence of operational write routes on the gateway.
- Register the Hub device, publish the first customer-safe menu and verify recurring publication, heartbeat and synchronization.
- Configure final HTTPS origins/CORS and an approved tunnel/private path to the operational API. Keep PostgreSQL private. Enroll every privileged production user in MFA.

Exit: a phone on mobile data can order and request the bill; the actual Hub imports commands; remote owner accesses the correct live authority.

### Phase D — operational recovery and monitoring

Owner: operator/developer together.

- Exercise internet loss with LAN intact, Hub restart, queued cloud ordering during Hub outage, duplicate deliveries, queue recovery and UPS shutdown/restart.
- Store backups off the Hub SSD; restore to a disposable DB and reconcile invoices/payments/stock/users/queues, not just table existence.
- Test alert delivery for API/DB/worker failure, menu publication failure, backup age, disk space, dead letters, stale heartbeat, unhealthy lease and tunnel failure. Choose the operator and delivery destination before enabling external messages.
- Record recovery objectives, restore procedure, secret rotation and rollback steps.

Exit: recovery and independent restore are demonstrated; alerts reach the operator; evidence is attached to the release record.

### Phase E — controlled pilot and public release

- Test simultaneous POS/waiter/kitchen/manager sessions on intended devices; test the real printer, scanner and any cash drawer.
- Run a complete controlled trading/closing cycle and reconcile totals, outstanding balances and stock with expected results.
- Resolve pilot defects, rerun affected gates and complete every applicable `PRODUCTION_GO_LIVE_CHECKLIST.md` item.
- Deploy/promote only the verified release. Record deployed SHA, domains, migration versions, evidence and rollback target.

Exit: business owner accepts the actual installation. Only then label it public-production ready.

### Phase F — finish the wider competitive expansion separately

The older Hitech add-on documents contain requirements beyond the release operating model. The current route/service/page inventory does not establish complete delivery of all of these:

- Dedicated A4/80 mm invoice/PDF templates, reprint behavior and barcode label printing.
- Item-level sales returns/refunds/credit notes; full purchase bills/returns and supplier ledger.
- Cash register/shift reconciliation, expense accounting and accounting reports beyond existing Cafe closing/reporting.
- Dedicated GST return exports and live e-invoice/e-way-bill provider workflows (tax calculation settings are not those integrations).
- Bulk migration/import tools, invoice messaging integrations and staff commissions.
- Purchase-bill photo/PDF OCR with human review before stock posting; advanced AI/local LLM features.
- Finished Power BI `.pbix` deliverable; current `powerbi` directory is a placeholder.

For each feature chosen for the next release: map its original acceptance criteria, implement schema/API/UI, prove authorization/idempotency/accounting, then add end-to-end acceptance. Do not claim the whole 21-phase expansion is complete. Conversely, do not block the frozen core release on optional future AI merely because it appears in a roadmap. Returns or printing required by the actual business must be promoted into Phase A before taking that business live.

## Required access to finish external work

- Authenticated access to the physical Local Hub, or execution from Codex on that machine.
- Vercel authorization for the existing `rishichaudhari` projects and the intended Supabase project.
- Final business data, approved domains, staff/device list, backup target and alert recipient/channel.

No production installation, migration, deployment promotion, account enrollment or physical acceptance was performed by this audit. No real customer data was modified. Do not paste production secrets into the report or chat.

## Validation of this change set

Fresh local results:

- Backend regression after the configuration fix: **239 passed, 18 skipped** (PostgreSQL/cloud-dependent coverage unavailable locally).
- Targeted authentication/configuration tests after the login locking change: **27 passed, 1 skipped**. The skipped test is the new PostgreSQL concurrent recovery-code proof.
- Frontend typecheck and production build: **passed**. Build warns about a large application chunk; this is a performance follow-up, not a test failure.
- Chromium browser contract/smoke tests: **3 passed**, including cloud order → failed bill request → retry with the same key → disabled confirmation button.
- Python compilation, JavaScript syntax, shell syntax and diff whitespace checks: **passed**.
- A local PostgreSQL installation attempt was blocked by this runtime's package-management permissions. No production database was touched. PostgreSQL migrations, cross-database convergence, fresh dependency audits and the new concurrency test still require the exact candidate's CI run.

The local full regression started before the final login-lock edit; the targeted authentication run covers that edit. These results do not certify production infrastructure or real full-stack E2E. Historical CI evidence above is explicitly separate from this patch's validation.
