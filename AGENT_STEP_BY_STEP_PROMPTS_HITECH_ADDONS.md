# Agent Step-By-Step Build Prompts: Hitech-Competitive Add-Ons

## Project

AI-Powered Hybrid Retail Billing, POS, GST, Inventory, Analytics, and Remote Order Management System

## Purpose

This document gives copy-paste prompts for expanding the existing project into a stronger Indian retail billing, POS, GST, inventory, accounting-lite, analytics, AI, and remote management product.

Use this prompt pack after the original MVP is complete.

Required source documents:

- `PRD.md`
- `EXECUTION_FLOW_ANALYSIS.md`
- `AGENT_STEP_BY_STEP_PROMPTS.md`
- `PRD_HITECH_COMPETITIVE_ADDONS.md`
- Current codebase

Treat the original PRD as the base product contract.
Treat `PRD_HITECH_COMPETITIVE_ADDONS.md` as the Version 2 add-on product contract.
Treat this file as the execution guide for the add-on phases.

## How To Use These Prompts

1. Give the agent the Global Add-On Build Context Prompt first.
2. Give only one phase prompt at a time.
3. Do not move to the next phase until the current phase passes its acceptance checks.
4. Each phase must end with a short report:
   - files changed
   - features implemented
   - commands run
   - verification results
   - known gaps
   - next recommended phase
5. If a phase touches stock, invoice, tax, payment, ledger, or permissions, add backend tests.
6. If a phase touches frontend pages, run typecheck/build and manually test the page.
7. Preserve the existing MVP features unless a change is explicitly required.

## Global Add-On Build Context Prompt

Use this before starting the add-on build and repeat it when starting a new agent session.

```text
You are expanding an existing full-stack portfolio project named "AI-Powered Hybrid Retail Inventory, Sales Analytics, and Remote Order Management System" into "AI-Powered Hybrid Retail Billing, POS, GST, Inventory, Analytics, and Remote Order Management System".

Before making changes, read these project documents:
- PRD.md
- EXECUTION_FLOW_ANALYSIS.md
- AGENT_STEP_BY_STEP_PROMPTS.md
- PRD_HITECH_COMPETITIVE_ADDONS.md
- AGENT_STEP_BY_STEP_PROMPTS_HITECH_ADDONS.md

Treat PRD.md as the foundation contract.
Treat PRD_HITECH_COMPETITIVE_ADDONS.md as the Version 2 add-on contract.
Treat this prompt file as the step-by-step execution guide.

Existing architecture to preserve:
- Hybrid local-first system.
- Main PostgreSQL database must remain local by default.
- Do not design the default system around a paid cloud database.
- Remote admin access must go through the authenticated web app/API.
- Do not expose the database directly.
- All database access must go through backend services/APIs.
- Backend must enforce role and branch permissions.

Existing stack:
- Backend: FastAPI, Python, SQLAlchemy
- Database: local PostgreSQL
- Migrations: Alembic
- Frontend: React, TypeScript, Vite
- Charts: Recharts
- AI assistant: backend tool layer first, OpenAI optional
- BI: Power BI Desktop through local SQL views or CSV exports

Expansion goal:
Add Hitech BillSoft-style practical retail software capabilities while keeping the project's existing strengths in analytics, AI, forecasting, Power BI, local-first architecture, and remote admin access.

Critical add-on features:
- Fast POS billing
- GST and Non-GST invoices
- HSN/SAC and GST rate support
- Barcode product lookup and label generation
- Invoice print/PDF/receipt templates
- Customer management and customer ledger
- Credit sales and payment collection
- Purchase bills and supplier ledger
- Sales returns, refunds, and credit notes
- GST reports and CA-friendly exports
- Payment modes, split payments, and cash register
- Advanced AI tools for invoices, GST, payments, ledgers, and stock
- Expanded report center and Power BI views

Important business rules:
- Backend is the source of truth for invoice, tax, payment, stock, and ledger totals.
- Issued invoices reduce inventory.
- Draft invoices do not reduce stock unless reservation is explicitly implemented.
- Every stock change must create a stock movement record.
- Credit sales must create customer receivable ledger entries.
- Customer payments must reduce receivables.
- Purchase bills must create supplier payable ledger entries.
- Supplier payments must reduce payables.
- Purchase order creation must not increase available inventory.
- Purchase receiving or purchase bill receiving increases inventory.
- Sale returns increase inventory only when goods are accepted back as saleable stock.
- Tax rows must be stored and used for reports.
- AI must not invent business numbers.
- AI must use backend tools for numerical answers.
- AI must ask confirmation before write actions.

Compliance caution:
GST, e-invoice, and e-way bill features are operational aids for a portfolio/demo system. Production use must be reviewed by a CA/GST expert and any live portal integration must use a valid provider or approved API path.

Implementation behavior:
- Work in small complete vertical slices.
- Preserve existing code and docs unless change is necessary.
- Keep services modular and transactional.
- Add tests where practical, especially for stock, tax, invoice, ledger, and permission rules.
- Do not hardcode dashboard or report KPI values in the frontend.
- Update seed data so each new phase has meaningful demo data.
- Update documentation as behavior changes.
- At the end of each phase, summarize changed files, completed requirements, commands run, verification results, known gaps, and next recommended phase.
```

## Common Testing Commands

Use these as appropriate for each phase.

Backend:

```powershell
cd "C:\Users\Admin\Documents\New project 2\backend"
.\.venv\Scripts\python.exe -m pytest -q
```

Targeted backend tests:

```powershell
cd "C:\Users\Admin\Documents\New project 2\backend"
.\.venv\Scripts\python.exe -m pytest tests/test_<module>.py -q
```

Migrations:

```powershell
cd "C:\Users\Admin\Documents\New project 2\backend"
alembic upgrade head
```

Seed data:

```powershell
cd "C:\Users\Admin\Documents\New project 2\backend"
.\.venv\Scripts\python.exe -m scripts.seed --reset
```

Frontend:

```powershell
cd "C:\Users\Admin\Documents\New project 2\frontend"
npm run typecheck
npm run build
```

Manual run:

```powershell
cd "C:\Users\Admin\Documents\New project 2\backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

```powershell
cd "C:\Users\Admin\Documents\New project 2\frontend"
npm run dev
```

Open:

```text
http://localhost:5173
```

Use `localhost`, not `127.0.0.1`, unless CORS is configured for both.

## Standard Phase Report Format

Every phase must end with this report:

```text
Phase completed:

Files changed:
- ...

Features implemented:
- ...

Commands run:
- ...

Verification results:
- ...

Known gaps or follow-ups:
- ...

Next recommended phase:
- ...
```

## Phase 0 Prompt: Competitive Baseline And Compliance Planning

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, AGENT_STEP_BY_STEP_PROMPTS.md, PRD_HITECH_COMPETITIVE_ADDONS.md, and the current codebase.

Build Add-On Phase 0: Competitive baseline and compliance planning.

Goal:
Create the technical decision foundation for adding POS, GST invoicing, barcode, customer ledger, supplier ledger, and billing features without breaking the existing MVP.

Tasks:
1. Inspect current backend models, services, routes, schemas, tests, migrations, seed data, and frontend pages.
2. Identify where current sales, sale_items, inventory, stock_movements, purchase_orders, suppliers, users, branches, exports, dashboards, and AI services will be extended.
3. Create docs/ADDON_ARCHITECTURE_DECISIONS.md.
4. Decide and document how invoices relate to existing sales:
   - Recommended: add invoices as first-class commercial documents and keep sales analytics compatible by deriving or linking sales records from issued invoices.
5. Define initial GST assumptions:
   - INR currency.
   - CGST/SGST for intra-state sales.
   - IGST for inter-state sales.
   - Product-level HSN/SAC and GST rate.
   - Stored tax rows are the source for reports.
6. Define transaction rules for invoice issue, stock movement, payments, customer ledger, purchase bill, supplier ledger, and returns.
7. Define compliance disclaimer for GST, e-invoice, and e-way bill.
8. Create docs/HITECH_COMPETITIVE_EXPANSION_PLAN.md with the final phase order and dependencies.
9. Do not implement business features yet.

Acceptance checks:
- Architecture decision document exists.
- Expansion plan exists.
- Existing MVP tests still pass or known failures are documented.
- No schema or feature behavior is changed in this phase unless documentation-only.

Testing after this phase:
1. Run backend tests if environment is available:
   cd backend
   .\.venv\Scripts\python.exe -m pytest -q
2. Run frontend checks if environment is available:
   cd frontend
   npm run typecheck
   npm run build
3. Manually check that README and docs still make sense with the add-on plan.

Report back using the standard phase report format.
```

## Phase 1 Prompt: Business Profile, Tax, And Invoice Settings Foundation

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, docs/ADDON_ARCHITECTURE_DECISIONS.md if present, and the current backend/frontend code.

Build Add-On Phase 1: Business profile, tax, and invoice settings foundation.

Goal:
Add the configuration foundation required for GST invoices, invoice numbering, payment modes, fiscal periods, and print templates.

Backend tasks:
1. Add SQLAlchemy models and Alembic migration for:
   - companies
   - business_profiles
   - gst_registrations
   - tax_rates
   - invoice_sequences
   - payment_modes
   - print_templates
   - fiscal_periods
2. Link business profile and GST registration to company/branch where appropriate.
3. Add controlled values for tax mode, invoice sequence reset rule, payment mode type, and template type.
4. Add unique constraints where needed:
   - company code/name if appropriate
   - GSTIN where present
   - invoice sequence per branch/type/fiscal year
   - payment mode name per company
5. Add service to generate the next invoice number safely.
6. Add APIs:
   - GET /business-profile
   - PUT /business-profile
   - GET /tax-rates
   - POST /tax-rates
   - PUT /tax-rates/{id}
   - GET /payment-modes
   - POST /payment-modes
   - PUT /payment-modes/{id}
   - GET /invoice-sequences
   - POST /invoice-sequences
   - PUT /invoice-sequences/{id}
7. Enforce Admin-only writes.
8. Add seed data:
   - demo company
   - demo branch GST/state data
   - common GST rates: 0, 5, 12, 18, 28
   - Cash, UPI, Card, Bank Transfer, Credit payment modes
   - default invoice sequence
9. Add backend tests for settings CRUD, permissions, tax rate validation, and invoice number generation.

Frontend tasks:
1. Add Settings sections/pages for:
   - Business Profile
   - GST/Tax Settings
   - Payment Modes
   - Invoice Sequences
   - Print Templates placeholder
2. Show loading, empty, error, and success states.
3. Make settings visible/editable for Admin only.

Documentation tasks:
1. Update setup/demo docs with default business profile.
2. Add GST compliance disclaimer.

Acceptance checks:
- Admin can configure business profile.
- Tax rates are stored in database.
- Payment modes are stored in database.
- Backend can generate next invoice number.
- Non-admin users cannot edit settings.
- Existing MVP features still work.

Testing after this phase:
1. Run migration:
   cd backend
   alembic upgrade head
2. Run seed:
   .\.venv\Scripts\python.exe -m scripts.seed --reset
3. Run targeted tests:
   .\.venv\Scripts\python.exe -m pytest tests/test_business_settings.py -q
4. Run existing critical tests:
   .\.venv\Scripts\python.exe -m pytest tests/test_auth.py tests/test_inventory.py tests/test_sales.py -q
5. Run frontend:
   cd frontend
   npm run typecheck
   npm run build
6. Manual UI test:
   - Login as Admin.
   - Open Settings.
   - Edit business profile.
   - Add/edit tax rate.
   - Login as Staff and confirm settings writes are blocked.

Report back using the standard phase report format.
```

## Phase 2 Prompt: Product Catalog Upgrade For Indian Retail

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, current product models/APIs/UI, and Phase 1 settings.

Build Add-On Phase 2: Product catalog upgrade for Indian retail.

Goal:
Extend products for GST, HSN/SAC, barcode, MRP, unit, brand, manufacturer, batch tracking, serial tracking, and expiry tracking.

Backend tasks:
1. Extend products with:
   - hsn_sac_code
   - gst_rate_id
   - cess_rate_percent
   - primary_barcode
   - unit_of_measure
   - mrp
   - brand
   - manufacturer
   - item_type: goods/service
   - batch_tracking_enabled
   - serial_tracking_enabled
   - expiry_tracking_enabled
2. Add models/migrations for:
   - product_barcodes
   - product_units
   - product_price_history
   - inventory_batches
   - serial_numbers
3. Add constraints:
   - SKU remains unique.
   - Barcode is unique when present.
   - Alternate barcode is unique.
   - MRP and prices cannot be negative.
   - GST rate must reference tax_rates.
4. Update product APIs to include new fields.
5. Add GET /products/search that can search by name, SKU, primary barcode, and alternate barcode.
6. Add barcode helper service:
   - normalize barcode
   - detect duplicates
   - optional internal barcode generation
7. Update seed data with realistic HSN/SAC, GST rates, MRP, unit, brand, and barcodes.
8. Add backend tests for product creation/update/search/barcode uniqueness.

Frontend tasks:
1. Update product list to show SKU, barcode, HSN, GST rate, MRP, selling price, stock status.
2. Update product create/edit form with:
   - HSN/SAC
   - GST rate
   - MRP
   - barcode
   - unit
   - brand
   - manufacturer
   - batch/serial/expiry toggles
3. Add search by barcode/SKU/name.
4. Keep inactive products hidden by default in operational selection.

Acceptance checks:
- Admin can create product with HSN, GST rate, MRP, and barcode.
- Duplicate barcode is rejected.
- Product search works by barcode, SKU, and name.
- Product UI handles new fields cleanly.
- Existing inventory and sales pages still work.

Testing after this phase:
1. Run migration and seed:
   cd backend
   alembic upgrade head
   .\.venv\Scripts\python.exe -m scripts.seed --reset
2. Run targeted tests:
   .\.venv\Scripts\python.exe -m pytest tests/test_products_retail_catalog.py tests/test_master_data.py -q
3. Run inventory/sales regression:
   .\.venv\Scripts\python.exe -m pytest tests/test_inventory.py tests/test_sales.py -q
4. Run frontend checks:
   cd frontend
   npm run typecheck
   npm run build
5. Manual UI test:
   - Login as Admin.
   - Create product with GST and barcode.
   - Try duplicate barcode.
   - Search product by barcode.
   - Confirm inventory page still loads.

Report back using the standard phase report format.
```

## Phase 3 Prompt: Customer Management And Customer Ledger

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, current auth/branch permissions, and current sales flow.

Build Add-On Phase 3: Customer management and customer ledger.

Goal:
Add customer accounts, credit limits, customer addresses, payment receipts, and append-style customer ledger entries.

Backend tasks:
1. Add models/migrations for:
   - customers
   - customer_addresses
   - customer_ledger_entries
   - customer_payments
   - customer_credit_limits if separated from customers
2. Customer fields:
   - name
   - phone
   - email
   - GSTIN
   - billing address
   - shipping address
   - state
   - credit limit
   - opening balance
   - active status
   - branch/company scope if needed
3. Ledger entry fields:
   - customer_id
   - branch_id
   - entry_type: opening_balance, invoice, payment, credit_note, adjustment
   - debit
   - credit
   - reference_type
   - reference_id
   - reason/notes
   - created_by
4. Add APIs:
   - GET /customers
   - POST /customers
   - GET /customers/{id}
   - PUT /customers/{id}
   - PATCH /customers/{id}/deactivate
   - GET /customers/{id}/ledger
   - POST /customers/{id}/payments
   - GET /customer-ledger/outstanding
5. Add customer outstanding calculation service.
6. Add credit limit validation helper.
7. Add audit logs for customer creation/update/payment.
8. Enforce permissions:
   - Admin can manage all customers.
   - Store Manager can manage assigned branch customers if allowed.
   - Staff can select customers and record allowed payments if permitted.
   - Analyst is read-only.
9. Add seed data with realistic retail customers, GST and non-GST customers, opening balances, and payment history.
10. Add backend tests for customer CRUD, ledger balance, payments, credit limit, and permissions.

Frontend tasks:
1. Add Customers page with search/filter.
2. Add customer create/edit form.
3. Add customer detail page or drawer with ledger.
4. Add payment receipt form.
5. Add customer outstanding list.
6. Add role-aware navigation.

Acceptance checks:
- Admin can create/edit customers.
- Customer ledger shows opening balance and payments.
- Outstanding balance is calculated correctly.
- Credit limit helper can block/warn future invoice flow.
- Non-admin writes are restricted correctly.

Testing after this phase:
1. Run migration and seed.
2. Run targeted tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_customers.py tests/test_customer_ledger.py -q
3. Run auth/permissions regression:
   .\.venv\Scripts\python.exe -m pytest tests/test_auth.py tests/test_master_data.py -q
4. Run frontend checks:
   cd frontend
   npm run typecheck
   npm run build
5. Manual UI test:
   - Login as Admin.
   - Create customer.
   - Add opening balance or payment.
   - Verify ledger balance.
   - Login as Analyst and confirm read-only behavior.

Report back using the standard phase report format.
```

## Phase 4 Prompt: Invoice And POS Billing Backend

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, Phase 0 decisions, product catalog, customer ledger, inventory, sales, and stock movement code.

Build Add-On Phase 4: Invoice and POS billing backend.

Goal:
Create a production-style invoice engine and POS checkout API that supports GST/Non-GST billing, stock reduction, payments, customer ledger entries, and compatibility with existing sales analytics.

Backend tasks:
1. Add models/migrations for:
   - invoices
   - invoice_items
   - invoice_taxes
   - invoice_payments
   - invoice_status_history
2. Invoice statuses:
   - draft
   - issued
   - paid
   - partial_paid
   - credit
   - cancelled
   - returned
3. Add invoice fields:
   - invoice_number
   - branch_id
   - customer_id optional
   - invoice_type: gst/non_gst
   - place_of_supply_state
   - invoice_date
   - subtotal
   - discount_total
   - taxable_total
   - cgst_total
   - sgst_total
   - igst_total
   - cess_total
   - round_off
   - grand_total
   - paid_amount
   - balance_due
   - payment_status
   - created_by
4. Add invoice item fields:
   - product_id
   - hsn_sac_code snapshot
   - quantity
   - unit_price
   - mrp snapshot
   - discount
   - taxable_value
   - gst_rate snapshot
   - tax totals
   - line_total
   - gross_profit
5. Add APIs:
   - GET /invoices
   - POST /invoices
   - GET /invoices/{id}
   - POST /invoices/{id}/issue
   - POST /invoices/{id}/cancel
   - POST /invoices/{id}/payments
   - GET /pos/products/search
   - POST /pos/checkout
6. Build tax calculation service:
   - chooses CGST/SGST or IGST from branch and place of supply
   - supports GST and Non-GST mode
   - stores item-level tax rows
7. Build invoice issue transaction:
   - validate branch, customer, products, stock, price, tax
   - generate invoice number
   - create invoice and items
   - create tax rows
   - reduce inventory
   - create stock movement records
   - create payment rows
   - create customer ledger receivable for credit/partial/unpaid amount
   - create sale record or analytics-compatible link according to Phase 0 decision
   - audit the action
8. Ensure invoice issue is atomic.
9. Add tests for:
   - GST tax calculation
   - invoice number uniqueness
   - stock reduction
   - stock movement creation
   - payment rows
   - customer ledger entry
   - insufficient stock
   - permission restrictions
   - sales dashboard compatibility

Business rules:
- Backend calculates all totals.
- Draft invoice does not reduce stock.
- Issued invoice reduces stock.
- Every stock change creates stock movement.
- Tax rows are stored.
- Credit/partial invoice creates receivable.
- Staff can issue invoices for allowed branch.
- Analyst cannot issue invoices.

Acceptance checks:
- Staff can create and issue an invoice through API.
- POS checkout API works.
- GST tax breakup is correct for intra-state and inter-state cases.
- Inventory decreases.
- Stock movements are created.
- Payments are stored.
- Customer ledger updates for credit/partial payment.
- Existing dashboard sales KPIs still work.

Testing after this phase:
1. Run migration and seed.
2. Run targeted tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_invoices.py tests/test_pos_checkout.py tests/test_invoice_tax.py -q
3. Run stock and sales regression:
   .\.venv\Scripts\python.exe -m pytest tests/test_inventory.py tests/test_sales.py tests/test_dashboard.py -q
4. Manual API tests:
   - Login as Staff.
   - Search product using /pos/products/search.
   - Create cash invoice with /pos/checkout.
   - Create credit invoice for customer.
   - Confirm inventory and stock movement.
   - Confirm customer ledger balance.

Report back using the standard phase report format.
```

## Phase 5 Prompt: Fast POS Frontend

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, current frontend app shell, product APIs, customer APIs, payment modes, and POS checkout backend.

Build Add-On Phase 5: Fast POS frontend.

Goal:
Build a counter-friendly POS screen connected to the backend POS checkout APIs.

Frontend tasks:
1. Add POS Billing page to authenticated app shell.
2. Make navigation role-aware:
   - Admin, Store Manager, and Staff can access POS.
   - Analyst cannot issue sales.
3. Build a barcode/search input focused by default.
4. Product lookup must support barcode, SKU, and product name.
5. Build cart with:
   - product name
   - SKU/barcode
   - HSN
   - GST rate
   - MRP
   - unit price
   - quantity
   - discount
   - taxable value
   - tax
   - line total
6. Add customer selector and quick customer create if practical.
7. Add invoice type selector:
   - GST
   - Non-GST
8. Add place of supply selector if needed.
9. Add payment mode selector and simple split payment support if backend supports it.
10. Add hold/draft invoice if backend supports draft.
11. Add one-click checkout for cash sale.
12. Show backend-calculated totals after quote/checkout where possible.
13. After checkout, show invoice success panel with print/download action placeholder if Phase 6 is not built yet.
14. Use existing UI style. Make it operational and dense, not a landing page.
15. Add loading, empty, error, and insufficient stock states.
16. Do not hardcode tax/KPI totals in frontend.

Backend tasks if needed:
1. Add lightweight quote endpoint if necessary:
   - POST /pos/quote
2. Ensure POS APIs return frontend-friendly errors.

Acceptance checks:
- Staff can open POS page.
- Barcode/scanner-like typing adds product.
- Staff can add multiple products.
- Totals display clearly.
- Checkout creates invoice through backend.
- Inventory decreases after checkout.
- Invalid/unknown barcode shows clear error.
- Analyst cannot access POS page.

Testing after this phase:
1. Run frontend checks:
   cd frontend
   npm run typecheck
   npm run build
2. Run backend POS/invoice tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_pos_checkout.py tests/test_invoices.py -q
3. Manual browser test:
   - Start backend and frontend.
   - Login as Staff.
   - Open POS Billing.
   - Search product by barcode.
   - Add 2 or more products.
   - Complete cash/UPI checkout.
   - Verify invoice success.
   - Open Inventory and verify stock reduced.
   - Login as Analyst and confirm POS is blocked.

Report back using the standard phase report format.
```

## Phase 6 Prompt: Invoice Print, PDF, And Receipt Templates

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, invoice backend, business profile, tax rows, and current frontend styling.

Build Add-On Phase 6: Invoice print, PDF, and receipt templates.

Goal:
Allow issued invoices to be previewed, printed, and downloaded in professional Indian retail formats.

Backend tasks:
1. Add invoice print service that loads:
   - business profile
   - GST registration
   - branch address
   - customer details
   - invoice items
   - tax rows
   - payment rows
2. Add APIs:
   - GET /invoice-prints/{invoice_id}
   - GET /invoice-prints/{invoice_id}/html
   - GET /invoice-prints/{invoice_id}/pdf if practical
3. Support templates:
   - A4 GST invoice
   - A5 invoice
   - 58mm POS receipt
   - 80mm POS receipt
   - Non-GST invoice
4. Add template fields:
   - business logo placeholder
   - legal name and trade name
   - GSTIN
   - address
   - invoice number/date
   - customer details
   - HSN
   - taxable value
   - CGST/SGST/IGST
   - grand total
   - payment mode
   - terms and conditions
   - QR placeholder
5. Add tests for invoice print data and template selection.

Frontend tasks:
1. Add invoice detail print/download buttons.
2. Add print preview page/modal.
3. Add template selector where appropriate.
4. Add print CSS for A4 and POS receipt sizes.
5. On POS checkout success, offer print receipt.

Acceptance checks:
- Issued invoice can be previewed.
- Invoice can be printed from browser.
- PDF/download works if implemented.
- A4 and POS receipt templates are readable.
- Tax breakup appears correctly.
- Non-GST invoice hides GST-specific fields appropriately.

Testing after this phase:
1. Run backend tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_invoice_prints.py tests/test_invoices.py -q
2. Run frontend checks:
   cd frontend
   npm run typecheck
   npm run build
3. Manual browser test:
   - Create invoice from POS.
   - Open invoice preview.
   - Switch A4 and POS receipt templates.
   - Use browser print preview.
   - Confirm GST breakup and business details are visible.

Report back using the standard phase report format.
```

## Phase 7 Prompt: Payments, Credit, And Cash Register

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, invoice payment rows, customer ledger, and current auth/branch scope code.

Build Add-On Phase 7: Payments, credit, and cash register.

Goal:
Track payment modes, split payments, customer credit, and daily cash register sessions.

Backend tasks:
1. Add models/migrations for:
   - cash_register_sessions
   - payment_transactions
   - payment_reconciliations
   - drawer_movements
2. Payment modes must include:
   - cash
   - UPI
   - card
   - bank transfer
   - wallet
   - cheque
   - credit
3. Add APIs:
   - POST /cash-register/open
   - POST /cash-register/{id}/close
   - GET /cash-register/current
   - GET /cash-register/sessions
   - POST /payments
   - GET /payments
   - GET /payments/summary
4. Enhance invoice payment behavior:
   - full paid
   - partial paid
   - unpaid
   - credit
   - split payment
5. Link payments to invoice/customer/cash register/user/branch.
6. Add daily closing service:
   - opening cash
   - cash sales
   - cash refunds
   - cash in/out
   - expected cash
   - counted cash
   - difference
7. Add customer outstanding and aging report support.
8. Add audit logs for register open/close, payment collection, and drawer movement.
9. Add tests for split payment, credit invoice, customer outstanding, register close, and permissions.

Frontend tasks:
1. Add Cash Register page.
2. Add open/close register UI for Staff/Manager.
3. Add payment collection UI.
4. Add payment summary by mode.
5. Upgrade POS payment section for split payments.
6. Add customer outstanding/aging view.

Acceptance checks:
- Staff can open and close cash register.
- Invoice can be full paid, partial paid, or credit.
- Split payment is stored correctly.
- Customer outstanding is accurate.
- Admin can view payment summary by mode.
- Analyst is read-only.

Testing after this phase:
1. Run migration and seed.
2. Run targeted tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_payments.py tests/test_cash_register.py tests/test_customer_ledger.py -q
3. Run invoice regression:
   .\.venv\Scripts\python.exe -m pytest tests/test_invoices.py tests/test_pos_checkout.py -q
4. Run frontend checks.
5. Manual browser test:
   - Login as Staff.
   - Open register.
   - Create invoice with cash + UPI split payment.
   - Create credit invoice.
   - Close register.
   - Login as Admin and check payment summary.

Report back using the standard phase report format.
```

## Phase 8 Prompt: Sales Returns, Refunds, And Credit Notes

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, invoice service, stock movement service, customer ledger, tax rows, and payment service.

Build Add-On Phase 8: Sales returns, refunds, and credit notes.

Goal:
Handle post-sale returns correctly with stock, tax, refund, and customer ledger effects.

Backend tasks:
1. Add models/migrations for:
   - sales_returns
   - sales_return_items
   - credit_notes
   - credit_note_items if needed
   - refund_transactions if separate from payments
2. Add APIs:
   - POST /sales-returns
   - GET /sales-returns
   - GET /sales-returns/{id}
   - POST /credit-notes
   - GET /credit-notes
   - GET /credit-notes/{id}
3. Return service must:
   - load original invoice
   - validate return quantity does not exceed sold quantity minus prior returned quantity
   - calculate tax reversal from original tax snapshots
   - increase inventory when returned goods are saleable
   - optionally route damaged goods to non-saleable adjustment if supported
   - create stock movements
   - create customer ledger credit
   - create refund/payment adjustment where applicable
   - update invoice return status
   - audit action
4. Add credit note print data using Phase 6 print system.
5. Update dashboards/reports to account for returns where needed.
6. Add tests for return quantity validation, stock increase, tax reversal, ledger credit, refund, and permissions.

Frontend tasks:
1. Add Sales Returns page.
2. Add return action from invoice detail.
3. Add return form with original invoice item selection.
4. Add saleable/damaged option if supported.
5. Add credit note preview/print.
6. Update invoice detail to show returned quantities.

Business rules:
- Return quantity cannot exceed sold quantity.
- Stock increases only for saleable accepted returns.
- Tax reversal must be based on stored invoice tax data.
- Return must create stock movement and audit log.

Acceptance checks:
- User can create return from issued invoice.
- Valid return increases inventory.
- Over-return is rejected.
- Credit note is created.
- Customer ledger is adjusted.
- Dashboards do not count returned revenue incorrectly.

Testing after this phase:
1. Run targeted tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_sales_returns.py tests/test_credit_notes.py -q
2. Run invoice, inventory, dashboard regression:
   .\.venv\Scripts\python.exe -m pytest tests/test_invoices.py tests/test_inventory.py tests/test_dashboard.py -q
3. Run frontend checks.
4. Manual browser test:
   - Create POS invoice.
   - Return one item.
   - Confirm stock increased.
   - Confirm credit note exists.
   - Try returning more than sold and confirm rejection.

Report back using the standard phase report format.
```

## Phase 9 Prompt: Purchase Bills, Purchase Returns, And Supplier Ledger

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, existing purchase order workflow, suppliers, inventory, stock movements, and tax settings.

Build Add-On Phase 9: Purchase bills, purchase returns, and supplier ledger.

Goal:
Upgrade the purchase workflow into full purchase bill and supplier payable tracking while keeping existing PO rules.

Backend tasks:
1. Add models/migrations for:
   - purchase_bills
   - purchase_bill_items
   - purchase_bill_taxes
   - supplier_ledger_entries
   - supplier_payments
   - purchase_returns
   - purchase_return_items
   - debit_notes
2. Add APIs:
   - GET /purchase-bills
   - POST /purchase-bills
   - GET /purchase-bills/{id}
   - POST /purchase-bills/from-purchase-order/{po_id}
   - POST /purchase-bills/{id}/receive
   - GET /supplier-ledger/{supplier_id}
   - POST /suppliers/{supplier_id}/payments
   - POST /purchase-returns
   - GET /purchase-returns
3. Purchase bill service must:
   - validate supplier, branch, products, GST/HSN, batch/MRP/expiry where applicable
   - calculate purchase tax rows
   - increase stock only when goods are received
   - create stock movements
   - create supplier payable ledger entry
   - reduce quantity_on_order if linked to PO
   - audit action
4. Supplier payment service must reduce payable.
5. Purchase return service must decrease stock and adjust supplier ledger.
6. Existing PO lifecycle must continue to work.
7. Add tests for purchase bill creation, PO to bill, stock increase, supplier payable, supplier payment, purchase return, and invalid transitions.

Frontend tasks:
1. Add Purchase Bills page.
2. Add purchase bill create/edit form.
3. Add convert PO to purchase bill action.
4. Add supplier ledger page.
5. Add supplier payment form.
6. Add purchase return/debit note page or action.

Business rules:
- PO creation does not increase stock.
- Purchase bill receiving increases stock.
- Purchase return decreases stock.
- Supplier payable is created from purchase bill.
- Supplier payment reduces payable.
- Every stock change creates stock movement.

Acceptance checks:
- Admin can create purchase bill manually.
- Admin can convert PO to purchase bill.
- Receiving purchase bill increases inventory.
- Supplier ledger shows bill, payment, return, and adjustment entries.
- Purchase return decreases stock.
- Existing PO receiving remains valid.

Testing after this phase:
1. Run targeted tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_purchase_bills.py tests/test_supplier_ledger.py tests/test_purchase_returns.py -q
2. Run PO/inventory regression:
   .\.venv\Scripts\python.exe -m pytest tests/test_purchase_orders.py tests/test_inventory.py tests/test_reorder.py -q
3. Run frontend checks.
4. Manual browser test:
   - Create PO.
   - Convert to purchase bill.
   - Receive bill.
   - Confirm stock increase.
   - Add supplier payment.
   - Check supplier ledger.

Report back using the standard phase report format.
```

## Phase 10 Prompt: Expense Tracking And Basic Accounting Reports

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, payment, customer ledger, supplier ledger, dashboard, and export services.

Build Add-On Phase 10: Expense tracking and basic accounting reports.

Goal:
Add practical expense tracking and accounting-lite reports without trying to replace full accounting software.

Backend tasks:
1. Add models/migrations for:
   - expense_categories
   - expenses
   - account_heads if needed
   - ledger_entries if a simple unified ledger is practical
2. Add APIs:
   - GET /expense-categories
   - POST /expense-categories
   - PUT /expense-categories/{id}
   - GET /expenses
   - POST /expenses
   - GET /expenses/{id}
   - PUT /expenses/{id}
   - GET /reports/accounting/daily-profit
   - GET /reports/accounting/cashbook
   - GET /reports/accounting/receivables
   - GET /reports/accounting/payables
3. Expense fields:
   - category
   - branch
   - payment mode
   - amount
   - date
   - vendor/payee
   - notes
   - attachment placeholder if practical
   - created_by
4. Reports:
   - daily profit summary
   - expense summary
   - payment mode summary
   - customer receivable
   - supplier payable
   - gross profit by item
   - cashbook
5. Add audit logging.
6. Add tests for expense CRUD, permissions, and report totals.

Frontend tasks:
1. Add Expenses page.
2. Add expense category settings.
3. Add accounting-lite report page or Report Center placeholder if Phase 18 will expand.
4. Add dashboard cards for expenses and net contribution if practical.

Acceptance checks:
- Admin/Manager can record expenses.
- Analyst can view reports only.
- Daily profit report uses sales/invoices, returns, payments, and expenses.
- Receivable/payable reports match ledgers.

Testing after this phase:
1. Run targeted tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_expenses.py tests/test_accounting_reports.py -q
2. Run payment/ledger regression:
   .\.venv\Scripts\python.exe -m pytest tests/test_payments.py tests/test_customer_ledger.py tests/test_supplier_ledger.py -q
3. Run frontend checks.
4. Manual browser test:
   - Add expense.
   - Open daily profit report.
   - Check payment mode summary.
   - Confirm unauthorized users cannot edit expenses if not allowed.

Report back using the standard phase report format.
```

## Phase 11 Prompt: GST Reporting And CA Exports

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, invoice tax rows, purchase bill tax rows, returns, business profile, exports, and Power BI support.

Build Add-On Phase 11: GST reporting and CA exports.

Goal:
Generate GST-ready operational reports and CA-friendly exports from stored tax rows.

Backend tasks:
1. Create GST report service using stored invoice, credit note, purchase bill, debit note, and tax rows.
2. Add APIs:
   - GET /gst-reports/sales-register
   - GET /gst-reports/purchase-register
   - GET /gst-reports/hsn-summary
   - GET /gst-reports/tax-liability
   - GET /gst-reports/gstr1-summary
   - GET /gst-reports/gstr3b-summary
   - GET /gst-reports/validation
   - GET /exports/gst-sales
   - GET /exports/gst-purchases
   - GET /exports/gstr1-summary
   - GET /exports/gstr3b-summary
3. Report sections:
   - B2B
   - B2C
   - credit notes
   - debit notes
   - HSN summary
   - outward taxable supplies
   - inward supplies summary if purchase tax data exists
4. Validation checks:
   - missing GSTIN for B2B customer
   - missing HSN/SAC
   - invalid GST rate
   - invoice tax mismatch
   - negative anomalies
5. Add reporting SQL views if useful for Power BI.
6. Add tests for GST report totals, tax sections, exports, and validation warnings.

Frontend tasks:
1. Add GST Reports page.
2. Add date/tax period filters.
3. Show sales register, purchase register, tax summary, HSN summary, and validation warnings.
4. Add CSV export buttons.
5. Add clear compliance disclaimer.

Documentation tasks:
1. Add docs/GST_REPORTING.md.
2. Explain that reports are for review/export and must be validated by a CA before filing.

Acceptance checks:
- Admin can view GST reports for a tax period.
- CSV exports work.
- Reports come from stored tax rows.
- Missing/invalid tax data is flagged.
- Power BI/export support is updated.

Testing after this phase:
1. Run targeted tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_gst_reports.py tests/test_gst_exports.py -q
2. Run invoice/purchase/return regression:
   .\.venv\Scripts\python.exe -m pytest tests/test_invoices.py tests/test_purchase_bills.py tests/test_sales_returns.py -q
3. Run frontend checks.
4. Manual browser test:
   - Create GST invoice.
   - Create purchase bill.
   - Create credit note.
   - Open GST Reports.
   - Export CSV.
   - Confirm validation warnings appear for incomplete data.

Report back using the standard phase report format.
```

## Phase 12 Prompt: E-Invoice And E-Way Bill Adapter-Ready Workflow

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, GST reports, invoice model, business profile, and compliance documentation.

Build Add-On Phase 12: E-invoice and e-way bill adapter-ready workflow.

Goal:
Prepare structured e-invoice/e-way bill workflows without hardcoding a paid provider or claiming live GST portal filing.

Backend tasks:
1. Add models/migrations for:
   - einvoice_requests
   - eway_bill_requests
   - compliance_payloads
2. Add APIs:
   - POST /compliance/einvoice/{invoice_id}/prepare
   - GET /compliance/einvoice/{request_id}
   - POST /compliance/einvoice/{request_id}/manual-result
   - POST /compliance/eway-bill/{invoice_id}/prepare
   - GET /compliance/eway-bill/{request_id}
   - POST /compliance/eway-bill/{request_id}/manual-result
3. Build payload preparation service:
   - validate business GSTIN
   - validate customer GSTIN if required
   - validate invoice number/date
   - validate HSN/tax rows
   - generate structured JSON payload
   - store status: draft, ready, submitted_manual, completed, failed
4. Allow manual entry of:
   - IRN
   - acknowledgement number/date
   - QR data
   - e-way bill number
   - validity
5. Add provider abstraction interface for future GSP integration.
6. Add tests for validation, payload shape, manual result storage, and permissions.

Frontend tasks:
1. Add compliance actions to invoice detail.
2. Add prepare e-invoice/e-way payload modal/page.
3. Show validation errors clearly.
4. Show JSON payload preview/download.
5. Add manual result entry form.

Documentation tasks:
1. Add docs/EINVOICE_EWAY_ADAPTER.md.
2. Clearly state live integration requires approved provider/API credentials.

Acceptance checks:
- Eligible invoice can produce structured compliance payload.
- Missing required fields are flagged.
- Admin can manually record IRN/e-way bill details.
- No provider credentials are committed.
- No live filing is implied.

Testing after this phase:
1. Run targeted tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_compliance_payloads.py -q
2. Run GST/invoice regression:
   .\.venv\Scripts\python.exe -m pytest tests/test_gst_reports.py tests/test_invoices.py -q
3. Run frontend checks.
4. Manual browser test:
   - Open GST invoice.
   - Prepare e-invoice payload.
   - View validation errors or JSON.
   - Enter manual IRN/e-way result.

Report back using the standard phase report format.
```

## Phase 13 Prompt: Barcode Label Generation

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, product barcode model, inventory batches, and POS product search.

Build Add-On Phase 13: Barcode label generation.

Goal:
Support internal barcode generation and printable product labels.

Backend tasks:
1. Add barcode generation service:
   - configurable prefix
   - uniqueness check
   - barcode value stored against product or batch
2. Add label template model if not already covered by print_templates.
3. Add APIs:
   - POST /barcodes/generate
   - POST /barcodes/labels/preview
   - POST /barcodes/labels/print-data
   - GET /barcodes/product/{product_id}
4. Label data must include:
   - product name
   - barcode
   - MRP
   - selling price if desired
   - unit
   - batch/expiry if applicable
5. Add tests for barcode uniqueness, label data generation, and POS search compatibility.

Frontend tasks:
1. Add Barcode Labels page.
2. Allow selecting products and quantities.
3. Allow generating internal barcode for products missing barcode.
4. Show label preview.
5. Provide browser print action.
6. Keep labels readable and printable.

Acceptance checks:
- Admin can generate barcode for product.
- Generated barcode is unique.
- POS can search generated barcode.
- Label preview includes product name, MRP, and barcode.
- Label print view is usable.

Testing after this phase:
1. Run targeted tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_barcodes.py tests/test_products_retail_catalog.py tests/test_pos_checkout.py -q
2. Run frontend checks.
3. Manual browser test:
   - Generate barcode for product.
   - Print/preview label.
   - Scan/type barcode in POS.
   - Confirm product is found.

Report back using the standard phase report format.
```

## Phase 14 Prompt: Bulk Import And Data Migration Tools

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, current seed script, product/customer/supplier/inventory models, and export services.

Build Add-On Phase 14: Bulk import and data migration tools.

Goal:
Make onboarding realistic by supporting CSV imports and exports for master data and opening balances.

Backend tasks:
1. Add import services for:
   - products
   - customers
   - suppliers
   - opening stock
   - price list
   - barcode list
2. Add export services for:
   - product catalog
   - customers
   - inventory
   - invoices
   - purchase bills
3. Add APIs:
   - POST /imports/products/validate
   - POST /imports/products/apply
   - POST /imports/customers/validate
   - POST /imports/customers/apply
   - POST /imports/suppliers/validate
   - POST /imports/suppliers/apply
   - POST /imports/opening-stock/validate
   - POST /imports/opening-stock/apply
   - GET /exports/products
   - GET /exports/customers
   - GET /exports/invoices
   - GET /exports/purchase-bills
4. Import behavior:
   - validate before writing
   - return row-level errors
   - handle duplicates safely
   - do not partially apply invalid files unless explicitly designed
   - opening stock import must create stock movements
5. Add CSV templates under docs/templates or exports/templates.
6. Add tests for validation, duplicate SKU/barcode, opening stock movement, and permissions.

Frontend tasks:
1. Add Import/Export page.
2. Add upload and validation result UI.
3. Add download template buttons.
4. Add export buttons.

Acceptance checks:
- CSV validation reports row-level errors.
- Product import handles duplicate SKU/barcode safely.
- Opening stock import updates inventory and creates stock movement.
- Export files have clear headers.
- Only authorized users can import.

Testing after this phase:
1. Run targeted tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_imports.py tests/test_exports.py -q
2. Run inventory regression:
   .\.venv\Scripts\python.exe -m pytest tests/test_inventory.py -q
3. Run frontend checks.
4. Manual browser test:
   - Download product template.
   - Upload sample invalid CSV.
   - Confirm row errors.
   - Upload valid CSV.
   - Confirm products created.
   - Import opening stock and confirm movement ledger.

Report back using the standard phase report format.
```

## Phase 15 Prompt: Communication And Invoice Sharing

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, invoice print/PDF, customer contacts, and environment configuration.

Build Add-On Phase 15: Communication and invoice sharing.

Goal:
Allow invoice sharing and payment reminder drafting through provider-safe configurable communication workflows.

Backend tasks:
1. Add models/migrations for:
   - communication_templates
   - outbound_messages
   - message_delivery_logs
2. Supported channels:
   - email
   - WhatsApp share link
   - SMS provider abstraction
3. Add APIs:
   - GET /communications/templates
   - POST /communications/templates
   - PUT /communications/templates/{id}
   - POST /communications/invoices/{invoice_id}/share
   - POST /communications/customers/{customer_id}/payment-reminder
   - GET /communications/outbound
4. Add provider abstraction:
   - no provider secrets committed
   - environment variables documented
   - deterministic fallback creates draft/share link only
5. Add template rendering with safe variables:
   - customer name
   - invoice number
   - amount due
   - due date
   - business name
6. Add audit logs.
7. Add tests for template rendering, missing provider fallback, permission checks, and message log creation.

Frontend tasks:
1. Add communication template settings.
2. Add Share Invoice action.
3. Add payment reminder action from customer ledger/outstanding page.
4. Show delivery status or draft state.

Acceptance checks:
- Invoice can be shared through email/draft link where configured.
- WhatsApp share link can be generated.
- Payment reminder draft uses real ledger amount.
- Missing provider credentials do not crash the app.
- Message attempts are logged.

Testing after this phase:
1. Run targeted tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_communications.py -q
2. Run invoice/customer regression:
   .\.venv\Scripts\python.exe -m pytest tests/test_invoices.py tests/test_customer_ledger.py -q
3. Run frontend checks.
4. Manual browser test:
   - Open invoice.
   - Click share.
   - Generate WhatsApp link or email draft.
   - Open customer outstanding and create payment reminder.

Report back using the standard phase report format.
```

## Phase 16 Prompt: Automated Backup, Restore, And Local Reliability

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, existing backup/restore docs/scripts, settings page, and local-first architecture docs.

Build Add-On Phase 16: Automated backup, restore, and local reliability.

Goal:
Strengthen the local-first reliability story with scheduled backup guidance, backup status visibility, retention policy, and health checks.

Backend/docs/tasks:
1. Review existing backup and restore scripts.
2. Add backup metadata/status tracking if practical:
   - backup path
   - started_at
   - completed_at
   - status
   - size
   - error message
3. Add APIs if safe:
   - GET /backup/status
   - POST /backup/run-local if practical and clearly local-only/Admin-only
4. Add scheduled backup instructions for Windows Task Scheduler.
5. Add backup retention policy.
6. Add optional encrypted backup archive guidance.
7. Add second-location backup guidance.
8. Add startup health check documentation.
9. Ensure scripts do not hardcode secrets.
10. Add tests for backup status endpoint if implemented.

Frontend tasks:
1. Add Backup Status section/page in Settings.
2. Link backup/restore docs.
3. Show last backup status if endpoint exists.
4. Avoid unsafe restore button unless thoroughly designed.

Documentation tasks:
1. Update docs/BACKUP_RESTORE.md.
2. Add docs/AUTOMATED_BACKUP.md if useful.
3. Update README links.

Acceptance checks:
- Admin can see backup documentation and optionally status.
- Backup commands are clear.
- Restore commands are clear.
- Scripts do not contain secrets.
- Database remains local by default.

Testing after this phase:
1. Run backend tests if endpoint implemented:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_backup_status.py -q
2. Run frontend checks.
3. Manually inspect scripts:
   - no hardcoded password
   - uses DATABASE_URL/env
   - safe paths documented
4. Manual UI/doc test:
   - Open Settings backup section.
   - Open backup docs.
   - Run backup script only if safe in local environment.

Report back using the standard phase report format.
```

## Phase 17 Prompt: Advanced AI Business Copilot

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, current AI assistant service, invoice, GST report, customer ledger, supplier ledger, payment, cash register, and reorder services.

Build Add-On Phase 17: Advanced AI business copilot.

Goal:
Expand the AI assistant so it beats traditional billing software by answering invoice, GST, customer credit, supplier payable, cash register, and stock questions using backend tools.

Backend tasks:
1. Add safe AI tool functions:
   - get_gst_summary
   - get_customer_outstanding
   - get_supplier_payables
   - get_cash_register_summary
   - get_invoice_profitability
   - draft_invoice
   - draft_purchase_bill
   - draft_payment_reminder
   - explain_tax_report
   - detect_stock_anomalies
   - suggest_discount_strategy
2. Update intent routing for questions such as:
   - Summarize this month's GST sales.
   - Which customers have overdue balances?
   - Which suppliers do we owe money to?
   - What was today's cash and UPI collection?
   - Which invoices are unpaid?
   - Which products have high stock but low sales?
   - Draft an invoice for this customer.
3. Keep write actions draft-only until user confirmation.
4. Enforce role and branch permissions inside every AI tool.
5. Make deterministic fallback responses from tool data when OPENAI_API_KEY is missing.
6. Store chat sessions/messages and tool metadata.
7. Add tests for:
   - tool use
   - no invented numbers
   - role/branch scope
   - confirmation required for write-like actions
   - GST disclaimer wording

Frontend tasks:
1. Update AI Assistant page with suggested questions for:
   - GST
   - customer dues
   - supplier payables
   - cash register
   - invoices
   - reorder
2. Show draft actions separately from executed actions.
3. Add confirmation UI if any write action becomes supported later.

Acceptance checks:
- AI answers GST, invoice, customer, supplier, payment, and stock questions from real data.
- AI does not invent numbers.
- AI cannot issue invoice or payment automatically.
- AI respects user permissions.
- Missing data is explained clearly.

Testing after this phase:
1. Run targeted tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_ai.py tests/test_ai_addon_tools.py -q
2. Run related service regression:
   .\.venv\Scripts\python.exe -m pytest tests/test_gst_reports.py tests/test_customer_ledger.py tests/test_supplier_ledger.py tests/test_payments.py -q
3. Run frontend checks.
4. Manual browser test:
   Ask:
   - Summarize this month's GST sales.
   - Which customers have overdue balances?
   - Which suppliers do we owe money to?
   - What was today's payment collection by mode?
   - Draft an invoice for a customer.
   Confirm answers use real data and draft actions are not auto-executed.

Report back using the standard phase report format.
```

## Phase 18 Prompt: Competitive Reporting Library

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, current dashboards, exports, Power BI views, invoices, GST reports, ledgers, payments, purchases, and AI tools.

Build Add-On Phase 18: Competitive reporting library.

Goal:
Create a broad report center that competes with traditional billing software reports while preserving the existing Power BI advantage.

Backend tasks:
1. Add report center service with consistent filters:
   - date range
   - branch
   - product
   - category
   - customer
   - supplier
   - payment mode
   - staff/user
2. Implement at least 30 high-value reports across:
   - sales
   - invoices
   - inventory
   - purchases
   - customer receivable
   - supplier payable
   - GST/tax
   - profit
   - staff
   - payment
   - cash register
   - reorder
   - forecast
3. Add APIs:
   - GET /report-center/catalog
   - GET /report-center/{report_key}
   - GET /report-center/{report_key}/export
4. Update SQL reporting views for Power BI:
   - invoice summary
   - GST summary
   - receivables
   - payables
   - payment modes
   - POS sales
   - returns
   - purchase bills
5. Add tests for catalog, permissions, filters, exports, and several critical report totals.

Frontend tasks:
1. Add Report Center page.
2. Show report categories and report list.
3. Add common filter bar.
4. Render table result.
5. Add CSV export button.
6. Link Power BI docs.

Documentation tasks:
1. Update docs/POWER_BI_SETUP.md with new views.
2. Add docs/REPORT_CENTER.md.

Acceptance checks:
- Report catalog lists at least 30 reports.
- Reports filter correctly.
- CSV export works.
- Power BI views are updated.
- Role/branch permissions are enforced.

Testing after this phase:
1. Run targeted tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_report_center.py tests/test_exports.py -q
2. Run dashboard regression:
   .\.venv\Scripts\python.exe -m pytest tests/test_dashboard.py tests/test_gst_reports.py -q
3. Run frontend checks.
4. Manual browser test:
   - Open Report Center.
   - Run sales report.
   - Run customer outstanding report.
   - Run GST report.
   - Export CSV.
   - Login as manager/staff and confirm branch scope.

Report back using the standard phase report format.
```

## Phase 19 Prompt: Staff Performance, Commission, And Access Rights

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, existing users/roles, invoice/sales records, cash register sessions, and auth dependencies.

Build Add-On Phase 19: Staff performance, commission, and access rights.

Goal:
Add staff-level performance reporting and optional commission calculation without building full payroll.

Backend tasks:
1. Extend user/staff profile if needed:
   - display name
   - staff code
   - branch
   - active status
   - commission eligible flag
2. Add models/migrations for:
   - commission_rules
   - commission_calculations
   - access_permission_overrides if needed
3. Add APIs:
   - GET /staff
   - GET /staff/{id}/performance
   - GET /staff/sales-summary
   - GET /staff/commission-report
   - POST /commission-rules
   - PUT /commission-rules/{id}
4. Reports:
   - sales by staff
   - invoices by staff
   - returns by staff
   - payment collection by staff
   - commission estimate
5. Permission matrix:
   - document permissions clearly
   - enforce backend checks
   - do not rely only on frontend hiding
6. Add tests for staff reports, commission calculation, and permission restrictions.

Frontend tasks:
1. Add Staff Performance page.
2. Add commission report section.
3. Add simple commission rules UI if practical.
4. Update Settings or Users page with staff fields if user management exists.

Acceptance checks:
- Admin can view sales by staff.
- Manager can view assigned branch staff.
- Commission report calculates from real invoice/sales data.
- Backend permission matrix is enforced.

Testing after this phase:
1. Run targeted tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_staff_performance.py tests/test_commissions.py tests/test_auth.py -q
2. Run invoice/payment regression:
   .\.venv\Scripts\python.exe -m pytest tests/test_invoices.py tests/test_payments.py -q
3. Run frontend checks.
4. Manual browser test:
   - Login as Admin.
   - Open Staff Performance.
   - Filter by date/branch.
   - View commission report.
   - Login as Staff and confirm restricted access.

Report back using the standard phase report format.
```

## Phase 20 Prompt: Optional Online Store And Customer Ordering Portal

```text
Read PRD_HITECH_COMPETITIVE_ADDONS.md, product catalog, inventory, customer, invoice, and branch scope logic.

Build Add-On Phase 20: Optional online store and customer ordering portal.

Important:
This phase is optional. Do not implement it until POS billing, GST, payments, ledgers, purchase bills, reports, AI, and backup foundations are stable.

Goal:
Add a lightweight customer ordering portal that can receive order requests without bypassing stock, invoice, or approval rules.

Backend tasks:
1. Add models/migrations for:
   - customer_order_requests
   - customer_order_items
   - order_request_status_history
2. Add APIs:
   - GET /storefront/products
   - POST /storefront/order-requests
   - GET /order-requests
   - GET /order-requests/{id}
   - POST /order-requests/{id}/approve
   - POST /order-requests/{id}/reject
   - POST /order-requests/{id}/convert-to-invoice
3. Public storefront must expose only safe product data.
4. Stock availability should be approximate or carefully scoped.
5. Order approval must be required before invoice.
6. Converting to invoice must use the same backend invoice service.
7. Add tests for order request, approval, conversion, stock validation, and abuse prevention.

Frontend tasks:
1. Add optional storefront pages if routed separately.
2. Add admin Order Requests page.
3. Add approve/reject/convert actions.
4. Make it clear this is not a full ecommerce/payment gateway system.

Acceptance checks:
- Customer can submit order request.
- Admin can approve/reject.
- Approved request can convert to invoice.
- Invoice still follows stock, tax, payment, and ledger rules.
- No payment gateway is required.

Testing after this phase:
1. Run targeted tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_order_requests.py tests/test_invoices.py -q
2. Run frontend checks.
3. Manual browser test:
   - Submit order request.
   - Login as Admin.
   - Approve request.
   - Convert to invoice.
   - Confirm inventory logic still works.

Report back using the standard phase report format.
```

## Phase 21 Prompt: Packaging, Demo, QA, And Portfolio Upgrade

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, PRD_HITECH_COMPETITIVE_ADDONS.md, AGENT_STEP_BY_STEP_PROMPTS_HITECH_ADDONS.md, and the current codebase.

Build Add-On Phase 21: Packaging, demo, QA, and portfolio upgrade.

Goal:
Make the upgraded product understandable, impressive, testable, and demo-ready as a Hitech-competitive Indian retail software portfolio project.

Documentation tasks:
1. Update README.md with Version 2 features:
   - POS billing
   - GST invoices
   - barcode
   - customer ledger
   - supplier ledger
   - payments
   - returns
   - GST reports
   - AI copilot
   - report center
2. Add docs/ADDON_ARCHITECTURE.md with expanded architecture diagram.
3. Add docs/HITECH_COMPETITIVE_CASE_STUDY.md.
4. Add docs/HITECH_COMPETITIVE_DEMO_SCRIPT.md.
5. Add docs/HITECH_COMPETITIVE_QA_CHECKLIST.md.
6. Update docs/POWER_BI_SETUP.md for new report views.
7. Update docs/REMOTE_ACCESS.md if app surface changed.
8. Update docs/BACKUP_RESTORE.md and automated backup docs.
9. Add docs/screenshots placeholder instructions if screenshots are not added.

Seed/demo data tasks:
1. Ensure seed data includes:
   - business profile and GSTIN
   - products with HSN, GST, barcode, MRP
   - customers with credit balances
   - suppliers with payables
   - invoices
   - payments
   - returns
   - purchase bills
   - GST report data
   - cash register data
   - AI-answerable scenarios
2. Document demo credentials.

QA tasks:
1. Add or update automated tests for critical workflows:
   - POS invoice
   - GST tax calculation
   - stock reduction
   - stock movement
   - customer credit ledger
   - payment collection
   - sale return
   - purchase bill
   - supplier payable
   - GST report
   - barcode lookup
   - AI tool-backed answers
2. Add manual QA checklist with full demo flow.
3. Run backend test suite or critical groups.
4. Run frontend typecheck/build.
5. Fix blocking failures.

Demo script must include:
1. Explain business problem.
2. Show local-first architecture.
3. Login as Admin.
4. Configure business GST profile.
5. Show product with HSN, GST, barcode, MRP, and stock.
6. Login as Staff.
7. Open POS screen.
8. Scan/search products.
9. Create GST invoice with cash/UPI payment.
10. Print/download invoice.
11. Show inventory reduced and stock movement created.
12. Create credit sale.
13. Show customer outstanding ledger.
14. Record customer payment.
15. Create sale return and credit note.
16. Show GST report.
17. Create purchase bill or receive PO.
18. Show supplier payable ledger.
19. Ask AI: Which customers have overdue balances?
20. Ask AI: Summarize this month's GST sales.
21. Ask AI: Which items should I reorder today?
22. Show forecasting and reorder dashboard.
23. Show Power BI/report center.
24. Explain how this beats traditional billing software through AI, analytics, and remote local-first design.

Acceptance checks:
- Reviewer can understand the upgraded product from README/docs.
- Demo flow is documented and matches implementation.
- Critical backend tests pass or known failures are documented.
- Frontend builds.
- Remaining gaps are clearly separated from completed MVP/add-on work.
- Final status report exists.

Testing after this phase:
1. Run backend tests:
   cd backend
   .\.venv\Scripts\python.exe -m pytest -q
2. If full suite is slow, run critical groups and document why:
   .\.venv\Scripts\python.exe -m pytest tests/test_auth.py tests/test_inventory.py tests/test_invoices.py tests/test_pos_checkout.py tests/test_invoice_tax.py tests/test_payments.py tests/test_customer_ledger.py tests/test_sales_returns.py tests/test_purchase_bills.py tests/test_gst_reports.py tests/test_ai.py -q
3. Run frontend checks:
   cd frontend
   npm run typecheck
   npm run build
4. Manual full demo:
   - Follow docs/HITECH_COMPETITIVE_DEMO_SCRIPT.md end to end.
5. Create docs/HITECH_COMPETITIVE_FINAL_VERIFICATION.md with:
   - commands run
   - test results
   - implemented requirements
   - known gaps
   - portfolio readiness conclusion

Report back using the standard phase report format.
```

## Final Expansion Definition Of Done

The Hitech-competitive add-on expansion is done when:

- Business profile and GST settings are configurable.
- Products support HSN, GST rate, barcode, MRP, unit, brand, and retail flags.
- Customers and customer ledger work.
- POS checkout creates issued invoices.
- GST/Non-GST invoice totals are calculated by backend.
- Issued invoices reduce inventory.
- Every stock change creates stock movement.
- Invoice print/receipt view works.
- Payment modes, partial payments, and credit sales work.
- Customer outstanding is accurate.
- Sale returns and credit notes adjust stock, tax, and ledger.
- Purchase bills and supplier ledger work.
- GST reports and CSV exports work from stored tax rows.
- Barcode labels can be generated and scanned in POS.
- AI assistant answers GST, invoice, stock, customer, supplier, and payment questions from tools.
- Report Center and Power BI views cover the expanded data.
- Backup/reliability docs are upgraded.
- Tests cover critical business rules.
- README, case study, demo script, QA checklist, and final verification docs are complete.

