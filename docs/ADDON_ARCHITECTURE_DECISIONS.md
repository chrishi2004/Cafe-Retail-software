# Add-On Architecture Decisions

## Purpose

This document records the technical decisions for expanding the existing local-first retail inventory, analytics, forecasting, AI, and remote order management MVP into a Hitech BillSoft-style Indian retail billing system with POS, GST invoices, barcode workflows, customer/supplier ledgers, payments, returns, and GST reports.

It is intentionally created before schema or feature changes. The goal is to protect the completed MVP while giving the next implementation phases a clear path.

## Source Documents

- [PRD](../PRD.md)
- [Execution Flow Analysis](../EXECUTION_FLOW_ANALYSIS.md)
- [Original Agent Prompts](../AGENT_STEP_BY_STEP_PROMPTS.md)
- [Hitech-Competitive Add-On PRD](../PRD_HITECH_COMPETITIVE_ADDONS.md)
- [Hitech-Competitive Agent Prompts](../AGENT_STEP_BY_STEP_PROMPTS_HITECH_ADDONS.md)
- [Current Architecture](ARCHITECTURE.md)
- [Final Verification](FINAL_VERIFICATION.md)

## Current MVP Baseline

The current system is a verified local-first MVP with:

- FastAPI backend under `backend/app/`.
- SQLAlchemy models under `backend/app/models/`.
- Alembic migrations under `backend/alembic/`.
- React TypeScript frontend under `frontend/src/`.
- Local PostgreSQL as the intended production-like database.
- SQLite in-memory test setup for backend tests.
- Auth, roles, and branch scope enforced by backend dependencies.
- Inventory tracked by product and branch.
- Stock movement ledger for inventory changes.
- Sales engine that reduces stock and writes sale stock movements.
- Purchase order workflow that supports draft, approval, ordered, partial receiving, and receiving.
- Dashboard, reorder, forecast, export, AI, Power BI, remote access, and backup documentation.

## Current Code Extension Points

| Area | Current Location | Add-On Extension Direction |
| --- | --- | --- |
| App route registration | `backend/app/main.py` | Add new route groups for settings, customers, POS, invoices, payments, returns, purchase bills, GST, barcodes, report center. |
| Models | `backend/app/models/` | Add add-on models in focused files, export them from `models/__init__.py`. |
| Migrations | `backend/alembic/versions/` | Add incremental migrations per phase. Do not rewrite the initial schema. |
| Auth and branch scope | `backend/app/api/deps.py` | Reuse for all new write and read restrictions. Add finer permission helpers only if needed. |
| Audit logging | `backend/app/services/audit.py` | Reuse for invoice, payment, ledger, return, GST, and settings actions. |
| Inventory | `backend/app/models/inventory.py`, `backend/app/services/inventory.py` | Keep product/branch inventory as the canonical available stock source. Extend for batches later without breaking base inventory. |
| Stock movements | `StockMovement` and `StockMovementType` | Continue as the mandatory stock ledger. Add movement types only when a new stock-changing workflow requires them. |
| Sales | `backend/app/models/sale.py`, `backend/app/services/sales.py` | Keep current sales for analytics compatibility. New invoices become commercial documents and link to or derive sales records when issued. |
| Purchase orders | `backend/app/models/purchase_order.py`, `backend/app/services/purchase_orders.py` | Preserve PO lifecycle. Add purchase bills as accounting/receiving documents that can be created manually or from POs. |
| Dashboards | `backend/app/services/dashboard.py` | Keep existing KPIs, then evolve to use invoice/return-adjusted reporting once invoices are introduced. |
| Exports and Power BI | `backend/app/services/exports.py`, reporting view migration | Extend views and CSV exports for invoices, GST, receivables, payables, payments, and POS. |
| AI assistant | `backend/app/services/ai.py` | Add tool-backed answers for GST, invoices, credit, payments, supplier payables, and cash register. |
| Frontend navigation | `frontend/src/navigation.ts` | Add POS, Invoices, Customers, Payments, GST Reports, Purchase Bills, Report Center, and settings routes with role checks. |
| Frontend API clients | `frontend/src/api/` | Add focused clients for each route group. |
| Frontend pages | `frontend/src/pages/` | Add operational pages without turning the app into a marketing site. |
| Seed data | `backend/scripts/seed.py` | Extend with GST profile, tax rates, barcodes, customers, invoices, payments, returns, purchase bills, and ledgers. |
| Tests | `backend/tests/` | Add phase-specific tests for stock, invoice, tax, ledger, permissions, and reports. |

## Decision 1: Preserve The Local-First Architecture

The add-on expansion must preserve the core local-first rule:

- PostgreSQL remains the main business database.
- The browser communicates with the FastAPI backend.
- The database is never exposed directly to remote users.
- Remote access remains through Cloudflare Tunnel, Tailscale, ngrok, or a similar tunnel/private network.
- All data access, permissions, and business rules stay in backend APIs/services.

Reason:

The local-first architecture is a key differentiator against generic cloud billing software because it lowers recurring cloud database cost while still supporting remote owner visibility.

## Decision 2: Invoices Become First-Class Commercial Documents

The add-on will introduce first-class invoice tables instead of overloading the existing `sales` table.

Recommended model direction:

- `invoices`
- `invoice_items`
- `invoice_taxes`
- `invoice_payments`
- `invoice_status_history`

Relationship to current sales:

- Current `sales` and `sale_items` remain for MVP compatibility.
- Issued invoices should either create a linked `sales` row or expose analytics through invoice-based reporting views.
- For the safest early implementation, issued invoice checkout can create a `Sale` row as an analytics compatibility record, with a future nullable link such as `sales.invoice_id` or `invoices.sale_id`.
- Existing sales APIs should keep working during the transition.
- New POS and billing flows should use invoice APIs.

Reason:

Traditional billing software needs invoice-specific fields that do not belong naturally in simple sales rows:

- invoice number sequences
- GST/Non-GST invoice type
- place of supply
- HSN/SAC snapshots
- line-level tax rows
- payment status
- customer credit
- print template
- cancellation/return/credit note state
- e-invoice/e-way bill metadata

## Decision 3: Backend Remains The Source Of Truth

The backend must calculate and persist:

- invoice subtotal
- discounts
- taxable value
- CGST
- SGST
- IGST
- cess
- round off
- grand total
- paid amount
- balance due
- gross profit
- stock changes
- ledger entries

The frontend may show estimates for usability, but persisted values must come from backend services.

Reason:

Tax, stock, and ledger errors are high-impact business failures. Centralizing calculations keeps POS, reports, AI, and Power BI consistent.

## Decision 4: Store Tax Snapshots And Tax Rows

GST reporting must come from stored invoice and purchase tax rows, not loose recalculation from current product settings.

Required snapshot direction:

- Product HSN/SAC is copied to invoice item at time of billing.
- Product GST rate is copied to invoice item/tax rows at time of billing.
- Item taxable value and tax amounts are stored.
- CGST/SGST/IGST split is stored.
- Purchase bill tax rows are stored separately from sales invoice tax rows.
- Credit notes and debit notes store reversal tax rows.

Reason:

Product tax settings can change later. Historical invoices and GST reports must retain what was applied at transaction time.

## Decision 5: Initial GST Assumptions

The add-on uses these MVP assumptions:

- Currency is INR.
- Business operates in India.
- GSTIN is stored on business profile/branch where available.
- Branch state code determines seller state.
- Customer state code/place of supply determines buyer/place state.
- Intra-state taxable sales use CGST plus SGST.
- Inter-state taxable sales use IGST.
- HSN/SAC is stored at product level and snapshotted into invoice items.
- GST rate is stored in `tax_rates` and referenced by products.
- Non-GST invoice mode is supported for businesses/items where tax is not applied.
- GST reports are operational aids for review and export.
- A CA/GST expert must review reports before production filing.

Out of scope for early add-on phases:

- Live GST portal filing.
- Live e-invoice submission through a GSP.
- Full legal compliance guarantee.
- Multi-country tax logic.

## Decision 6: Add Business Settings Before Transactions

Phase 1 must create business and tax settings before invoice/POS work.

Required foundations:

- company/business profile
- GST registration
- state code
- invoice sequences
- tax rates
- payment modes
- fiscal periods
- print template metadata

Reason:

Invoices need business identity, GST state data, sequence generation, tax rates, payment modes, and print configuration.

## Decision 7: Ledgers Are Append-Style Records

Customer and supplier balances should be computed from ledger entries rather than overwritten balance fields.

Customer ledger entry types:

- opening_balance
- invoice
- payment
- credit_note
- refund
- adjustment

Supplier ledger entry types:

- opening_balance
- purchase_bill
- supplier_payment
- debit_note
- purchase_return
- adjustment

Rules:

- Ledger entries store debit and credit amounts.
- Adjustments require a reason and audit log.
- Deleting ledger entries should not be part of the MVP.
- Corrections should be represented through reversal or adjustment entries.

Reason:

Append-style ledgers are easier to audit and safer for financial history.

## Decision 8: Stock Movement Remains Mandatory

The existing rule continues:

Every stock change must create a `stock_movements` record.

New stock-changing workflows:

- issued invoice or POS checkout
- sale return accepted into saleable stock
- purchase bill receiving
- purchase return
- opening stock import
- damaged/non-saleable adjustment if implemented
- stock transfer if later implemented

Likely new or reused movement types:

- `sale` for invoice issue/POS checkout stock reduction
- `return` for sale returns
- `purchase_received` for purchase bill receiving or PO receiving
- `manual_adjustment` for opening stock and corrections if no more specific type exists
- future: `purchase_return`, `opening_stock`, `damaged`, `transfer`

Reason:

Inventory trust is one of the strongest parts of the current MVP. The add-on must not weaken it.

## Decision 9: Purchase Bills Extend, Not Replace, Purchase Orders

Purchase orders stay as planning/approval documents.

Purchase bills become supplier accounting/receiving documents.

Rules:

- Creating a PO does not increase stock.
- Marking a PO as ordered may increase `quantity_on_order`.
- Receiving a PO or purchase bill increases `quantity_on_hand`.
- A purchase bill can be created manually or from an approved/ordered PO.
- A purchase bill creates supplier payable entries.
- Supplier payments reduce payable entries.
- Purchase returns reduce stock and create debit note/supplier ledger adjustments.

Reason:

This keeps the existing PO workflow intact while adding the supplier bill and ledger depth expected from Indian billing software.

## Decision 10: POS Is A Dedicated Operational Flow

The POS frontend should be a separate route from the existing Sales Summary page.

Route direction:

- `POS Billing` for counter sales and checkout.
- `Invoices` for invoice search/detail/print/payment/return actions.
- Existing `Sales Summary` remains analytics/reporting.

POS UX direction:

- barcode input focused by default
- search by barcode, SKU, or name
- dense cart table
- customer selector
- payment mode selector
- keyboard-friendly interaction
- fast checkout
- clear backend errors for stock/tax/payment issues

Reason:

Counter billing and management analytics are different workflows. Splitting them keeps both fast and understandable.

## Decision 11: Permissions Remain Backend-Enforced

Default add-on permissions:

| Role | Add-On Access Direction |
| --- | --- |
| Admin | All branches, all settings, all operational and reporting features. |
| Store Manager | Assigned branch POS, invoices, inventory, customers, local payments, purchase requests/bills if allowed, branch reports. |
| Staff | Assigned branch POS billing, limited customer lookup/create if allowed, payment collection if register open. |
| Analyst | Read-only reports, dashboards, exports, Power BI, AI read-only tools. |

Important:

- Frontend route hiding is only convenience.
- Backend dependencies/services must enforce every write action.
- Branch scope must be enforced inside AI tools, exports, reports, ledgers, invoices, payments, and purchase bills.

## Decision 12: AI Can Draft, But Not Execute Writes Without Confirmation

The existing AI rule remains and expands:

- AI numerical answers must use backend tools.
- AI cannot invent invoice, tax, stock, payment, or ledger values.
- AI can draft invoice, purchase bill, or payment reminder payloads.
- AI cannot issue invoice, approve purchase, record payment, file GST, or delete data without explicit confirmation and backend permission check.
- Tax explanations must be phrased as operational summaries, not legal advice.

Reason:

This preserves the project's AI advantage while keeping business data safe.

## Decision 13: E-Invoice And E-Way Bill Are Adapter-Ready, Not Live Filing

MVP add-on will support:

- validation of required invoice fields
- structured JSON payload generation
- payload storage
- manual entry of IRN, acknowledgement number, QR data, e-way bill number, and validity
- provider interface for future GSP integration

MVP add-on will not claim:

- direct GST portal filing
- guaranteed compliance
- live provider submission without credentials and review

Reason:

This gives strong portfolio value without risky compliance claims.

## Decision 14: Report Center Extends Power BI, Not Replaces It

The app will gain a report center for operational reports.

Power BI remains for executive presentation and richer BI dashboards.

Reporting direction:

- backend report center APIs for interactive app reports
- CSV exports for CA/accountant workflows
- SQL views for Power BI
- AI tools call the same trusted report services

Reason:

This keeps operational reporting inside the app and presentation reporting in Power BI.

## Decision 15: Phase Order Must Protect Existing Workflows

Implementation order should be:

1. Documentation and decisions.
2. Business/tax/settings foundation.
3. Product catalog upgrade.
4. Customer ledger.
5. Invoice/POS backend.
6. POS frontend.
7. Invoice print.
8. Payments/cash register.
9. Returns.
10. Purchase bills/supplier ledger.
11. Accounting-lite reports.
12. GST reports.
13. E-invoice/e-way adapter.
14. Barcodes and labels.
15. Imports/exports.
16. Communication.
17. Backup status.
18. AI expansion.
19. Report center.
20. Staff performance.
21. Optional storefront.
22. Final packaging and QA.

Reason:

Invoice/POS work depends on tax settings, product tax/barcode fields, customer records, and payment modes. GST reports depend on stored invoice/purchase tax rows. AI and report center should come after reliable data exists.

## Proposed Expanded Component Map

| Component | New Responsibility |
| --- | --- |
| `business_settings` models/service/routes | Company profile, GST registration, tax rates, invoice sequences, payment modes. |
| `retail_catalog` extensions | HSN/SAC, GST rate, MRP, unit, barcode, batch/serial/expiry flags. |
| `customers` service/routes | Customer master, addresses, credit settings, outstanding balance. |
| `customer_ledger` service | Append-style receivable ledger and payments. |
| `invoices` service/routes | Commercial invoice lifecycle, issue/cancel/payment status. |
| `pos` service/routes | Barcode search, quote, checkout. |
| `invoice_prints` service/routes | A4, A5, 58mm, 80mm invoice and receipt data. |
| `payments` service/routes | Payment transactions, split payments, summaries. |
| `cash_register` service/routes | Staff shift/register open and close. |
| `sales_returns` service/routes | Sale returns, stock adjustment, tax reversal, credit notes. |
| `purchase_bills` service/routes | Supplier purchase bill and receiving workflow. |
| `supplier_ledger` service | Payables, supplier payments, purchase returns, debit notes. |
| `gst_reports` service/routes | GST sales, purchase, HSN, tax liability, validation, exports. |
| `compliance` service/routes | E-invoice/e-way payload preparation and manual result tracking. |
| `barcodes` service/routes | Internal barcode generation and label data. |
| `report_center` service/routes | Broad operational report library and CSV exports. |
| `ai` service additions | GST, ledger, invoice, payment, cash, report, and draft tools. |

## Transaction Rules

### Invoice Issue

One atomic transaction should:

1. Validate user permission and branch access.
2. Validate business profile, tax settings, branch, customer, products, inventory, and payment modes.
3. Generate invoice number.
4. Calculate invoice item totals and tax rows.
5. Create invoice, invoice items, invoice taxes, invoice payments, and status history.
6. Reduce inventory for stock items.
7. Create stock movement records.
8. Create or update analytics-compatible sales record if using the compatibility bridge.
9. Create customer ledger receivable for unpaid or credit balance.
10. Write audit log.
11. Commit.

If any step fails, rollback.

### Customer Payment

One atomic transaction should:

1. Validate user permission and branch access.
2. Validate customer and payment mode.
3. Create payment transaction.
4. Create customer ledger credit.
5. Update invoice payment status if payment references invoice.
6. Write audit log.
7. Commit.

### Sale Return

One atomic transaction should:

1. Validate original invoice and returned quantities.
2. Calculate tax reversal from stored snapshots.
3. Create sale return and credit note records.
4. Increase inventory only for saleable returned goods.
5. Create stock movement records.
6. Create customer ledger adjustment or refund record.
7. Update invoice return status.
8. Write audit log.
9. Commit.

### Purchase Bill Receiving

One atomic transaction should:

1. Validate supplier, branch, products, PO link if present, and tax fields.
2. Calculate purchase item totals and tax rows.
3. Create purchase bill and items.
4. Increase inventory for received quantities.
5. Reduce `quantity_on_order` if linked to an ordered PO.
6. Create stock movement records.
7. Create supplier payable ledger entry.
8. Write audit log.
9. Commit.

### Purchase Return

One atomic transaction should:

1. Validate purchase bill and return quantities.
2. Decrease inventory.
3. Create stock movement records.
4. Create purchase return/debit note.
5. Adjust supplier ledger.
6. Write audit log.
7. Commit.

## Migration Strategy

- Add new migrations incrementally by phase.
- Do not modify historical migration files.
- Prefer nullable columns when adding optional product/customer fields to existing tables, then seed values.
- Use constraints for unique SKU/barcode, invoice numbers, ledger references, and controlled statuses.
- Use indexes on report-heavy fields:
  - invoice date
  - branch id
  - customer id
  - supplier id
  - product id
  - tax period
  - payment mode
  - ledger reference
- Keep SQLite test compatibility where practical, because current tests use in-memory SQLite.

## Frontend Strategy

- Keep the current operational dashboard style.
- Do not add marketing hero pages.
- Add pages in focused vertical slices.
- Use role-aware navigation, but rely on backend for security.
- New route groups should get focused API clients under `frontend/src/api/`.
- Shared tables, filters, loading, empty, and error states should reuse existing UI components.
- POS should be denser and faster than dashboard pages.

## Testing Strategy

Every phase should run:

- targeted backend tests for new business rules
- relevant regression tests for stock, sales, purchase orders, auth, and dashboard behavior
- frontend typecheck/build when frontend changes
- manual workflow test when UI changes

High-risk tests required before final completion:

- GST tax split calculation
- invoice issue reduces stock
- invoice issue creates stock movements
- credit invoice creates customer receivable
- customer payment reduces receivable
- sale return cannot exceed sold quantity
- sale return stock/tax/ledger effects
- purchase bill receiving increases stock
- supplier payment reduces payable
- GST reports come from stored tax rows
- AI uses data tools and does not invent numbers
- role and branch scope are enforced

## Compliance Disclaimer

GST, e-invoice, and e-way bill features in this project are for portfolio, demo, operational planning, and educational use. They are not legal, tax, accounting, or compliance advice.

Before production use:

- GST setup and reports must be reviewed by a qualified CA/GST expert.
- Portal filing formats must be checked against current GST rules.
- Live e-invoice or e-way bill integration must use an approved provider or valid API access.
- Business owners are responsible for legal compliance.

## Known Phase 0 Constraints

- No schema changes are made in Phase 0.
- No code behavior changes are made in Phase 0.
- The add-on plan intentionally creates a large Version 2 roadmap, but implementation should remain phase-by-phase.
- The CORS/local dev host behavior should be fixed separately if the app must support both `localhost` and `127.0.0.1` during development.

## Decision Summary

The add-on expansion should build a serious Indian retail billing product by adding first-class invoices, GST tax rows, POS checkout, customer/supplier ledgers, payments, returns, purchase bills, barcode workflows, report center, and advanced AI tools on top of the existing local-first MVP.

The most important architectural rule is simple:

Do not replace the verified inventory, sales analytics, purchase order, AI, and reporting foundation. Extend it carefully through new transactional services, explicit links, stored tax snapshots, append-style ledgers, and tests around every stock or money movement.

