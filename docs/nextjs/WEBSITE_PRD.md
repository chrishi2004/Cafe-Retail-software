# Kalpvriksh Group — Website Product Requirements Document

**Document version:** 1.1 · **Source audit:** 18 October 2026
**Source repository:** `chrishi2004/Cafe-Retail-software`
**Preserved source commit:** `5d36734d4c104d21f92fc35ac6b7d595bba65187`
**Current development branch:** `main` (merged rewrite baseline `9a80860`)
**Target:** Next.js App Router + TypeScript server Route Handlers + MongoDB Atlas; deployable as a separate Vercel project.

> This document specifies the whole existing product and the web rewrite. It distinguishes existing functionality from native Next.js implementation. Native web workflows are implemented on main; full legacy parity and production acceptance are not claimed. See the implementation report for explicit compatibility decisions and verification results. A compiled page is not evidence that every API used by that page has been ported. The installed Café, PostgreSQL data and existing release branches are unchanged.

## 1. Product purpose and success criteria

Kalpvriksh Group operates two ventures: Kalpvriksh Cafe and Kalpvriksh Retail. The website gives each employee a scoped operational workspace and gives the owner an authorized view across both ventures. It covers sales, billing, receipts, stock, customers, suppliers, purchases, closing, reporting and optional customer QR ordering, forecasts and AI assistance.

The full web target is a single application URL with server-side authorization for every request. Different counters, kitchen screens and owner devices use independent authenticated sessions; a shared CPU or multiple monitors do not change the authorization model. Operating-system multiseat and printer-driver installation are outside the website.

A completed rewrite must reproduce the existing business contracts and pass transaction, monetary, role, branch, concurrency, reporting and failure tests. No synthetic business data or hard-coded revenue may be used to demonstrate production readiness. Existing invoice numbers, original transaction dates and record ownership must survive any separately approved data import.

### Architecture decision

The user selected **MongoDB Atlas** for this new branch. Atlas becomes the target web application's authoritative store only after an approved migration/cutover. No PostgreSQL → MongoDB import is executed by this branch. During development the original PostgreSQL installation remains authoritative for the customer's existing operations.

An Atlas-hosted application requires working internet connectivity for authoritative billing. The earlier LAN-only/offline requirement is **not satisfied** by this new architecture. A browser cache is not a financial database, and the app must never report a successful bill when the server transaction failed. Offline writes require a separate, explicit design and acceptance decision; they are not silently included in this conversion.

## 2. Audited scope and counting rules

| Inventory | Actual count | Interpretation |
| --- | ---: | --- |
| Logical user screens | **35** | 16 Retail (including Daily Closing) + 13 Café + 4 owner + login + public QR ordering |
| Existing page component modules | **29** | Shared/generic components render multiple logical screens; not 29 distinct URLs |
| Operational API paths | **140** | Distinct OpenAPI paths, excluding method multiplicity |
| Operational API operations | **163** | Each HTTP method/path pair counted separately |
| Restricted cloud API operations | **15** | Includes its own health operation; not 15 additional unique public URLs |
| Existing service modules | **34** | Includes the package initializer |
| Top-level service functions/classes | **474** | Includes private helpers, not just user-facing features |

These counts are generated from actual source, not a proposed sitemap. Login currently renders on unauthenticated portal routes; `/login` is the target explicit entry route. Retail historically used hash navigation; the new app routes its copied workspace through Next.js navigation and accepts old hash links. Table order status is a state inside the public order screen, not an extra counted page. Modals, receipt overlays, tax panels and generic master-data variations are not counted as additional component files.

`CafeContinuityPage.tsx`, `SettingsPage.tsx` and generic dashboard/fallback code exist in source but do not each create an additional primary navigation destination. Preserve them in the reference inventory; do not inflate the screen count.

## 3. Users, roles and information boundaries

| Role | Primary purpose | Default destination / constraints |
| --- | --- | --- |
| Business owner (`super_admin`) | Select ventures, review consolidated results and users | `/super-admin/ventures`; company selection must belong to the owner's group |
| Venture admin (`admin`) | Configure and operate one venture | Café dashboard or Retail overview; company-wide permissions |
| Store manager (`store_manager`) | Branch operations, stock, purchases, reporting | Assigned branch only; no cross-company switching |
| Employee/cashier (`staff`) | Fast sales, billing and authorized receipt lookup | Café POS or new Retail POS; the preserved Retail source default was overview |
| Order taker (`order_taker`) | Café order intake and permitted billing | Café POS; no Retail access |
| Kitchen (`kitchen`) | Café preparation queue and permitted state changes | `/cafe/kitchen`; no invoice/payment administration |
| Analyst (`analyst`) | Authorized reporting and analysis | Read access only; no checkout, stock adjustment or closing writes |
| Customer/guest | Menu, cart, order tracking and bill request | `/order/{token}`; no employee financial or administrative API access |

Sidebar visibility improves usability; **the API is the security boundary**. Tenant scope comes from a verified account and validated owner venture selection, never an arbitrary `company_id` sent in JSON. Branch records, products, customers and payment modes must belong to that same venture. A receipt ID from the other venture returns unavailable, not its contents.

Privileged MFA is required. Preserve logout revocation and do not close the business day when an employee logs out. Protect destructive operations with step-up and the existing governance approval rules after their native port is verified.

## 4. Page catalogue — shared entry

| ID / route | Content and purpose | Main actions and navigation | Access / API groups |
| --- | --- | --- | --- |
| G01 `/login` | Kalpvriksh branding; email, password, authenticator/recovery-code fields; login errors | Authenticate → role-specific portal; no public self-registration | Employees/owner; `/auth/login`, `/auth/me`, MFA lifecycle |
| G02 `/order/{token}` | QR resolution, configured Café/table identity, menu categories, availability, cart, submitted orders/status, bill request | Scan → resolve session → browse → add quantities → submit → track; request bill without issuing invoice | Restricted guest capability; `/public/cafe/*` or restricted `/cloud/public/cafe/*` |

## 5. Page catalogue — Retail (15 screens)

Owner entry selects Retail; the Retail shell shares a role-filtered sidebar. Every screen includes appropriate loading, empty, validation and failure states.

| ID / route | Contents and purpose | Main actions / next destinations | Existing API groups |
| --- | --- | --- | --- |
| R01 `/retail/overview` | Revenue, transaction, inventory and purchasing overview; role-specific KPIs/charts | Filter branch/period; open POS, sales, inventory and purchases | `/dashboard/*` |
| R02 `/retail/products` | Product catalogue, SKU/barcode, category, supplier, costs/prices and active state | Search; create/edit/deactivate; proceed to POS or inventory | `/products`, `/products/search`, `/products/{id}` |
| R03 `/retail/customers` | Customer identity/contact/tax details, balances and ledger/payment interactions | Search; create/edit; review ledger; record authorized customer payment | `/customers/*` |
| R04 `/retail/pos` | Barcode/product search, branch/customer selection, cart quantities, authorized discounts, tax mode, quote and payment rows | Quote → Cash/UPI/Card → checkout → invoice/print → reset for next customer; hold draft where supported | `/pos/products/search`, `/pos/quote`, `/pos/checkout`, `/invoices` |
| R05 `/retail/sales` | Historical sales and summaries with date/branch/product filters | Review results; export; navigate to operational analysis | `/sales`, `/sales/summary`, `/exports/sales` |
| R06 `/retail/inventory` | Product/branch stock, reserved/on-order figures, value, movement history and adjustment form | Filter; inspect product; authorized stock adjustment | `/inventory`, `/inventory/{product_id}`, `/inventory/movements`, `/inventory/adjustments` |
| R07 `/retail/low-stock` | Low-stock list and reorder recommendations by priority/supplier/category | Filter shortages; inspect purchasing needs; proceed to purchase orders | `/inventory/low-stock`, `/inventory/reorder-recommendations` |
| R08 `/retail/purchase-orders` | Purchase dashboard, order list/details, status and receipt history | Create/edit → approve/mark ordered → receive partially/fully; authorized cancel; export | `/purchase-orders/*`, `/exports/purchase-orders` |
| R09 `/retail/suppliers` | Supplier directory, contacts, address, tax and lead-time fields | Search/create/edit; use in product and purchase flows | `/suppliers/*` |
| R10 `/retail/categories` | Product category master data | Create/edit classification; return to products/inventory | `/categories/*` |
| R11 `/retail/branches` | Branch address/location/manager and active state | Create/edit branch; assign operational scope through authorized user management | `/branches/*` |
| R12 `/retail/forecasting` | Forecast runs/history, product demand/revenue trends and model results | Choose period/product/type; run authorized forecast; export | `/forecasts/*`, `/exports/forecasts` |
| R13 `/retail/ai-assistant` | Conversation UI, saved sessions and scoped operational questions | Ask supported questions; inspect answer/data; reopen session | `/ai/chat`, `/ai/sessions/*` |
| R14 `/retail/power-bi` | Reporting/BI surface and configured report context | Review available reports and navigate back to operational screens | Existing reporting/export sources; external BI availability requires separate configuration |
| R15 `/retail/settings` | Business profile, GST/tax operation, rates, payment modes and invoice sequence settings | Configure authorized settings; validate statutory activation prerequisites | `/business-profile`, `/tax-operation/*`, `/tax-rates`, `/payment-modes`, `/invoice-sequences` |

**Observed gap:** the existing Retail shell has no dedicated daily-closing navigation entry and no separate historical receipt page. Do not claim those are existing pages. Native Retail closing and receipt-history UX are required for final parity/product acceptance and may add routes after deliberate scope review.

## 6. Page catalogue — Café (13 screens)

| ID / route | Contents and purpose | Main actions / next destinations | Existing API groups |
| --- | --- | --- | --- |
| C01 `/cafe/dashboard` | Today order count, billed/net sales, collections, Cash/UPI/Card, outstanding, average bill, top items and open orders | Monitor current business; navigate to orders, reports and closing | `/dashboard/cafe`, `/cafe/orders` |
| C02 `/cafe/orders` | Live orders with source, table/takeaway, value, status and permissible actions | Accept/reject → preparation → ready/served; request bill/cancel under rules | `/cafe/orders/*` |
| C03 `/cafe/pos` | Simple menu search/select, quantities, counter/takeaway, payment mode, receipt and next customer | Immediate transactional checkout; print; reset; receipt history | `/cafe/menu/*`, `/payment-modes`, `/branches`, `/cafe/billing/pos/checkout` |
| C04 `/cafe/new-order` | Staff table/standalone order creation with table/session and item selection | Choose context → add items → submit → live order/kitchen | `/cafe/table-sessions`, `/cafe/orders`, menu/table APIs |
| C05 `/cafe/tables` | Tables, active sessions and QR status/print controls | Create/edit/deactivate; open/close session; rotate/revoke/render/print QR | `/cafe/tables/*`, `/cafe/table-sessions/*` |
| C06 `/cafe/menu` | Categories, menu item price, product mapping, preparation area and availability | Create/edit; toggle availability; manage catalogue | `/cafe/menu/categories`, `/cafe/menu/items/*` |
| C07 `/cafe/inventory` | Shared inventory component scoped to Café company/authorized branch | Inspect balances and movements; authorized adjustments | `/inventory/*` |
| C08 `/cafe/billing` | Table/order bill candidates, eligible/excluded items, quotes and collections | Quote → issue bill with key/version → collect authorized balance → receipt | `/cafe/billing/table-sessions/*`, `/cafe/billing/orders/*`, invoice receipt/payment APIs |
| C09 `/cafe/receipts` | Searchable date/branch-filtered invoice history and receipt preview | Read existing invoice → authorized reprint; never create a transaction | `/cafe/billing/invoices`, `/cafe/billing/invoices/{id}/receipt` |
| C10 `/cafe/reports` | Today, Yesterday, 7 Days, This Month, Last Month and custom dates; sales/payment/item metrics | Apply dates; review comparisons; download CSV | `/dashboard/cafe`, `/exports/cafe` |
| C11 `/cafe/settings` | Company tax operation/profile prerequisites | Review/change authorized configuration; guarded GST activation when supported | `/tax-operation/*` |
| C12 `/cafe/closing` | Authorized branch/day, opening cash, collections, expected/count/non-cash/variance and status | Open day → submit count → close; controlled reopening | `/governance/closings/*` |
| C13 `/cafe/kitchen` | Preparation queue, item preparation context and status controls | Begin preparing → mark ready → hand over under permissions | `/cafe/kitchen/orders`, order transitions |

## 7. Page catalogue — owner (4 screens)

| ID / route | Contents and purpose | Main actions / navigation | Existing API groups |
| --- | --- | --- | --- |
| O01 `/super-admin/ventures` | Active ventures, separate/combined turnover and workspace selection | Enter Café or Retail; switch back without broadening employee permissions | `/ventures`, `/tax-operation/combined-turnover` |
| O02 `/super-admin/dashboard` | Consolidated financial/item/payment view with period filters and venture summaries | Compare ventures; export consolidated report; open selected venture | `/dashboard/consolidated`, `/exports/consolidated` |
| O03 `/super-admin/users` | Group users, role, company and active state | Review assignments; target authorized user provisioning/update UI | `/venture-users`, `/venture-users/{id}` |
| O04 `/super-admin/purge` | Protected data-removal review, dependency report, backup reference and approvals | Request/review/approve/execute only with appropriate governance and step-up | `/governance/purges/*`, step-up |

## 8. Navigation and operating flows

### Authentication and workspaces

Unauthenticated request → login → validate credentials, MFA and active group/company/branch → establish session → owner venture selector, Café role destination or Retail destination. An unauthorized deep link resolves to the user's allowed portal; server requests outside their scope are independently rejected. Owner venture changes affect only that owner's session and are validated on every server call.

### Retail sale

Authorized branch → barcode/search → fresh product/stock/price lookup → cart quantity/discount → server quote → operator payment confirmation → transactional sequence allocation, invoice, payments and stock movements → receipt → next-customer reset. An ambiguous network timeout retains the payment key so retry returns the same outcome. A changed payload with the same key is a conflict.

### Café counter sale

Menu selection → quantity → counter/takeaway → Cash/UPI/Card → atomic billing using the existing domain contract → automatically created invoice → receipt/print → clear paid cart → next customer. Logout ends the session only.

### Table and QR order

Guest scans restricted QR → menu/session capability → cart submission with duplicate protection → staff acceptance and kitchen state changes → bill request → authorized staff invoice/payment → closure. Guest requests never select internal company/branch IDs or call staff financial handlers. The old hybrid sync/continuity state machine requires a deliberate redesign for a web-authoritative target; do not label all `/cloud` endpoints obsolete without deciding customer/device recovery semantics.

### Purchasing and stock

Supplier/category/product configuration → purchase draft → approval/order → receive quantities against outstanding lines → one stock and cost/accounting effect per receipt → inspect movements and low-stock state. Retried receipts must not double-count. Manual changes require reason, actor and audit history. Never edit a quantity without a corresponding movement.

### Closing

Authorized venture/branch → actual business date → opening cash → derive confirmed cash collections minus refunds/expenses → enter counted cash → calculate variance → submit → close. Non-cash collections appear separately. Checkout and closing must serialize at branch/day level to prevent a bill slipping into a finalized period. Reopening is audited and privileged.

## 9. Functional requirements

| ID | Requirement | Acceptance condition |
| --- | --- | --- |
| IAM-01 | Credential login, MFA and revocable sessions | Expired/revoked/invalid sessions fail; privileged accounts cannot bypass MFA |
| IAM-02 | Group/company/branch isolation | Guessed IDs, headers and payload assignments cannot cross boundaries |
| CAT-01 | Product/barcode and Café menu masters | Correct scoped lookups, immutable historical line snapshots and availability controls |
| SALE-01 | Retail and Café checkout | Invoice, payments, sequence and stock commit together or all roll back |
| SALE-02 | Idempotency | Parallel same-key/same-body requests return one transaction; changed body conflicts |
| SALE-03 | Numeric correctness | Integer paise/scaled quantity or decimal arithmetic; no binary-float monetary drift |
| SALE-04 | Stock concurrency | Two buyers cannot sell the same final stock twice; unavailable/reserved stock is respected |
| TAX-01 | GST/non-GST and effective dates | Match old tax quotes, rounding, place-of-supply, invoice formats and statutory settings |
| PRINT-01 | 80mm receipt-only print | Company/branch, number/date, item/qty/unit/line totals, tax where applicable, total/payment/paid/balance; no navigation/buttons |
| PRINT-02 | Authorized historical reprint | No new invoice, payment, sequence allocation, stock or accounting write |
| INV-01 | Inventory and supplier purchasing | Adjustments/receipts are authorized, audited, atomic and retry safe |
| CUST-01 | Customer ledger | Opening balances, invoices, collections and credit/refund entries reconcile |
| CAFE-01 | Counter/table/kitchen lifecycle | Legal transitions, stale-version conflicts and explicit cancellation/refund rules |
| QR-01 | Restricted public ordering | Token/session isolation, bounded payloads/rates, durable retries; no guest financial posting |
| REP-01 | Venture and consolidated reporting | Identical source transactions produce reconciled date-range totals and exports |
| GOV-01 | Closing/reversal/purge | Audit, step-up, dependency checks and backup requirements retained |
| OPS-01 | Backup/restore and migration | Restore drill and historical reconciliation succeed before approved import/cutover |
| INT-01 | Forecasts, AI, BI | Preserve scoped input/output contracts or explicitly mark functionality unavailable |

UPI/Card records are operator-confirmed payment records unless an actual provider integration is implemented. Do not display bank settlement or terminal confirmation that was never obtained.

## 10. API specification and complete reference

The full method/path catalogue is [API_ROUTE_INVENTORY.md](API_ROUTE_INVENTORY.md), with machine-readable [CSV](API_ROUTE_INVENTORY.csv). Original request/response schemas, parameter constraints and declared security are retained in [operational-openapi.json](operational-openapi.json) and [cloud-openapi.json](cloud-openapi.json). Authentication dependencies must still be checked in the source: OpenAPI alone does not enumerate every role or company filter.

| Domain | Representative contracts | Purpose |
| --- | --- | --- |
| Identity | `/auth/login`, `/auth/me`, `/auth/logout`, `/auth/step-up`, `/auth/mfa/*` | Authentication, session/MFA lifecycle |
| Group | `/ventures`, `/ventures/current`, `/venture-users/*` | Authorized venture and team management |
| Master data | `/products/*`, `/categories/*`, `/suppliers/*`, `/branches/*` | Catalogue and organizational configuration |
| Business settings | `/business-profile`, `/payment-modes`, `/invoice-sequences`, `/tax-rates`, `/tax-operation/*` | Legal/business/tax/payment/number configuration |
| Customers | `/customers/*` | Customer profile, addresses, ledger and payments |
| Retail billing | `/pos/products/search`, `/pos/quote`, `/pos/checkout`, `/invoices/*` | Quotes, invoicing, collections and lifecycle |
| Inventory | `/inventory/*` | Stock visibility, movements, adjustments and reorder |
| Purchases | `/purchase-orders/*` | Approval/order/receipt/supplier workflow |
| Café | `/cafe/menu/*`, `/cafe/tables/*`, `/cafe/table-sessions/*`, `/cafe/orders/*`, `/cafe/kitchen/orders` | Menu, sessions, order lifecycle and preparation |
| Café billing | `/cafe/billing/*` | Existing-source quotes/bills, fast counter checkout, receipt history and payment |
| Reporting | `/dashboard/*`, `/sales/*`, `/exports/*` | Metrics, dates and CSV |
| Governance | `/governance/*` | Closing, reversal, step-up and controlled purge |
| Intelligence | `/forecasts/*`, `/ai/*` | Scoped forecasts/conversations |
| Guest | `/public/cafe/*` | Restricted table/session customer interactions |
| Hybrid/cloud | `/sync/*`, `/cloud/*` | Publications, commands, receipts, leases and reconciliation |

API invariants: validate bodies; reject unknown financial state transitions; derive money server-side; verify related-document ownership; require idempotency/version where appropriate; never serialize password hashes, MFA secrets or database credentials; use no-store for private responses. Vercel/browser public environment variables contain only public URLs, never Atlas URI or signing keys.

## 11. Backend function catalogue and data model

[The service-function CSV](SERVICE_FUNCTION_INVENTORY.csv) lists all **474** top-level functions/classes with source file and line. This is an engineering appendix; business capabilities are grouped below.

| Function group | Existing service modules | Responsibilities |
| --- | --- | --- |
| Financial | `invoices`, `sales`, `cafe_billing`, `cafe_pos`, `business_settings`, `tax_operation` | Price/tax calculation, numbers, issue/collect/cancel, source billing and legal settings |
| Catalogue/stock | `barcodes`, `inventory`, `purchase_orders`, `reorder`, `customers` | Product lookup, movements, receipt/cost flow, shortages and customer ledger |
| Café operations | `cafe`, `cafe_order_engine`, `cafe_staff_orders`, `cafe_bill_request` | Menu/table/session, staff order states and bill requests |
| Public coordination | `public_cafe`, `public_cafe_entry`, `public_cafe_ordering`, `cafe_cloud_publication` | Restricted token resolution, menu/order input and publication |
| Reporting | `dashboard`, `p9_reporting`, `exports`, `business_day` | KPI and consolidated queries, CSV, timezone/date boundaries |
| Controls | `audit`, `governance`, `production_safety` | Immutable evidence, closing/reversal/purge and production guards |
| Hybrid transport | `cloud_coordination`, `cloud_transport`, `continuity`, `hc3_cloud_orders`, `hc3_cloud_bill_requests` | Durable messaging, convergence, leases and recovery |
| Intelligence | `forecasting`, `ai` | Demand/revenue prediction and scoped conversational operations |

### MongoDB target representation

One target operational database contains `business_groups`, `companies`, `branches`, `users`, catalogue/configuration collections, customers/ledger, inventory/movements, orders/sessions, invoices/payments, purchasing, governance and audit collections. Do not give Café and Retail independent financial databases.

Keep numeric legacy-compatible public `id` fields where required by existing UI contracts; MongoDB `_id` remains internal. Store server-derived invoice lines and branded historical snapshots, with payments in the same financial transaction. Use unique indexes for company invoice numbers, company payment keys, branch/product inventory and branch/date closing. Idempotency binds an authenticated actor, company, request key and canonical body hash. A key cannot be reused for a different body.

Use multi-document transactions on a replica-set-capable deployment. Never implement a non-transactional financial fallback for a standalone server. Transaction retry callbacks must not send external messages or charge a provider. Sequence increments, invoice creation, stock deductions, movement entries and payment records share the same session/transaction. Domain activity and accounting audit must be explicitly ported before production acceptance.

## 12. Current conversion status — honest parity boundary

The [endpoint parity CSV](NEXTJS_API_PARITY.csv) records 158 native-service operation entries, five single-database status/check replacements and 15 explicitly retired Local Hub interfaces. Among the 163 operational operations, 162 dispatch natively and the obsolete Local Hub retry interface is retired. The shared health operation appears in both original inventories. These are implementation classifications, not claims that every legacy edge case is certified.

The current route inventory contains **35 logical screens**. The additional `/retail/closing` screen reuses the closing workflow for independently scoped Retail cash counts and owner/admin correction with password/MFA step-up. The source gateway's QR functionality now uses native `/api/public/cafe/*` APIs; old device/writer-lease/sync gateway paths are not part of the hosted-only architecture.

See [the implementation and acceptance report](NATIVE_COMPLETION_REPORT.md) for native modules, automated evidence, inherited Python date-boundary failure, deployment setup, rollback boundaries and remaining production gates. The original local-first source remains preserved. Physical printing, Atlas backup/restore, payment-provider settlement and statutory A4 GST acceptance are not established by automated builds.

## 13. Nonfunctional requirements and release gates

- Financial integrity: exact monetary arithmetic; no double issue/payment/stock; repeatable history reconciliation; valid transaction/index setup before accepting sales.
- Security: least privilege, tenant/branch filters, bounded input, durable distributed login/public rate controls, MFA, encrypted secrets, revocation, no public financial endpoints, audited administration and protection against ID enumeration.
- Availability: explicit service-unavailable states; retries retain transaction identity; no false success offline. Define measured latency, concurrency and recovery targets after representative deployment tests rather than inventing them.
- UX: keyboard/barcode-first Retail; simple Café counter flow; obvious payment/receipt state; responsive owner views; accessible labels, errors and loading states.
- Printing: browser print with only 80mm receipt content; actual driver/paper tests required. Web deployment does not install printer drivers or guarantee silent printing.
- Operations: external secrets, separate staging/production databases and projects, controlled new bootstrap, versioned data migrations, dependency audits, health checks and structured non-sensitive error logs.
- Recovery: verified MongoDB backup plus independent copy and disposable restore; original PostgreSQL archives retained. Hosting/database tier selection, retention, scheduling, quotas and cross-OS restore must be explicitly certified. Do not assume an Atlas free account supplies the former Linux backup policy.
- Release: no customer cutover until all source contract domains, tests, physical devices, import reconciliation, backup/restore and business acceptance pass. Never replace the currently installed Café from this branch automatically.

## 14. Data migration and rollout

1. Freeze a reviewed PostgreSQL source version and archive; inventory real groups, companies, users, sequences, tax settings and reports.
2. Design a mapping of keys, enums, timestamps, decimals, null values, constraints and foreign references to indexed MongoDB collections. Preserve historical IDs/numbers/snapshots. Treat password/MFA formats as a separate migration: the new scrypt/AES representation is not automatically compatible with old password/TOTP storage.
3. Export from a consistent source snapshot; import into a separate Atlas staging database. No automatic reseeding or live dual-write.
4. Reconcile counts, invoice/payment/tax totals, balances, stock movements, customer ledger, sequences and closing by company/branch/date. Verify old invoice lookup and reports on the imported copy.
5. Complete native API parity and browser/transaction tests, print tests and workload tests. Certify backups and restore in the chosen environment.
6. Approved cutover: quiesce old writers, take final archive and independent copy, import/reconcile delta or repeat clean staging process, deploy immutable reviewed web version, validate then open sales. Never allow both stores to issue financial records independently for the same business during transition.
7. Rollback: before new web sales, return to old unchanged system after verifying no new accepted financial writes. After web sales, code rollback alone cannot discard/replay transactions safely; freeze writes and reconcile/forward-repair or execute an explicitly approved recovery plan. Record the backup's data-loss boundary.

## 15. Acceptance scenarios

| Scenario | Required evidence |
| --- | --- |
| Cash/UPI/Card at each venture | Correct scoped invoice, payment, receipt, stock and sequence; next customer works |
| Same-key parallel Pay / retry after timeout | One committed invoice/payment set and stock effect; same result on retry |
| Two simultaneous buyers of last units | No negative/oversold available stock; correct conflict and rollback |
| Unauthorized actions | Staff cannot manage owner configuration, close outside permission, switch venture or read another branch invoice |
| Historical print/reprint | Receipt-only 80mm output; before/after business records unchanged |
| GST/non-GST/credit/refund | Reference-engine parity across rounding, rates, split taxes, dates and reversal/ledger rules |
| Purchases/receiving | Partial/full/retried receipts reconcile quantity, cost, supplier and movements |
| Dashboard/report/CSV | Today/month/custom dates and company/consolidated totals reconcile with source records |
| Closing concurrent with payment | No transaction posted into a closed period; counted/expected/non-cash/variance correct |
| QR/kitchen | Restricted guest input, duplicate prevention and legal staff state transitions; no guest invoice posting |
| Migration/recovery | Populated source import reconciled; verified archive restored; documented RPO/RTO boundaries |
| Frontend/backend release | Typecheck/build, native Mongo integration, preserved Café regression, dependency/security checks and browser acceptance |

## 16. Repository handoff

- `apps/web`: independently built Next.js frontend and native TypeScript backend.
- `frontend` and `backend`: unchanged original Vite/FastAPI reference application, including Alembic history and installed-device scripts.
- `docs/nextjs/API_ROUTE_INVENTORY.md` / `.csv`: every original HTTP operation.
- `docs/nextjs/*-openapi.json`: original request/response schemas.
- `docs/nextjs/SERVICE_FUNCTION_INVENTORY.csv`: source-level function appendix.
- `docs/nextjs/SOURCE_INVENTORY.json`: reproducible counts and source SHA.
- `scripts/inventory_nextjs_rewrite.py`: regenerate reference inventory using the existing development Python environment; not a production Next.js dependency.
- `apps/web/README.md`: setup, test commands, implementation boundary and deployment instructions.

Technical references: [Next.js installation](https://nextjs.org/docs/app/getting-started/installation), [Route Handlers](https://nextjs.org/docs/app/api-reference/file-conventions/route), [MongoDB Node transactions](https://www.mongodb.com/docs/drivers/node/current/crud/transactions/). Version pins and resolved dependencies are in the new app's lockfile.
