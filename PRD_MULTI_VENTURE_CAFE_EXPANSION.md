# Product Requirements Document: Multi-Venture Retail And Cafe Expansion

## Document Status

- Version: 1.1
- Status: Approved planning baseline with hybrid cloud continuity addendum; implementation not started
- Product stage: Version 3 expansion of the existing retail/POS system
- Last updated: 2026-08-11

## Product Name

AI-Powered Hybrid Multi-Venture Retail And Cafe Management Platform

## Document Purpose And Precedence

This document is the product contract for adding a second, Cafe-focused venture to the existing retail management application. It defines what must be built, who may see each venture, how customers and staff create Cafe orders, how billing and tax modes behave, and how the Final Super Admin governs both ventures.

Future implementation agents must read these documents in this order:

1. `PRD.md` - existing retail, inventory, analytics, forecasting, AI, and local-first foundation.
2. `PRD_HITECH_COMPETITIVE_ADDONS.md` - existing billing, POS, GST-ready, barcode, invoice, and ledger add-on contract.
3. `PRD_MULTI_VENTURE_CAFE_EXPANSION.md` - product contract for venture isolation and Cafe operations.
4. `PRD_HYBRID_CLOUD_CONTINUITY_ADDENDUM.md` - approved Vercel, Supabase, Local Hub, outage, and automatic recovery contract.
5. `TRD_MULTI_VENTURE_CAFE_EXPANSION.md` - technical and security contract for the business expansion.
6. `TRD_HYBRID_CLOUD_CONTINUITY.md` - technical contract for cloud coordination, durable queues, and recovery.
7. `docs/MULTI_VENTURE_CAFE_IMPLEMENTATION_PHASES.md` - required implementation order and phase gates.
8. `AGENT_STEP_BY_STEP_PROMPTS_MULTI_VENTURE_CAFE.md` - standalone execution prompt for each approved phase.

When requirements conflict, the newest document controls its stated scope. The hybrid addendum supersedes older one-deployment and no-cloud-database topology statements only. Existing stock, invoice, ledger, audit, local authority, and AI data-integrity rules remain mandatory.

## 1. Existing Product Baseline

The current application already provides a strong Retail venture foundation:

- FastAPI backend and React TypeScript frontend.
- Local PostgreSQL database with SQLAlchemy and Alembic.
- Authentication, role checks, and branch scoping.
- Products, categories, suppliers, customers, inventory, and stock movements.
- Sales, invoices, POS checkout, payment modes, and customer ledger.
- Purchase orders, receiving, reorder recommendations, and forecasting.
- Operational dashboards, CSV exports, Power BI support, and AI data tools.
- GST-ready product and invoice fields, with GST and Non-GST invoice types.
- Local-first remote access, backup, audit, and QA documentation.

This expansion must reuse those capabilities. It must not create a separate Cafe backend, database, authentication system, invoice engine, or payment engine.

## 2. Business Context

The owners operate two distinct ventures under a common partnership or ownership group:

1. Retail venture - the existing inventory, POS, billing, purchasing, and analytics product.
2. Cafe venture - table-based QR ordering, staff order entry, order preparation, billing, payments, and Cafe reporting.

The owners need one management system and one Final Super Admin view, while the Cafe partner must see only the Cafe venture. Retail information, totals, customers, inventory, staff, and reports must never be visible from the Cafe partner account.

Customers need a low-friction mobile ordering flow after scanning a table QR code. Cafe staff must also be able to enter an order directly for the same table, takeaway customer, or counter sale. Both entry methods must feed one consistent order, bill, payment, and audit workflow.

## 3. Product Vision

Provide one local-first business platform with clearly separated venture workspaces:

- A Final Super Admin can supervise Retail, Cafe, and consolidated performance.
- A Cafe Partner Admin can operate and analyze only the Cafe venture.
- Retail users remain inside the Retail venture.
- Cafe managers, order takers, cashiers, and kitchen staff receive task-specific interfaces.
- Customers receive a simple mobile menu and ordering experience without access to internal systems.
- Billing, stock, payment, audit, tax readiness, backup, and reporting remain centrally governed.

## 4. Product Goals

### 4.1 Business Goals

- Keep exact Retail and Cafe sales separated while supporting owner-level consolidated reporting.
- Give the Cafe partner full visibility into the Cafe venture without revealing Retail information.
- Reduce order-taking errors through table QR ordering and a staff order-entry alternative.
- Distinguish ordered value, billed revenue, money collected, unpaid value, cancellations, and refunds.
- Reuse the current invoice, payment, inventory, reporting, and local-first infrastructure.
- Operate without a paid cloud database by default.
- Remain Non-GST by default today while preserving a controlled path to GST activation later.
- Make financial corrections traceable and prevent silent deletion from changing business history.

### 4.2 Customer Goals

- Scan a table QR and open the correct Cafe menu immediately.
- Place an order without creating an account.
- See accurate menu prices, availability, cart totals, and order status.
- Add more items during the same open table session.
- Request the bill without needing to call the billing counter repeatedly.
- Never see internal inventory, cost, staff, tax configuration, or other customers' data.

### 4.3 Staff Goals

- Create an order directly when a customer does not use QR ordering.
- Select dine-in table or takeaway mode.
- Receive and process QR orders in one live order queue.
- Track orders through accepted, preparing, ready, served, billed, and closed states.
- Generate one final bill for all unbilled items in a table session.
- Record cash, UPI, card, credit, or supported split payments through backend-calculated totals.

### 4.4 Owner And Partner Goals

- The Final Super Admin can see both ventures and consolidated totals.
- The Cafe Partner Admin sees only Cafe data and Cafe controls.
- Both can identify who placed, accepted, prepared, billed, paid, cancelled, voided, or adjusted a Cafe transaction when permitted.
- Reports reconcile orders, invoices, payments, refunds, and cash differences.

## 5. Guiding Product Decisions

1. One repository and shared React codebase will serve both ventures through an approved Local Hub and cloud gateway deployment profile.
2. The existing `companies` concept will represent venture workspaces such as Retail and Cafe.
3. A lightweight ownership/business-group level will support Final Super Admin consolidation and aggregate turnover monitoring.
4. Normal users belong to exactly one venture for the MVP. The Final Super Admin is the only cross-venture role.
5. Frontend navigation improves usability, but backend scope enforcement is the security boundary.
6. Customer QR ordering and authenticated staff ordering create records in the same Cafe order engine.
7. Cafe billing reuses the existing invoice and payment engine.
8. REST polling is sufficient for the MVP live queue. WebSockets and Redis are deferred.
9. GST product metadata remains available internally, but an unregistered venture issues Non-GST bills with zero applied tax and no GSTIN display.
10. Issued financial records are corrected by reversal or void workflows. Permanent purge is exceptional and controlled.
11. Local PostgreSQL remains the financial and inventory system of record; Supabase is a cloud coordination, queue, and read-model database.
12. Vercel hosts the public portal and limited cloud API; a secure tunnel may expose selected Local Hub APIs but never PostgreSQL.
13. Internet and power recovery must resume automatically from durable queue checkpoints with idempotent processing.

## 6. Product Hierarchy

```text
Business Group / Partnership
|
+-- Retail Venture / Company
|   +-- Retail branch or outlet
|       +-- Retail admins, managers, staff, analysts
|
+-- Cafe Venture / Company
    +-- Cafe branch or outlet
        +-- Cafe Partner Admin
        +-- Cafe Manager
        +-- Order Taker / Cashier
        +-- Kitchen Staff
        +-- Tables and QR customer sessions
```

The hierarchy is intentionally limited. This version is not a general SaaS tenant builder, franchise marketplace, or dynamic legal-entity management platform.

## 7. Users And Roles

### 7.1 Final Super Admin

The Final Super Admin is the owner-level global role.

Can:

- Access Retail, Cafe, and consolidated dashboards.
- Switch between ventures.
- Configure ownership-level settings.
- Create and deactivate Venture Admin accounts.
- View cross-venture audit and reconciliation reports.
- Configure GST activation controls where legally applicable.
- Initiate or approve exceptional void and purge workflows.
- Close or reopen business periods when permitted.
- Export owner-level data and manage backup/restore procedures.

Cannot:

- Silently rewrite issued invoices, stock movements, payments, or ledger entries.
- Bypass database integrity, retention locks, or mandatory audit evidence.

### 7.2 Venture Admin

`Venture Admin` is a company-scoped role. The Cafe partner receives this role for the Cafe venture and may be labeled `Cafe Partner Admin` in the UI.

Can within the assigned venture:

- View all venture branches, sales, orders, bills, payments, inventory, and reports.
- Manage venture staff and operational settings allowed by policy.
- Manage Cafe menu, tables, QR codes, order queue, and billing.
- View venture-specific audit events and daily closings.
- Approve permitted corrections and void requests.

Cannot:

- See the existence, name, URL, counts, or records of another venture through normal application APIs.
- Access the consolidated owner dashboard.
- Change ownership-level identity or global security policy.
- Permanently purge issued financial records without Final Super Admin authorization.
- Activate GST without the required registration configuration and Final Super Admin authorization.

### 7.3 Manager

Can operate the assigned venture and branch, including orders, tables, billing oversight, local inventory, shift reporting, and permitted corrections. Cannot access another branch unless explicitly assigned and cannot access another venture.

### 7.4 Retail Staff

Retains the existing Retail POS and operational permissions for the assigned Retail branch only.

### 7.5 Cafe Order Taker / Cashier

Can:

- Create dine-in and takeaway orders.
- View active orders for the assigned Cafe branch.
- Update allowed service statuses.
- Generate bills and record payments when granted cashier permission.

Cannot:

- View cost/profit reports unless separately allowed.
- Change tax, venture, user, purge, or global configuration.
- Access Retail.

### 7.6 Kitchen Staff

Can view only preparation-relevant order details and update preparation statuses. Cannot see customer ledgers, costs, owner reports, payments, tax settings, or Retail.

### 7.7 Analyst

Read-only reporting role scoped to one venture. A global analyst is not part of the MVP unless explicitly created later by the Final Super Admin.

### 7.8 QR Customer

An unauthenticated guest with short-lived, table-scoped access.

Can:

- View the active Cafe menu for the scanned table's branch.
- Submit an order for that table session.
- View status for the same guest/table session.
- Add items and request a bill while the session is open.

Cannot:

- Browse tables, ventures, internal order lists, customer lists, inventory, reports, or admin APIs.
- Change prices, taxes, discounts, payment status, or order workflow status.
- Access another table session by changing a numeric identifier.

## 8. Portal And Route Experience

### 8.1 Shared Login

- Staff and administrators use one `/login` page.
- The backend returns the authenticated user's role and authorized venture scope.
- The user is redirected directly to the correct portal.
- The Cafe partner does not receive a venture selector.
- Only the Final Super Admin receives an `All Ventures`, `Retail`, and `Cafe` selector.

### 8.2 Portal Routes

```text
/login                  Shared authenticated login
/super-admin            Final Super Admin dashboard
/retail                 Retail venture portal
/cafe                   Cafe venture portal
/cafe/orders            Cafe live order queue
/cafe/pos               Staff order entry and billing
/cafe/tables             Cafe table and QR management
/cafe/menu               Cafe menu management
/order/{qr_token}        Public mobile customer ordering
```

Route visibility must not be treated as authorization. Direct API and URL attempts outside the authenticated scope must return a non-disclosing `403` or `404` response according to the technical contract.

## 9. Core User Journeys

### 9.1 Cafe Partner Login

1. Cafe partner opens the shared login page.
2. Partner enters the Cafe Venture Admin credentials.
3. Backend validates the account and current venture assignment.
4. Frontend redirects to `/cafe/dashboard`.
5. Navigation contains Cafe pages only.
6. Dashboard queries are restricted to the Cafe venture by the backend.
7. Attempts to access Retail routes, APIs, exports, AI tools, or object IDs are denied.

### 9.2 Customer QR Order

1. Staff places a unique QR code on a Cafe table.
2. Customer scans the QR and opens `/order/{qr_token}`.
3. Backend resolves the opaque token to the active Cafe venture, branch, and table.
4. Customer sees the active menu, availability, and customer-facing prices.
5. Customer adds items and submits the order.
6. Backend recalculates price and validates availability.
7. Order enters the live queue as `placed` with source `qr_customer`.
8. Order taker accepts or rejects it.
9. Customer sees the resulting status without seeing internal data.
10. Accepted items proceed through preparation and service.

### 9.3 Staff Direct Table Order

1. Order taker logs in to the Cafe portal.
2. Staff selects a table with an open session.
3. Staff adds menu items and notes.
4. Backend validates menu state and calculates totals.
5. Order enters the same queue with source `order_taker` or `billing_counter`.
6. Items from customer and staff orders remain traceable but belong to one table session.

### 9.4 Takeaway Or Counter Order

1. Staff selects `Takeaway` instead of a table.
2. Staff adds items and optionally customer details.
3. The order can move directly to accepted/preparing or immediate billing according to permission.
4. The invoice and payment use the same backend billing engine.

### 9.5 Add Items To Existing Table

1. Customer or staff adds a second order under the open table session.
2. The system creates new order items rather than rewriting previously accepted items.
3. Previously billed items cannot be billed again.
4. The final bill includes all eligible unbilled items for the session.

### 9.6 Bill And Close Table

1. Customer requests the bill or staff starts billing.
2. Cashier reviews all unbilled, accepted Cafe order items.
3. Backend creates one invoice linked to the Cafe table session and included orders/items.
4. Backend calculates final totals and payment status.
5. Invoice issue performs the configured stock effect exactly once.
6. Payment is recorded through the existing payment engine.
7. Session becomes `billed` and then `closed` after settlement.
8. Table becomes available for a new session.

### 9.7 Final Super Admin Consolidated Review

1. Final Super Admin opens `/super-admin`.
2. Selects `All Ventures`, `Retail`, or `Cafe`.
3. Reviews separately defined metrics for orders, billed sales, collections, outstanding amounts, refunds, and cash variance.
4. Drills into a venture without losing the ownership-level context.
5. Export and AI results use the same selected scope.

## 10. Functional Requirements

### 10.1 Venture Isolation

- `MV-FR-001`: Every authenticated non-global user must be assigned to exactly one venture/company.
- `MV-FR-002`: Every branch must belong to exactly one venture.
- `MV-FR-003`: All operational and reporting data must be scoped by venture and, where relevant, branch.
- `MV-FR-004`: The backend must reject cross-venture reads and writes even when a valid record ID is supplied.
- `MV-FR-005`: Exports, dashboards, AI tools, search, counts, autocomplete, error messages, and audit views must apply the same scope.
- `MV-FR-006`: The Cafe partner must never receive Retail navigation or a venture selector.
- `MV-FR-007`: The Final Super Admin must be able to select one venture or all ventures.
- `MV-FR-008`: Cross-venture consolidated values must be available only to the Final Super Admin.

### 10.2 Cafe Menu

- `MV-FR-010`: Cafe admins must manage menu categories and menu items.
- `MV-FR-011`: A menu item must include name, description, selling price, active state, availability state, preparation area, and optional image.
- `MV-FR-012`: A menu item may link to an existing venture-scoped product for billing and sellable-item stock tracking.
- `MV-FR-013`: Customer-facing prices must come from the backend.
- `MV-FR-014`: Inactive or unavailable menu items must not be orderable.
- `MV-FR-015`: Menu management must be restricted to authorized Cafe users.

### 10.3 Tables And QR Codes

- `MV-FR-020`: Cafe admins must create tables with a unique name/number within a branch.
- `MV-FR-021`: Each active table must have a cryptographically unpredictable QR token.
- `MV-FR-022`: QR tokens must be revocable and rotatable.
- `MV-FR-023`: A QR token must resolve to exactly one active venture, branch, and table.
- `MV-FR-024`: Public APIs must not accept a user-supplied venture or branch ID as authority.
- `MV-FR-025`: Disabled tables or revoked QR tokens must not accept new orders.
- `MV-FR-026`: Printable QR output must contain the customer route and human-readable table identity.

### 10.4 Table Sessions

- `MV-FR-030`: A table may have at most one active billable session at a time.
- `MV-FR-031`: A session must track open, bill requested, billed, closed, and cancelled states.
- `MV-FR-032`: Multiple QR and staff orders may belong to one table session.
- `MV-FR-033`: Closing a session must release the table.
- `MV-FR-034`: A closed session cannot accept new items.
- `MV-FR-035`: Reopening a closed session requires an authorized, audited correction workflow.

### 10.5 Customer QR Ordering

- `MV-FR-040`: Customer ordering must work in a mobile browser without account creation.
- `MV-FR-041`: Customer access must be limited to the resolved table session and public menu data.
- `MV-FR-042`: Backend must recalculate every order total and reject client-supplied price changes.
- `MV-FR-043`: Duplicate submissions must be prevented through idempotency controls.
- `MV-FR-044`: Customers must be able to view status for their current session.
- `MV-FR-045`: Customers may request a bill but cannot mark it paid.
- `MV-FR-046`: Customer notes must be length-limited and treated as untrusted text.
- `MV-FR-047`: Public order creation must be rate-limited.

### 10.6 Staff Order Entry

- `MV-FR-050`: Authorized staff must create dine-in and takeaway orders.
- `MV-FR-051`: Staff must be able to select an existing open table session or create one when allowed.
- `MV-FR-052`: Staff-created and QR-created orders must appear in one queue.
- `MV-FR-053`: Each order and item must retain its source channel and creator where available.
- `MV-FR-054`: Staff must not change a final billed item's quantity or price directly.
- `MV-FR-055`: Discounts must require an allowed role and be calculated by the backend.

### 10.7 Order Operations

- `MV-FR-060`: Required order states are `placed`, `accepted`, `preparing`, `ready`, `served`, `bill_requested`, `billed`, `closed`, `rejected`, and `cancelled` where applicable.
- `MV-FR-061`: Invalid state transitions must be rejected by the backend.
- `MV-FR-062`: Status history must record actor, old state, new state, time, and reason where required.
- `MV-FR-063`: Customer orders require staff acceptance before they become preparation commitments.
- `MV-FR-064`: Rejected and cancelled items must remain visible in audit and reconciliation views.
- `MV-FR-065`: Live views may use polling every 5 to 10 seconds for the MVP.

### 10.8 Cafe Billing And Payments

- `MV-FR-070`: Cafe billing must use the existing invoice engine rather than a second billing implementation.
- `MV-FR-071`: An invoice must identify its venture, branch, source type, and source Cafe session/order.
- `MV-FR-072`: A table bill must include eligible unbilled items exactly once.
- `MV-FR-073`: Backend is the source of truth for subtotal, discounts, taxes, round-off, grand total, paid amount, and balance.
- `MV-FR-074`: Supported payment modes come from venture settings.
- `MV-FR-075`: Cashier may record split payment only when the payment total passes backend validation.
- `MV-FR-076`: Issuing the bill, creating the analytics-compatible sale, applying stock effects, and recording initial payments must be transactional.
- `MV-FR-077`: Retrying a completed bill request must not create a second invoice.
- `MV-FR-078`: A bill cannot be closed as paid unless recorded non-credit payments cover the required amount.

### 10.9 Inventory Behavior

- `MV-FR-080`: Cafe menu items may link to venture-scoped products.
- `MV-FR-081`: For the MVP, linked sellable-item stock is reduced once when the invoice is issued.
- `MV-FR-082`: QR order placement alone does not reduce stock.
- `MV-FR-083`: Every Cafe stock change must create a stock movement.
- `MV-FR-084`: An invoice or order retry must never reduce stock twice.
- `MV-FR-085`: Recipe-level ingredient consumption is outside the MVP and must not be simulated inaccurately.

### 10.10 GST-Ready, Non-GST-Default Operation

- `MV-FR-090`: Each venture must have an explicit tax operation mode.
- `MV-FR-091`: The initial Cafe and Retail operating mode may be `non_gst` while no valid registration is configured.
- `MV-FR-092`: In Non-GST mode, customer bills must have zero applied GST, no GST tax rows used for GST reporting, and no GSTIN displayed.
- `MV-FR-093`: Product HSN/SAC and reference GST rates may remain stored internally for catalog, costing, and future readiness.
- `MV-FR-094`: Internal reference GST metadata must not be added to a customer's payable amount in Non-GST mode.
- `MV-FR-095`: GST invoice mode must be blocked unless an active GST registration, state, effective date, and invoice sequence are configured.
- `MV-FR-096`: GST activation must be effective-dated and must not convert historical Non-GST bills.
- `MV-FR-097`: Customer GST/B2B fields must be hidden from bills and GST reports unless the venture and customer are explicitly enabled for that workflow.
- `MV-FR-098`: The Final Super Admin must see combined turnover across ventures belonging to the same ownership/legal group for monitoring purposes.
- `MV-FR-099`: The software must show a compliance disclaimer and require CA/GST expert review before production GST filing or live portal integration.

### 10.11 Dashboards And Reconciliation

- `MV-FR-100`: Cafe dashboard must show order count, ordered value, billed revenue, collections, unpaid amount, average bill value, cancellations, refunds, and table turnover.
- `MV-FR-101`: Ordered value and billed revenue must be distinct metrics.
- `MV-FR-102`: Billed revenue and cash collected must be distinct metrics.
- `MV-FR-103`: Daily reconciliation must separate Cash, UPI, Card, Bank, Credit, Refunds, Expenses, expected cash, counted cash, and variance where those modules exist.
- `MV-FR-104`: The Cafe Partner Admin sees Cafe values only.
- `MV-FR-105`: The Final Super Admin sees Retail, Cafe, and consolidated views with a visible scope label.
- `MV-FR-106`: Dashboard values must come from database-backed services and must not be hardcoded.
- `MV-FR-107`: Exports and Power BI views must include venture identifiers for Final Super Admin reporting but must filter them for venture-scoped users.

### 10.12 AI Assistant

- `MV-FR-110`: AI tools must receive the authenticated venture scope from backend context.
- `MV-FR-111`: The Cafe partner's AI assistant must answer only from Cafe data.
- `MV-FR-112`: AI must not reveal Retail existence, counts, names, or values to a Cafe-scoped account.
- `MV-FR-113`: AI numerical answers must use database-backed tools.
- `MV-FR-114`: AI write suggestions require confirmation and normal backend permission checks.
- `MV-FR-115`: Public QR customers do not receive access to the internal AI assistant.

### 10.13 Correction, Void, And Deletion

- `MV-FR-120`: Unissued drafts with no downstream effects may be deleted by an authorized user and must still generate an audit event.
- `MV-FR-121`: Issued invoices, payments, stock movements, and ledger entries must not be silently edited or directly deleted.
- `MV-FR-122`: Normal financial corrections must use void, refund, return, credit note, or compensating ledger/stock entries.
- `MV-FR-123`: Final Super Admin may initiate exceptional permanent purge only through a controlled workflow.
- `MV-FR-124`: Purge requires re-authentication, reason, dependency analysis, a verified backup, confirmation, period/retention checks, and an immutable tombstone.
- `MV-FR-125`: A configured second approval may be required for Cafe financial purges.
- `MV-FR-126`: The purge permission does not permit bypassing legal retention rules, locked periods, database integrity, or audit evidence.
- `MV-FR-127`: Master data such as products, customers, tables, and users should normally be deactivated or anonymized rather than deleted.
- `MV-FR-128`: Development demo reset is a separate environment-gated operation and must not be available in production.

## 11. Customer Experience Requirements

- Mobile-first layout with no horizontal scrolling at common phone widths.
- Initial menu content should load quickly on a local network or secure tunnel.
- Menu categories and search must remain easy to scan.
- Cart and total must remain visible without covering menu controls.
- Clear feedback for unavailable item, expired session, rejected order, and duplicate submission.
- No mandatory account, app installation, or marketing page before ordering.
- Customer must always see the Cafe name, table identity, order status, and current bill-request state.
- Customer-facing pages must not expose cost, stock quantity, GST setup, internal notes, employee identity, or other sessions.

## 12. Admin And Partner Experience Requirements

- Every authenticated page must show the active venture and branch scope.
- Cafe partner navigation must contain only Cafe modules.
- Final Super Admin venture switching must be explicit and persistent only for the current session.
- Destructive and financial actions must use clear confirmation dialogs and reasons.
- Live order queue must prioritize status, age, table, source, and preparation notes.
- Billing must make unbilled versus already billed items unmistakable.
- Reports must label gross sales, discounts, refunds, net billed sales, collections, and outstanding values separately.

## 13. Non-Functional Requirements

### 13.1 Security

- Authoritative financial and inventory data remains local, and neither local nor Supabase database ports are exposed to browsers.
- Remote access uses the Vercel cloud gateway and selected authenticated Local Hub APIs through HTTPS or a private network tunnel.
- Backend performs role, venture, branch, object, and action checks for every protected operation.
- Public QR endpoints use opaque tokens, short-lived guest access, input validation, rate limiting, and idempotency.
- Sensitive actions require step-up authentication.
- Secrets, QR token material, password hashes, and payment references must not appear in logs or client error messages.
- Cross-venture negative tests are release-blocking.

### 13.2 Reliability And Integrity

- Invoice, stock, payment, and ledger changes are transactional.
- Duplicate customer taps, browser retries, and network retries are idempotent.
- Status transitions use optimistic locking or equivalent concurrency protection.
- Backup and restore must be verified before enabling exceptional purge.
- Audit and status histories are append-only through normal application flows.

### 13.3 Performance

- Common dashboard and order-list APIs should target under 2 seconds on the supported local deployment and seeded data volume.
- Public menu should target under 2 seconds after network connection is established.
- Order submission should target under 3 seconds and return a durable order reference.
- Required query columns must be indexed by venture, branch, status, and business date.

### 13.4 Usability

- POS and order-taker screens must support tablet and desktop use.
- QR ordering must support current Android and iOS browsers.
- All totals and status changes must have clear loading, success, error, and retry states.
- The product remains an operational interface, not a marketing-style website.

### 13.5 Cost

- Local PostgreSQL remains the operational system of record.
- Supabase is approved as the cloud coordination database; development may use a free tier, while production must follow provider commercial terms and reliability requirements.
- Redis, a separate message broker, and hosted BI are not required for the MVP because durable PostgreSQL queues are used.
- REST polling is used before introducing real-time infrastructure.

## 14. Reporting Definitions

To avoid disputes between partners, these values must never be presented as synonyms:

- Ordered value: current value of submitted order items, including unbilled items.
- Billed revenue: value of issued invoices before returns, according to the selected reporting basis.
- Net billed revenue: billed revenue less approved returns, refunds, and credit notes.
- Collections: non-credit payments actually recorded.
- Outstanding: issued invoice balance not yet collected.
- Cash expected: cash collections less cash refunds and approved cash expenses for the shift/day.
- Cash variance: counted closing cash minus expected closing cash.
- Cancelled value: value removed through approved cancellation before billing.
- Void value: value reversed from previously issued transactions.

Every report must state its date range, active venture scope, branch scope, and whether cancelled/voided/refunded records are included.

## 15. MVP Scope

The multi-venture Cafe MVP includes:

1. Ownership group with Retail and Cafe venture workspaces.
2. Final Super Admin and Cafe Partner Admin isolation.
3. Venture and branch scope enforced across existing APIs.
4. Separate Retail, Cafe, and Final Super Admin portal shells.
5. Cafe menu and menu availability.
6. Cafe tables and secure QR token management.
7. Customer mobile QR ordering without login.
8. Staff dine-in and takeaway order entry.
9. Unified order queue and controlled status transitions.
10. Table sessions with multiple orders and one bill workflow.
11. Cafe billing and payment through the existing invoice engine.
12. GST-ready, Non-GST-default behavior.
13. Cafe and consolidated owner dashboards.
14. Audit, daily reconciliation, void, and controlled purge workflow.
15. Automated isolation, transaction, and end-to-end tests.
16. Vercel cloud gateway, Supabase coordination schema, and Local Hub synchronization worker.
17. Automatic restart, queue resume, retry, reconciliation, and visible synchronization health.

## 16. Deferred Scope

The following are intentionally deferred until the MVP is stable:

- Recipe-level ingredient inventory and automatic raw-material consumption.
- Kitchen printers and hardware-specific printer agents.
- WebSockets, Redis, and distributed event infrastructure.
- Online payment gateway and customer self-payment.
- Delivery fleet, aggregator, or marketplace integration.
- Customer loyalty, coupons, subscriptions, and marketing automation.
- Native Android or iOS applications.
- Dynamic custom-role builder and many-to-many venture memberships.
- Franchise/SaaS onboarding for unrelated businesses.
- Multiple unrelated legal entities under one deployment.
- Live GST portal, e-invoice, or e-way bill submission.
- Full general ledger or statutory accounting replacement.

## 17. Dependencies

- Existing authentication and role framework.
- Existing `companies`, branches, users, products, inventory, invoices, payments, and audit models.
- Existing POS/invoice backend and frontend.
- Current migrations and seed data must remain upgradeable.
- Tax activation depends on valid business/GST settings and professional compliance review.
- Consolidated dashboards depend on complete venture scoping across transactional data.
- Exceptional purge depends on backup verification, period locking, and append-only audit support.

## 18. Success Metrics

- Zero successful cross-venture access attempts in automated authorization tests.
- Cafe partner can complete all Cafe management tasks without seeing Retail UI or data.
- A customer can scan, order, and receive confirmation in under two minutes during a normal demo.
- A staff member can directly create and bill a table or takeaway order.
- A mixed QR plus staff table session creates exactly one correct bill with no duplicated item.
- Order, invoice, payment, stock, and dashboard totals reconcile for the same date and scope.
- Non-GST bills contain no applied GST or GSTIN while internal product tax references remain available.
- Every financial correction and exceptional purge attempt produces an audit record.

## 19. Release Acceptance Scenarios

### Scenario A: Cafe Partner Isolation

1. Login as Cafe Partner Admin.
2. Confirm redirect to `/cafe/dashboard`.
3. Confirm only Cafe navigation is visible.
4. Request known Retail API objects by ID.
5. Confirm no Retail data or identifying metadata is returned.
6. Export and ask AI questions; confirm results contain Cafe data only.

### Scenario B: QR And Staff Combined Order

1. Open a Cafe table session.
2. Scan its QR and submit two items.
3. Add another item from the authenticated staff portal.
4. Accept, prepare, and serve the orders.
5. Generate one bill from the table session.
6. Confirm all eligible items appear exactly once.
7. Record payment and close the table.
8. Confirm dashboard and audit results.

### Scenario C: Direct Takeaway Billing

1. Login as order taker/cashier.
2. Create a takeaway order without a table.
3. Add menu items and complete payment.
4. Confirm invoice creation, status history, stock effect, and reporting.

### Scenario D: Non-GST Operation

1. Set the Cafe venture to Non-GST with no active GST registration.
2. Create and print a Cafe bill.
3. Confirm GST amount is zero and GSTIN/customer GST section is absent.
4. Confirm product HSN/reference rate remains available only in permitted internal screens.
5. Attempt a GST invoice and confirm the backend blocks it.

### Scenario E: Future GST Activation

1. Configure valid registration fields, state, effective date, and sequence in a test environment.
2. Activate GST with Final Super Admin permission.
3. Confirm eligible new invoices use the configured tax logic.
4. Confirm older Non-GST invoices are unchanged.

### Scenario F: Correction And Purge Controls

1. Attempt to directly delete an issued invoice as Cafe Partner Admin and confirm denial.
2. Void it through the authorized reversal flow and confirm stock/payment/ledger effects reconcile.
3. Initiate exceptional purge as Final Super Admin.
4. Confirm re-authentication, reason, backup, period, dependency, and approval checks.
5. Confirm an immutable tombstone remains after an allowed purge.

## 20. Definition Of Done

The expansion is complete only when:

- Existing Retail workflows continue to pass regression tests.
- Retail and Cafe data are fully venture-scoped.
- Cafe partner access is demonstrably isolated at API and UI levels.
- Customer QR and staff-entered orders share one Cafe order engine.
- Table sessions consolidate orders into one correct, idempotent bill.
- Existing invoice, payment, stock movement, sales analytics, and audit services are reused safely.
- Non-GST mode is the active default and cannot accidentally apply or display GST.
- Future GST activation is controlled, effective-dated, and non-retroactive.
- Cafe and consolidated dashboards reconcile against invoices and payments.
- Void and exceptional purge workflows meet the audit and backup requirements.
- Backend tests, frontend checks, migration checks, and browser workflows pass.
- Documentation and demo credentials match the implemented behavior.

## 21. Compliance Disclaimer

This portfolio system provides operational GST readiness, not legal, tax, accounting, or filing advice. Registration obligations and invoice requirements depend on current law, supply type, location, legal entity, aggregate PAN-based turnover, and other facts. Before production use, a qualified CA/GST professional must validate the configured tax mode, invoice format, retention policy, registration status, and reporting process.

Official reference starting points:

- CBIC invoice rules: https://cbic-gst.gov.in/gst-invoice-rules.html
- CBIC GST FAQs: https://cbic-gst.gov.in/faq.html
- CBIC registration FAQs: https://cbic-gst.gov.in/pdf/faq-manual/faqs-registration.pdf
