# Kalpvriksh native Next.js implementation update

Date: 19 October 2026 (India). Target branch: `main`.
Baseline: merged rewrite commit `9a80860d2db2744f6391744100d542b6640c5580`.

## Result and boundaries

The hosted application's operational workflows now have native TypeScript/MongoDB services. The inventory dashboard error that triggered this update is implemented. The source API inventory no longer labels 119 operations as pending. This is a web implementation, **not a claim of identical legacy request/response semantics, physical acceptance, or production certification**.

The original 34 logical screens remain, with one additional Retail closing route: **35 logical screens**. One Next.js catch-all page and one API Route Handler dispatch these screens and services; this does not require separate frontend/backend deployments.

| Source operation entries | Classification |
| --- | --- |
| 158 | Native web services, including the shared cloud/operational health entry |
| 5 | Local sync status/reconciliation interfaces replaced by single-database health/integrity checks |
| 15 | Explicitly retired Local Hub interfaces: 14 old cloud gateway operations and the operational dead-letter retry operation |

Of the **163 original operational operations**, 162 dispatch to native services/domain validation. The remaining Local Hub dead-letter retry operation returns 410 because this hosted application has no Local Hub delivery queue. The 15-entry cloud inventory has one shared health operation; its other interfaces belong to the preserved hybrid system. Counts are operation entries, not unique URL files. See `NEXTJS_API_PARITY.csv` for per-operation classifications.

## Implemented workflows

| Area | Native behavior |
| --- | --- |
| Dashboards | Overview, sales, inventory valuation/health/low-stock/slow stock, purchasing, Café and owner consolidated reports; scoped filters and date ranges |
| Catalogue | Products/barcodes, categories, suppliers, branches, customers, menu, tables, payment modes and tax rates; scoped writes and audit events |
| Billing | Shared Retail/Café monetary engine, authorized prices/discounts, GST/cess calculations, Cash/UPI/Card and configured collection modes, customer credit/partial payment, drafts and draft issue/cancel |
| Transaction integrity | MongoDB snapshot transactions, conditional stock updates, branch/day locking, invoice numbering and immutable sale snapshots; payment/idempotency replay and conflicting-payload rejection |
| Customer accounts | Opening balances, invoice/payment ledger entries, credit-limit enforcement, account payments and outstanding balances |
| Purchasing | Draft/edit/submit/approve/order/partial receive/full receive/cancel, on-order stock, over-receipt protection, supplier/branch grouping from reorder lines; optional request-key replay |
| Café operations | Versioned orders, acceptance/rejection/preparation/ready/serve/bill request/cancel, kitchen queue, table session open/close, combined table bills and paid-table release |
| Customer QR | Opaque token rotation/revocation/expiry, printable QR SVG, short-lived guest capabilities, safe menu, idempotent order intake and bill requests. No guest invoice, payment or stock authority |
| Receipts | Shared receipt renderer for Café and Retail, invoice-time item/price/branding snapshots, GST breakdown, receipt-only 80mm print CSS, read-only historical Retail reprint |
| Daily closing | Separate branch/venture cash counts, expected cash/non-cash totals/variance, submit/close, owner/admin reopen with reason and credential/MFA step-up; Retail navigation added |
| Authentication | Owner/cashier role routing, active group/company/branch enforcement, TOTP, one-use recovery codes, enrollment/confirmation, protected step-up, scoped account administration and session revocation |
| Planning | Existing moving-average/trend forecast algorithm, minimum-history result, stored forecasts, demand/reorder calculation and supplier lead-time information |
| Assistant | Database-backed deterministic business answers, saved per-user/per-venture chats, write-action refusal/confirmation guidance. No paid LLM provider is required |
| Exports | Scoped sales/purchasing line CSVs, inventory, forecasts, Café and consolidated CSVs; formula-cell escaping |
| Governance | Audited void/reversal records; protected demo-only purge request/independent approval/typed execution/tombstones; financial records cannot be purged through this path |

## Automated evidence

Run from `apps/web` unless otherwise noted.

| Command | Evidence |
| --- | --- |
| `npm run typecheck` | Passed |
| `npm test` | 10 passed |
| `npm run test:integration` | 4 integration suites passed on disposable MongoDB replica sets |
| `npm run build` | Passed; Next.js production build |
| `npm run test:browser` | Passed: production Next server → Chromium → native API → disposable MongoDB |
| `npm audit --audit-level=high --json` | Zero vulnerabilities in the Next.js application dependency tree |
| `python scripts/check_cafe_v1_baseline.py` (repository root) | 396 preserved V1 files unchanged; no removals; ancestry verified |
| `node --test tests/cafe-v1.test.mjs` (original `frontend`) | Both tests passed |
| `.venv/bin/python -m pytest backend/tests -q -rs` (root) | **308 passed, 27 skipped, 1 failed**; pre-existing failure described below |

The route inventory suite sends requests to all 163 operational operation definitions and checks dispatch/domain errors, no unavailable-service result, and explicit retirement of the Local Hub retry path. **It is a dispatch coverage test, not proof that every legacy edge case has complete behavioral parity.**

The three transaction workflow suites additionally test actual Cash/UPI/Card sales, simultaneous Pay replay, stock races, receipt immutability, branch/company rejection, purchase receiving, over-receipt rejection, customer credit and payment reconciliation, draft issue, GST intra/interstate totals, table concurrency, QR isolation and price snapshots, table billing replay, MFA recovery reuse rejection, the trusted terminal MFA replacement begin/confirm commands, forecasts and chat history.

The browser scenario exercises Café checkout/receipt/next customer/logout, Retail barcode checkout/receipt print CSS, owner inventory/purchasing/forecast/settings/closing pages, and an unauthenticated customer's real QR order. Customer order submission is asserted not to create a financial invoice. Physical printing is not asserted.

### Inherited Python failure — not silently waived

`backend/tests/test_cafe_dashboard.py::test_cafe_dashboard_reconciles_orders_bills_collections_and_open_sessions` expects one order but returns zero. Its fixture uses `datetime.now(UTC)` and the test passes a UTC end date, while the legacy report interprets date filters as India business dates. After India midnight and before UTC midnight, the fixture lies outside that requested business-day interval.

The same test was run on an independent detached checkout of unchanged Café V1 commit `9ab1eb67cea5d6cb613a582455cc53099834cacc`; it fails identically (`0 == 1`). No protected source or test was edited to hide this. The preserved Python suite therefore remains **not fully green**, and this update does not certify a new local Café release. The 27 skips require PostgreSQL/cloud/browser integration configuration that was not provided for the legacy runtime.

## Deliberate compatibility decisions and remaining acceptance work

- This is the selected **Next.js + Vercel + Atlas** application. Internet access is required. Old device heartbeat/menu-publication/command-receipt/writer-lease APIs do not provide offline operation on Vercel. Public QR now uses `/api/public/cafe/*` directly; cloud gateway interfaces return explicit HTTP 410. Their original implementation remains in the original application.
- `/api/sync/*` read/check interfaces describe a **single database** and validate invoice/payment/order/stock invariants. They do not claim cross-database recovery or repair. No synthetic Local Hub heartbeat/lease is generated.
- The legacy raw-sale adapter uses the shared invoice checkout engine for Cash non-GST sales. Arbitrary manual `tax_rate` overrides are refused; use the effective-dated GST POS workflow for taxed sales.
- GST activation requires configured identity/state/registration/sequence and owner step-up. The shared 80mm renderer shows tax breakdowns; **statutory A4 GST document acceptance and accountant review are not certified**.
- A void creates a financial reversal and explicitly records manual refund/stock compensation requirements, matching the legacy service boundary. It does **not** claim to refund a bank/UPI/Card provider or silently perform stock compensation. Those operational follow-ups must be resolved before treating a void as fully settled.
- Privileged users cannot disable their only MFA protection through the web API. A trusted terminal command can replace the authenticator; existing protection stays active until confirmation. Newly bootstrapped owners receive recovery codes. Existing owners need an intentional MFA replacement to obtain a new recovery-code set.
- Assistant output is deterministic and database-backed. The old optional external-provider wording layer is not included in this web implementation.
- PostgreSQL historical data has **not** been imported into Atlas. No live customer database was accessed, reset or reseeded. Existing Atlas accounts must not be bootstrapped again.
- Atlas backups/restore drills, provider integrations, actual Vercel runtime checks and real printer/device acceptance remain deployment/production gates. Build success is not that acceptance. The health response retains `production_parity:false`.

## Upgrade and rollback

The change adds collections/indexes and code paths; it does not drop or rewrite financial collections. Required unique/TTL indexes are ensured once per server process and cached. Existing inconsistent duplicate data will cause index creation to fail rather than be deleted or silently repaired. The original database-name isolation guard remains.

Deploy the tested `main` source with Vercel Root Directory **`apps/web`**. Keep the same private `MONGODB_URI`, `MONGODB_DB` and `AUTH_SECRET`; do not rotate `AUTH_SECRET` as part of an ordinary code deployment, and do not rerun bootstrap. The database must support multi-document transactions.

A source rollback does not undo sales, payments or stock movements. Before accepting new transactions, a deployment can revert to its previous version. **After new GST/credit/table transactions exist, the earlier partial rewrite may not understand them**: pause writes, retain a verified backup and reconcile/export affected records before enabling older code. Never drop new collections or decrement invoice sequences as a rollback strategy. The original tagged/local Café installation is separate and remains untouched.

## Publication

Publication uses an upload branch to assemble a complete Git tree through the GitHub plugin, then a single commit/ref update advances `main` with an expected-head check. This avoids exposing incomplete intermediate source snapshots to Vercel's automatic main-branch deployment. No force push or merge into a protected Café release branch is involved. Remote CI and Vercel results must be inspected separately; local results above are not remote deployment evidence.
