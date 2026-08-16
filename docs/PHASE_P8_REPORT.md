# P8 Phase Report

Status: Complete

## Verified Git State

- Source phase: Phase 8 - Cafe Billing, Payments, And Table Closing
- Base state: P7-complete `main` at `ee904913dbbfa3c5e53fdc904a3f9c7c1d64356a`
- Tested P8 head: `47ef25d75061d004f2ba8b7893279e59c3780552`
- Pull request: #12 `P8 Cafe billing, payments, stock, and table closing`
- Merge commit: `02e9ff028696f182ad5d6eeac50beda15bc047cd`

## Migration Boundary

P8 adds Local Hub revision `20260814_0015`, chained from HC3 revision `20260814_0014`.

Implemented migration changes:
- Cafe invoice `source_type` and `source_id`
- billing idempotency and normalized request hashes
- uniqueness protecting one active invoice per Cafe billing source
- nullable invoice/sale product links for intentionally unlinked prepared-food items
- table-session billed-invoice link
- billed-link indexes for Cafe orders and order items

The migration handles both fresh databases and already-upgraded P7 databases. Historical revision `0013` builds Cafe order tables from current SQLAlchemy metadata, so P8 uses inspect-and-create-if-missing logic for billed-link indexes to avoid duplicate-index DDL on fresh installations while still adding missing indexes on real upgrades.

Cloud coordination migration history remains separate and unchanged at `20260813_cloud_0001`.

## P8 Delivery

Implemented a Cafe billing adapter over the existing shared invoice, payment, customer-ledger, inventory, stock-movement, sale, sequence, and audit primitives.

### Billing sources

Supported billing sources:
- `cafe_table_session` for dine-in sessions containing one or more QR/staff orders
- `cafe_takeaway` for standalone takeaway/counter orders

One active invoice is allowed per billing source.

### Bill review and item eligibility

The backend bill quote:
- selects Cafe company and allowed branch from authenticated server scope
- uses immutable Cafe order-item price/name/SKU snapshots
- includes only eligible unbilled accepted/served items
- excludes already billed, rejected, cancelled, or otherwise ineligible items visibly
- calculates the authoritative Non-GST total server-side
- does not mutate financial data

### Atomic invoice issue

One Local Hub transaction performs the required effects together:
- locks/version-checks the billing source and source orders/items
- validates Non-GST operation mode
- validates optional Cafe customer scope
- validates Cafe-scoped payment modes and required references
- validates stable billing idempotency
- generates the branch/company invoice number
- creates one shared `Invoice` and `InvoiceItem` set
- creates the existing analytics-compatible `Sale` linkage
- reduces linked sellable-product inventory exactly once
- creates a `StockMovement` for every linked-product inventory change
- leaves unlinked prepared-food menu items free of fake stock/ingredient effects
- records payments using the existing payment helper
- writes customer-ledger debit/credit effects where applicable
- links Cafe orders/items/session to the issued invoice
- writes Cafe order status history and audit evidence
- marks the source billed
- closes/releases the order/table only when settlement policy is satisfied
- commits all effects together or rolls all effects back together

### Idempotency and concurrency

- Billing requires a stable `Idempotency-Key`.
- Same key + same normalized request + same source returns the original invoice.
- Same key with changed request returns conflict.
- A second key cannot create a second active invoice for the same source.
- Idempotent replay is checked before stale source-version rejection, so a lost HTTP acknowledgement can safely retry after the original transaction already advanced the source version.
- Source rows, Cafe orders/items, and linked inventory rows use database locking/version checks during checkout.

### Payments and closing

Supported through existing venture-scoped payment modes:
- Cash
- UPI
- Card / Bank / other configured modes
- valid split payments
- customer credit where policy permits

Reference-required modes fail closed when their reference is missing.

Anonymous bills must be fully settled. Customer-credit bills may remain billed with an outstanding balance. Later payment collection updates the existing invoice/ledger and closes/releases the Cafe source once valid settlement reaches zero balance.

### Non-GST operation

P8 remains restricted to the currently approved Non-GST Cafe mode:
- invoice type is Non-GST
- CGST, SGST, IGST, and cess remain zero
- no invoice-tax rows are fabricated
- Cafe receipt output contains no GSTIN
- internal product GST metadata is not rewritten or deleted

### Frontend

Activated Cafe Billing for Partner Admin, Manager, and Order Taker/Cashier while keeping Kitchen and Analyst outside the billing surface.

The Billing workspace provides:
- eligible table/takeaway source selection
- backend bill-quote review
- backend-authoritative totals
- customer/credit selection
- configured payment modes
- split payment rows
- payment reference fields
- stable checkout idempotency key through retry
- duplicate-click protection
- quote refresh immediately before checkout
- server-returned Non-GST receipt
- browser print action

The browser does not become the financial source of truth.

## Verification

All eleven verification workflows passed on the exact tested P8 head `47ef25d75061d004f2ba8b7893279e59c3780552`:
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

P8 verification results:
- required P8 billing suites: **11 passed**
- shared Retail financial regression suite: **37 passed**
- complete backend regression: **199 passed, 11 skipped**
- backend compile: passed
- PostgreSQL Local Hub migration rehearsal through `20260814_0015`: passed
- cloud migration independence/head verification: passed
- P8 frontend boundary checks: passed
- authenticated portal-boundary verification: passed
- TypeScript typecheck: passed
- production frontend build: passed

The inherited HC3 workflow also ran its actual cloud/local convergence suite on the same P8 head and passed after its migration check was made forward-compatible. The HC3 tests themselves were not removed or weakened.

## Release Scenarios Covered

Automated coverage includes:
- one mixed QR + staff table session producing one invoice with each eligible item once
- direct takeaway billing through the same invoice engine
- same-key retry returning the original invoice
- changed payload with reused key failing
- different key attempting to rebill the same source failing
- linked inventory decrementing exactly once with matching stock movements
- retry creating no additional stock effect
- unlinked prepared-food items creating no fake inventory movement
- forced mid-checkout failure rolling back invoice, stock, Cafe links, and other effects
- Cash + UPI split payment reconciliation
- required payment-reference enforcement
- anonymous partial settlement failing closed
- customer-credit bill remaining billed until later collection
- later collection reconciling the customer ledger and closing the table
- Kitchen, Analyst, and Retail users being denied Cafe billing actions
- zero-GST storage and receipt behavior
- table release allowing a new session only after valid close

## Exit Gate

P8 is complete when eligible Cafe QR/staff order items can be converted into exactly one shared financial result with correct payment, stock, ledger, status, and audit effects, while duplicate/retry and rollback paths remain safe.

That gate passed on the tested head above.

The next approved phase in the hybrid dependency order is HC4. P9 and later multi-venture reporting/governance work remain separate. HC4 and P9 were not started as part of P8.
