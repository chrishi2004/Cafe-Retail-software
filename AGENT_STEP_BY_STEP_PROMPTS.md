# Agent Step-By-Step Build Prompts

## Project

AI-Powered Hybrid Retail Inventory, Sales Analytics, and Remote Order Management System

## Purpose

This document gives copy-paste prompts for building the project in executable parts. Each prompt is designed for an AI coding agent. The prompts are based on:

- `PRD.md`
- `EXECUTION_FLOW_ANALYSIS.md`

Use these prompts in order. Do not jump to later parts before earlier parts are complete, because inventory, sales, dashboards, forecasting, AI, and Power BI all depend on a reliable local database and clean business flows.

## How To Use These Prompts

1. Open a fresh agent session or continue the same coding agent thread.
2. Give the agent the "Global Build Context Prompt" first.
3. Then give Part 0.
4. Let the agent implement, test, and report changed files.
5. Review the result.
6. Then give the next part.

Recommended rule:

Do not move to the next part until the previous part passes its acceptance checks.

## Global Build Context Prompt

Use this before starting the build and repeat it when starting a new agent session.

```text
You are building a full-stack portfolio project named "AI-Powered Hybrid Retail Inventory, Sales Analytics, and Remote Order Management System".

Before making changes, read these project documents:
- PRD.md
- EXECUTION_FLOW_ANALYSIS.md
- AGENT_STEP_BY_STEP_PROMPTS.md

Treat PRD.md as the product contract.
Treat EXECUTION_FLOW_ANALYSIS.md as the build strategy.
Treat this prompt file as the step-by-step execution guide.

Core architecture:
- Hybrid local-first system.
- Main business database must be local.
- Do not design the default system around a paid cloud database.
- Remote admin access must go through the web app/API, not direct database exposure.
- Database must only be accessed through backend APIs.

Recommended stack unless the repo already has another stack:
- Backend: FastAPI with Python
- Database: local PostgreSQL
- ORM: SQLAlchemy
- Migrations: Alembic
- Frontend: React with TypeScript
- Charts: Recharts or ECharts
- Styling: Tailwind CSS or a clean component system
- Forecasting: Python service using simple moving average/trend first
- AI assistant: backend tool layer first; OpenAI API optional and configurable
- BI: Power BI Desktop connected to local SQL views or exported CSV files
- Remote access: Cloudflare Tunnel, Tailscale, or ngrok documentation

Important business rules:
- Sales must reduce inventory.
- Purchase order creation must not increase available inventory.
- Purchase order receiving must increase inventory.
- Every stock change must create a stock movement record.
- Reorder recommendations must use current stock, target stock, sales velocity, and supplier lead time.
- AI must not invent business numbers.
- AI must use backend data retrieval tools for numerical answers.
- AI must ask confirmation before write actions.
- Role-based access must be enforced in the backend, not only in the frontend.

Implementation behavior:
- Work in small, complete vertical slices.
- Preserve existing code and docs unless a change is necessary.
- Keep code modular and readable.
- Add tests where practical, especially for business rules.
- Do not hardcode dashboard KPI values in the frontend.
- Use realistic seed data so dashboards are meaningful.
- Update documentation as the implementation evolves.
- At the end of each part, summarize changed files, completed requirements, how to run/test, and any known gaps.
```

## Part 0 Prompt: Repository Setup And Technical Foundation

```text
Read PRD.md and EXECUTION_FLOW_ANALYSIS.md first.

Build Part 0: Project setup and technical foundation.

Goal:
Create the initial full-stack project structure so the backend, frontend, and local database setup can run locally.

Use the recommended stack unless a stack already exists:
- Backend: FastAPI, Python
- Frontend: React, TypeScript
- Database: local PostgreSQL
- ORM: SQLAlchemy
- Migrations: Alembic
- Styling: Tailwind CSS or equivalent clean UI setup

Tasks:
1. Inspect the repository structure.
2. Create a clean project structure for backend, frontend, docs, scripts, and optional Power BI/reporting assets.
3. Add backend app with a health endpoint.
4. Add frontend app with a basic shell page.
5. Add environment variable templates.
6. Add local database connection configuration.
7. Add package/dependency files.
8. Add basic run instructions to README.md.
9. Add .gitignore for Python, Node, environment files, build outputs, and local database artifacts.
10. Do not implement business features yet.

Expected structure:
- backend/
- frontend/
- docs/ or keep current planning docs in root
- scripts/
- reports/ or powerbi/
- README.md
- .env.example

Backend must include:
- GET /health returning a simple healthy response.
- App startup without database errors when configured correctly.

Frontend must include:
- A working development server.
- A basic landing/dashboard placeholder, not a marketing page.

Acceptance checks:
- Backend can start.
- Frontend can start.
- Health endpoint works.
- README explains how to install and run backend/frontend.
- .env.example documents required variables.

Report back:
- Files created or changed.
- Commands to run backend.
- Commands to run frontend.
- Any setup assumptions.
```

## Part 1 Prompt: Database Schema And Migrations

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, and the current codebase.

Build Part 1: Database schema and migrations.

Goal:
Create the local SQL database foundation for the entire business system.

Use PostgreSQL locally unless the project has already chosen another SQL database.

Required tables/entities:
1. users
2. branches
3. categories
4. suppliers
5. products
6. inventory
7. stock_movements
8. sales
9. sale_items
10. purchase_orders
11. purchase_order_items
12. forecasts
13. ai_chat_sessions
14. ai_chat_messages
15. audit_logs

Tasks:
1. Add SQLAlchemy models for all required entities.
2. Add Alembic migration setup if not present.
3. Create the initial migration.
4. Add constraints:
   - product SKU must be unique.
   - user email must be unique.
   - inventory should be unique per product and branch.
   - purchase order status should use controlled values.
   - stock movement type should use controlled values.
5. Add timestamps where appropriate.
6. Add foreign key relationships.
7. Add indexes for dashboard-heavy fields:
   - sale date
   - branch id
   - product id
   - category id
   - supplier id
   - purchase order status
8. Add database session utilities.

Important business requirements:
- Inventory must be tracked by product and branch.
- Sales must support multiple sale items.
- Purchase orders must support multiple line items.
- Forecasts must support product/category/branch level records.
- Audit logs must be able to track important actions.

Acceptance checks:
- Migrations run cleanly on a local database.
- All required tables are created.
- Relationships are valid.
- Backend can connect to the database.
- No paid cloud database is required.

Report back:
- Model files changed.
- Migration files created.
- Database setup commands.
- Any schema decisions made.
```

## Part 2 Prompt: Realistic Seed Data

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, and the existing schema.

Build Part 2: Seed data.

Goal:
Create realistic retail sample data so dashboards, forecasts, AI answers, and Power BI reports are meaningful.

Seed data requirements:
- 2 to 3 branches.
- 5 to 8 categories.
- 8 to 15 suppliers.
- 50 to 100 products.
- Inventory records for all products across branches.
- 6 to 12 months of sales history.
- 20 to 50 purchase orders.
- Some low-stock products.
- Some slow-moving products.
- Some fast-moving/high-demand products.
- Users for admin, store manager, staff, and analyst roles.

Tasks:
1. Create a repeatable seed script.
2. Make seed script safe to run on a clean development database.
3. Add realistic product categories such as Grocery, Beverages, Dairy, Snacks, Personal Care, Household, and Stationery.
4. Create suppliers with lead times and contact data.
5. Create products with unit cost, selling price, reorder threshold, target stock level, supplier, and category.
6. Create inventory quantities that intentionally include:
   - healthy stock
   - low stock
   - zero stock
   - quantity on order
7. Generate historical sales with realistic seasonal or weekly patterns.
8. Generate purchase orders in multiple statuses.
9. Hash user passwords securely.
10. Document default demo credentials in README.md or a development-only docs file.

Important:
- Do not hardcode dashboard metrics in frontend.
- The seed data should allow dashboards to calculate real values.
- The seed data should allow forecasting to run.
- The seed data should allow AI assistant data tools to return meaningful answers.

Acceptance checks:
- Seed script runs successfully.
- Database has sample users, products, inventory, sales, and purchase orders.
- At least a few products are low-stock.
- At least a few products are slow-moving.
- At least a few products are top sellers.
- Sales history covers enough time for forecasting.

Report back:
- Seed files changed.
- How to run seed script.
- Demo credentials.
- Summary of generated sample data.
```

## Part 3 Prompt: Backend Auth, RBAC, And Audit Foundation

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, and existing backend code.

Build Part 3: Backend authentication, role-based access control, and audit foundation.

Goal:
Secure the backend API and prepare role-aware access for all future modules.

Required roles:
- Admin
- Store Manager
- Staff
- Analyst

Permission rules:
- Admin can access all branches and all features.
- Store Manager can access assigned branch operational data.
- Staff can add sales and perform limited data entry.
- Analyst can view dashboards/reports but cannot modify operational records.

Tasks:
1. Implement password hashing and verification.
2. Implement login endpoint.
3. Implement logout endpoint or token/session invalidation strategy if applicable.
4. Implement current user endpoint.
5. Implement backend dependency/utilities for authenticated users.
6. Implement backend dependency/utilities for role checks.
7. Implement branch-scope helper for Store Manager and Staff users.
8. Add audit logging utility.
9. Audit important auth actions such as login success/failure where practical.
10. Add structured error responses for unauthorized and forbidden requests.
11. Add tests for login and role restrictions.

Required endpoints:
- POST /auth/login
- POST /auth/logout
- GET /auth/me
- GET /health

Security requirements:
- Passwords must be hashed.
- Do not expose password hashes in API responses.
- Backend must enforce permissions.
- Frontend-only role hiding is not enough.

Acceptance checks:
- Valid user can log in.
- Invalid login fails clearly.
- GET /auth/me returns current user without password hash.
- Protected endpoint rejects unauthenticated user.
- Admin role check works.
- Non-admin cannot access admin-only test route or protected operation.
- Audit log utility can write records.

Report back:
- Auth files changed.
- How tokens/sessions work.
- Test commands.
- Known limitations.
```

## Part 4 Prompt: Frontend App Shell, Login, And Navigation

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, and the existing frontend/backend code.

Build Part 4: Frontend authenticated app shell.

Goal:
Create the user-facing dashboard shell that will hold all business modules.

Design direction:
- This is an operational business dashboard, not a landing page.
- Use restrained, professional UI.
- Prioritize scanability, tables, filters, cards, and charts.
- Do not add marketing hero sections.

Tasks:
1. Build login page connected to backend auth.
2. Store auth token/session safely according to the chosen auth strategy.
3. Fetch current user after login.
4. Build protected route handling.
5. Build authenticated layout:
   - sidebar navigation
   - top bar with user name/role
   - main content area
6. Make navigation role-aware.
7. Add placeholder pages for:
   - Overview
   - Sales Summary
   - Inventory
   - Low Stock and Reorder
   - Purchase Orders
   - Suppliers
   - Forecasting
   - AI Assistant
   - Power BI Reports
   - Settings
8. Add reusable UI components:
   - metric card
   - data table shell
   - filter bar
   - loading state
   - empty state
   - error state
9. Ensure responsive behavior for desktop and tablet.

Acceptance checks:
- User can log in through UI.
- Invalid login shows an error.
- Authenticated user sees dashboard shell.
- Role-aware navigation works.
- Logout works if implemented.
- Protected pages are not visible to unauthenticated users.

Report back:
- Frontend files changed.
- How to log in with demo credentials.
- Screens/pages implemented.
- Any design or library choices.
```

## Part 5 Prompt: Master Data Management

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, and the current app.

Build Part 5: Master data management for products, categories, suppliers, and branches.

Goal:
Allow admins to manage core reference data without editing the database directly.

Backend scope:
1. Product APIs:
   - GET /products
   - POST /products
   - GET /products/{id}
   - PUT /products/{id}
   - PATCH /products/{id}/deactivate
2. Category APIs:
   - GET /categories
   - POST /categories
   - PUT /categories/{id}
3. Supplier APIs:
   - GET /suppliers
   - POST /suppliers
   - GET /suppliers/{id}
   - PUT /suppliers/{id}
4. Branch APIs:
   - GET /branches
   - POST /branches
   - PUT /branches/{id}

Frontend scope:
1. Product list with search/filter.
2. Product create/edit form.
3. Supplier list with search/filter.
4. Supplier create/edit form.
5. Category management, simple page or settings section.
6. Branch management, admin-only.

Product fields:
- SKU
- name
- description
- category
- supplier
- unit cost
- selling price
- reorder threshold
- target stock level
- active status

Supplier fields:
- name
- contact person
- email
- phone
- address
- payment terms
- lead time days
- active status

Business rules:
- SKU must be unique.
- Inactive products should not appear by default in new sales selection.
- Products must link to categories and suppliers.
- Only Admin should create/update master data unless explicitly permitted.

Acceptance checks:
- Admin can create and edit products.
- Admin can create and edit suppliers.
- Product SKU uniqueness is enforced.
- Products display category and supplier names.
- Non-admin users cannot perform admin-only changes.
- UI handles loading, errors, and empty states.

Report back:
- APIs implemented.
- UI pages implemented.
- Permission behavior.
- Tests or manual checks completed.
```

## Part 6 Prompt: Inventory Engine And Stock Movement Ledger

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, and current code.

Build Part 6: Inventory engine and stock movement ledger.

Goal:
Make stock tracking reliable and auditable.

Core rule:
Inventory must never change silently. Every stock change must create a stock movement record.

Backend APIs:
- GET /inventory
- GET /inventory/{product_id}
- GET /inventory/low-stock
- POST /inventory/adjustments
- GET /inventory/movements

Backend tasks:
1. Build inventory query service with filters:
   - branch
   - category
   - supplier
   - product search
   - low-stock status
2. Build low-stock detection:
   - quantity_on_hand <= reorder_threshold
3. Build manual stock adjustment:
   - validate product and branch
   - require adjustment reason
   - update inventory
   - create stock_movement
   - audit log the action
4. Build stock movement list query.
5. Enforce role permissions:
   - Admin can view and adjust all stock.
   - Store Manager can view/adjust assigned branch if allowed.
   - Staff has limited access if configured.
   - Analyst is read-only.

Frontend tasks:
1. Inventory table with product, branch, category, supplier, quantity, reorder threshold, target stock, stock value, and low-stock status.
2. Filters for branch/category/supplier/low-stock/search.
3. Product stock detail view or drawer.
4. Manual stock adjustment modal for authorized users.
5. Stock movement history view.

Acceptance checks:
- Inventory list shows real database values.
- Low-stock filter works.
- Manual adjustment changes inventory.
- Manual adjustment creates stock movement.
- Manual adjustment creates audit log.
- Read-only users cannot adjust stock.
- Stock value is calculated correctly.

Report back:
- Inventory services/APIs changed.
- UI pages/components changed.
- Business rules enforced.
- Test/manual verification results.
```

## Part 7 Prompt: Sales Engine With Inventory Updates

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, and current code.

Build Part 7: Sales engine.

Goal:
Allow staff or managers to record sales, and ensure sales reduce inventory correctly.

Backend APIs:
- GET /sales
- POST /sales
- GET /sales/{id}
- GET /sales/summary
- GET /sales/trends

Backend tasks:
1. Implement sale creation with multiple sale items.
2. Validate branch and products.
3. Validate quantity.
4. Validate stock availability unless the system explicitly allows negative inventory.
5. Calculate subtotal, discounts, tax, total amount, gross profit, and related values server-side.
6. Reduce inventory quantity_on_hand after sale.
7. Create stock_movement records with movement_type = sale.
8. Audit sale creation.
9. Add transaction handling so sale creation and inventory update succeed or fail together.
10. Add sales summary and trend query services.

Frontend tasks:
1. Add sale entry form.
2. Allow adding multiple products to a sale.
3. Show calculated totals.
4. Submit sale to backend.
5. Show sales list.
6. Show sale detail.
7. Show basic sales summary page.

Business rules:
- Backend is source of truth for totals.
- Sales reduce stock.
- Sales must create stock movement records.
- Sale creation should be atomic.

Acceptance checks:
- Staff can create a sale.
- Sale with multiple items is saved correctly.
- Inventory decreases for sold products.
- Stock movement records are created.
- Sale totals are correct.
- Insufficient stock is handled clearly.
- Sales summary endpoint returns revenue, units sold, gross profit, and average order value.

Report back:
- Sales APIs implemented.
- UI screens implemented.
- Inventory update behavior verified.
- Tests/manual checks completed.
```

## Part 8 Prompt: KPI Services And Core Dashboards

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, and current code.

Build Part 8: KPI services and core dashboards.

Goal:
Create business dashboards from real backend calculations.

Backend APIs:
- GET /dashboard/overview
- GET /dashboard/sales
- GET /dashboard/inventory
- GET /dashboard/purchase-orders

Backend tasks:
1. Create dashboard service layer.
2. Calculate these KPIs:
   - total revenue
   - gross profit
   - gross margin percent
   - units sold
   - number of transactions
   - average order value
   - current stock value
   - low-stock product count
   - pending purchase orders
   - top-selling product
   - sales growth percent
   - slow-moving stock
3. Add date range filters.
4. Add branch/category/product filters where relevant.
5. Add previous period comparison for sales.
6. Return chart-ready data:
   - sales trend
   - revenue by category
   - top products
   - branch performance
   - inventory health
   - low-stock table
7. Optimize queries reasonably.

Frontend tasks:
1. Build Overview dashboard.
2. Build Sales Summary dashboard.
3. Build Inventory dashboard summary.
4. Add filters and date range controls.
5. Add charts using the selected chart library.
6. Add tables for top products, low-stock items, and slow-moving products.
7. Ensure loading, empty, and error states.

Important:
- Do not hardcode KPI values in frontend.
- All dashboard values must come from API/database.
- The app should feel like an operational dashboard, not a landing page.

Acceptance checks:
- Overview dashboard loads real values.
- Sales Summary dashboard loads real trends.
- Inventory dashboard loads real stock metrics.
- Filters update metrics.
- Previous-period comparison works.
- Dashboard is readable and responsive.

Report back:
- Dashboard APIs implemented.
- Dashboard UI pages implemented.
- KPI definitions used.
- Verification results.
```

## Part 9 Prompt: Reorder Recommendation Engine

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, and current code.

Build Part 9: Reorder recommendation engine.

Goal:
Help the admin decide what to order based on current stock, sales velocity, target stock, and supplier lead time.

Required formula:
Suggested reorder quantity = target stock level - current quantity on hand + expected demand during supplier lead time

Expected demand during lead time = average daily sales * supplier lead time

Suggested reorder quantity must never be negative.

Inputs:
- current stock
- reorder threshold
- target stock level
- average daily sales
- supplier lead time
- quantity already on order

Backend APIs:
- GET /inventory/reorder-recommendations
- POST /purchase-orders/from-recommendations

Backend tasks:
1. Calculate average daily sales by product and branch.
2. Calculate days until stockout where possible.
3. Calculate expected demand during supplier lead time.
4. Calculate suggested reorder quantity.
5. Assign priority:
   - Critical: stock is zero or expected to run out before supplier lead time
   - High: stock is below reorder threshold
   - Medium: stock is near reorder threshold
   - Low: stock is healthy
6. Return recommendation list with product, branch, supplier, current stock, threshold, target stock, average daily sales, lead time, days until stockout, suggested quantity, and priority.
7. Implement create purchase order draft from selected recommendations, grouped by supplier and branch.

Frontend tasks:
1. Build Low Stock and Reorder page.
2. Show recommendation table.
3. Add filters for branch, category, supplier, and priority.
4. Allow admin to select recommendations.
5. Allow admin to override suggested quantities.
6. Add action to create purchase order draft.

Acceptance checks:
- Reorder recommendation endpoint returns meaningful results from seed data.
- Critical/high/medium/low priority is visible.
- Suggested quantity is never negative.
- Admin can select products and create purchase order draft.
- Draft order has correct supplier, branch, products, quantities, and costs.

Report back:
- Reorder logic implemented.
- APIs and UI changed.
- Formula and assumptions.
- Test/manual verification results.
```

## Part 10 Prompt: Purchase Order Workflow

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, and current code.

Build Part 10: Purchase order workflow.

Goal:
Implement the full purchase order lifecycle from draft to received stock.

Statuses:
- Draft
- Pending Approval
- Approved
- Ordered
- Partially Received
- Received
- Cancelled

Backend APIs:
- GET /purchase-orders
- POST /purchase-orders
- GET /purchase-orders/{id}
- PUT /purchase-orders/{id}
- POST /purchase-orders/{id}/submit
- POST /purchase-orders/{id}/approve
- POST /purchase-orders/{id}/cancel
- POST /purchase-orders/{id}/mark-ordered
- POST /purchase-orders/{id}/receive

Backend tasks:
1. Implement purchase order list/detail/create/update.
2. Implement status transition validation.
3. Allow draft order editing.
4. Allow submit for approval.
5. Allow admin approval.
6. Allow cancellation when valid.
7. Allow mark as ordered.
8. Allow receiving full or partial quantities.
9. On receiving:
   - increase inventory quantity_on_hand
   - reduce quantity_on_order if tracked
   - create stock_movement records with movement_type = purchase_received
   - change status to Partially Received or Received
10. Audit all important purchase order actions.
11. Enforce permissions.

Frontend tasks:
1. Purchase order list page.
2. Purchase order detail page.
3. Purchase order create/edit form.
4. Approval actions for authorized admin.
5. Receive order modal.
6. Status badges and filters.

Business rules:
- Creating an order does not increase available stock.
- Receiving an order increases stock.
- Cancelled orders do not update stock.
- Only authorized users can approve orders.

Acceptance checks:
- Admin can create purchase order manually.
- Admin can approve pending purchase order.
- Admin can mark order as ordered.
- Admin can receive full or partial order.
- Receiving updates inventory and stock movement ledger.
- Invalid status transitions are rejected.
- Unauthorized approval is rejected.

Report back:
- Purchase order services/APIs changed.
- UI pages/components changed.
- Status rules implemented.
- Verification results.
```

## Part 11 Prompt: Forecasting And Demand Prediction

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, and current code.

Build Part 11: Forecasting and demand prediction.

Goal:
Use historical sales to predict future sales or demand in a business-friendly way.

MVP forecasting approach:
- Start with moving average and simple trend logic.
- Add advanced libraries only if needed and practical.
- Forecast must handle insufficient data gracefully.

Backend APIs:
- POST /forecasts/run
- GET /forecasts
- GET /forecasts/products/{product_id}

Backend tasks:
1. Build forecasting service.
2. Use historical sales data from the database.
3. Support forecast horizons:
   - 7 days
   - 30 days
   - 90 days
4. Start with overall revenue or total units forecast.
5. Add product/category/branch forecast if practical in this part.
6. Store forecast output in forecasts table.
7. Return chart-ready data for historical and forecast values.
8. Return trend label:
   - increasing
   - decreasing
   - stable
9. Return clear message if not enough historical data exists.

Frontend tasks:
1. Build Forecasting page.
2. Add forecast horizon selector.
3. Add dimension selector if supported.
4. Show historical vs forecast chart.
5. Show forecast summary and trend explanation.
6. Show insufficient-data state clearly.

Acceptance checks:
- Forecast can run from seeded historical sales.
- Forecast output is stored or returned consistently.
- Forecast dashboard displays chart.
- Insufficient data does not crash the system.
- Forecast explanation is understandable for a business user.

Report back:
- Forecasting files changed.
- Forecast method used.
- APIs/UI implemented.
- Test/manual verification results.
```

## Part 12 Prompt: AI Assistant With Database-Backed Tools

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, and current code.

Build Part 12: AI assistant.

Goal:
Create a business assistant that answers questions using real database-backed tools.

Important:
The assistant must not invent numbers. For numerical or business questions, it must call backend data retrieval tools or services.

MVP AI scope:
Read-only assistant first. Write actions can be suggested, but must require confirmation before execution.

Questions the assistant should answer:
- What are today's sales?
- Which products are low in stock?
- Which items should I reorder today?
- What are the top-selling products this month?
- Which branch performed best?
- Which products are slow-moving?
- Summarize pending purchase orders.
- Forecast next week's demand.

Backend APIs:
- POST /ai/chat
- GET /ai/sessions
- GET /ai/sessions/{id}

Required safe tool functions:
- get_sales_summary
- get_low_stock_items
- get_top_products
- get_slow_moving_products
- get_pending_purchase_orders
- get_reorder_recommendations
- get_forecast_summary

Backend tasks:
1. Create AI assistant service.
2. Create safe tool layer that queries existing services/database.
3. Implement intent routing for the required questions.
4. Store chat sessions and messages.
5. Add configurable AI provider:
   - If OPENAI_API_KEY exists, use it for language response formatting.
   - If no key exists, provide deterministic fallback responses from tool data.
6. Enforce role and branch permissions in AI data tools.
7. Add guardrails:
   - no invented numbers
   - explain missing data
   - no deletion
   - confirmation required for write actions
8. Add tests for common assistant questions if practical.

Frontend tasks:
1. Build AI Assistant page.
2. Add chat interface.
3. Add suggested question buttons.
4. Show assistant responses clearly.
5. Show loading and error states.
6. If action suggestions exist, show confirmation UI but do not auto-execute writes.

Acceptance checks:
- Assistant answers at least 8 required questions.
- Answers use actual database values.
- Missing data is explained clearly.
- Assistant does not approve orders automatically.
- Assistant respects user role and branch restrictions.
- Chat messages are stored.

Report back:
- AI services/APIs changed.
- UI page changed.
- Tool functions created.
- How to configure AI provider.
- Verification examples with sample questions and answers.
```

## Part 13 Prompt: Exports And Power BI Integration

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, and current code.

Build Part 13: Exports and Power BI integration support.

Goal:
Enable executive reporting through Power BI using local database views or exported files.

Power BI purpose:
Power BI is for reporting and presentation. Operational actions stay in the web dashboard.

Backend/database tasks:
1. Create reporting SQL views or equivalent query endpoints:
   - vw_sales_summary
   - vw_sales_by_product
   - vw_sales_by_category
   - vw_inventory_health
   - vw_low_stock
   - vw_purchase_order_status
   - vw_supplier_performance
   - vw_forecast_summary
2. Add export APIs if useful:
   - GET /exports/sales
   - GET /exports/inventory
   - GET /exports/purchase-orders
   - optional GET /exports/forecasts
3. Ensure exports respect user permissions if exposed through API.
4. Add CSV export format with clear headers.

Documentation tasks:
1. Create docs/POWER_BI_SETUP.md or equivalent.
2. Explain how Power BI Desktop can connect to local PostgreSQL.
3. Explain alternative CSV import workflow.
4. List recommended Power BI pages:
   - Executive Overview
   - Sales Performance
   - Inventory Health
   - Supplier and Purchase Orders
   - Forecast and Recommendations
5. List fields/measures to create in Power BI.
6. Add screenshots placeholder folder if needed.

Frontend tasks:
1. Build Power BI Reports page.
2. Link to setup documentation.
3. Show report refresh instructions or placeholders.
4. Optionally show export buttons.

Acceptance checks:
- Reporting views or export endpoints exist.
- CSV export works for key datasets.
- Power BI setup documentation is clear.
- Power BI page exists in web app.
- No paid cloud BI dependency is required for MVP.

Report back:
- Views/APIs created.
- Docs created.
- Export behavior.
- Power BI setup steps.
```

## Part 14 Prompt: Remote Access And Hybrid Deployment Documentation

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, and current code.

Build Part 14: Remote access and hybrid local-first deployment documentation.

Goal:
Document how the admin can access the dashboard remotely while the database remains local.

Core rules:
- Main database stays local.
- Browser accesses dashboard/API only.
- Database port must not be publicly exposed.
- Remote access must require app authentication.

Recommended options:
- Cloudflare Tunnel for a public demo URL.
- Tailscale for private secure access.
- ngrok for temporary demos.

Tasks:
1. Create docs/REMOTE_ACCESS.md.
2. Explain local-first architecture.
3. Explain why the database remains local.
4. Document Cloudflare Tunnel setup at a high level.
5. Document Tailscale setup at a high level.
6. Document ngrok demo setup at a high level.
7. Add security checklist:
   - strong admin password
   - backend auth required
   - database port private
   - environment secrets not committed
   - HTTPS/tunnel security
8. Add local run/deployment diagram if useful.
9. Update README to link this document.
10. Optionally add a Settings page section showing remote access documentation link.

Acceptance checks:
- Remote access documentation exists.
- It clearly states that the database is not exposed.
- It explains at least two remote access options.
- README links to the document.

Report back:
- Docs changed.
- Recommended option for demo.
- Security warnings included.
```

## Part 15 Prompt: Backup, Restore, And Reliability

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, and current code.

Build Part 15: Backup, restore, and reliability support.

Goal:
Make the local-first system safer by documenting and optionally scripting database backup/restore.

Tasks:
1. Create docs/BACKUP_RESTORE.md.
2. Document PostgreSQL backup command using pg_dump.
3. Document PostgreSQL restore command using psql or pg_restore.
4. Define local backup folder convention.
5. Add environment variable notes.
6. Add optional backup script in scripts/ if practical.
7. Add optional restore script in scripts/ if practical.
8. Ensure scripts do not hardcode secrets.
9. Update README with backup/restore link.
10. Optionally add Settings page backup documentation link.

Optional app feature:
- Admin can trigger a local backup command only if safe and practical.
- If not implemented, document manual commands clearly.

Acceptance checks:
- Backup documentation exists.
- Restore documentation exists.
- Commands are clear for local PostgreSQL.
- No secrets are committed.
- README links backup/restore docs.

Report back:
- Docs/scripts changed.
- Backup command.
- Restore command.
- Any limitations.
```

## Part 16 Prompt: Testing And QA Hardening

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, and current code.

Build Part 16: Testing and QA hardening.

Goal:
Verify the project as complete business workflows, not disconnected pages.

Required backend/business tests where practical:
1. Login works.
2. Role permissions work.
3. Product creation works.
4. Supplier creation works.
5. Manual stock adjustment updates inventory.
6. Manual stock adjustment creates stock movement.
7. Sale creation reduces inventory.
8. Sale creation creates stock movement.
9. Low-stock alert appears correctly.
10. Reorder suggestion calculates correctly and never returns negative quantity.
11. Purchase order creation works.
12. Purchase order approval works.
13. Purchase order receiving increases inventory.
14. Invalid purchase order status transition is rejected.
15. Forecast handles enough data.
16. Forecast handles insufficient data.
17. AI assistant answers from data tools and does not invent values.

Frontend/manual QA checklist:
1. Admin can log in.
2. Staff can log in.
3. Unauthorized pages are blocked.
4. Overview dashboard loads.
5. Sales dashboard filters work.
6. Inventory search/filter works.
7. Low-stock page shows recommendations.
8. Purchase order flow works from draft to received.
9. AI Assistant answers required questions.
10. Forecasting page displays chart or clear empty state.
11. Power BI page links docs/exports.
12. Remote access docs are reachable from README.

Tasks:
1. Add automated tests for core backend business rules.
2. Add test fixtures or test database setup.
3. Add frontend tests if project already has a frontend testing setup.
4. Add docs/QA_CHECKLIST.md with manual testing steps.
5. Run tests and fix failures.
6. Update README with test commands.

Acceptance checks:
- Automated tests pass.
- QA checklist exists.
- Manual critical workflow is documented.
- Known limitations are documented.

Report back:
- Tests added.
- Test commands run.
- Results.
- Any remaining gaps.
```

## Part 17 Prompt: Final Documentation And Portfolio Packaging

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, and current code.

Build Part 17: Final documentation and portfolio packaging.

Goal:
Make the project understandable and impressive for GitHub, interviews, and consulting-style presentation.

Required deliverables:
- README.md
- PRD.md
- EXECUTION_FLOW_ANALYSIS.md
- AGENT_STEP_BY_STEP_PROMPTS.md
- Architecture diagram
- Setup guide
- Demo script
- Business case study
- Power BI setup/reporting documentation
- Remote access documentation
- Backup/restore documentation
- Screenshots folder or placeholder instructions

README should include:
1. Project title.
2. Short business problem.
3. Solution summary.
4. Core features.
5. Tech stack.
6. Hybrid local-first architecture explanation.
7. Setup instructions.
8. Demo credentials for development seed data.
9. How to run backend.
10. How to run frontend.
11. How to run migrations and seed data.
12. How to run tests.
13. Power BI integration instructions link.
14. Remote access instructions link.
15. Backup/restore instructions link.
16. Portfolio/resume description.

Business case study should include:
1. Client problem.
2. Existing pain points.
3. Proposed solution.
4. Architecture.
5. Key features.
6. Business KPIs tracked.
7. Forecasting and reorder logic.
8. AI assistant examples.
9. Cost optimization strategy.
10. Expected business impact.

Demo script should follow this flow:
1. Explain business problem.
2. Show hybrid architecture.
3. Log in as admin.
4. Show overview dashboard.
5. Show sales summary.
6. Show inventory.
7. Show low-stock recommendations.
8. Create purchase order from recommendation.
9. Approve purchase order.
10. Receive purchase order and show stock update.
11. Ask AI Assistant: "Which products should I reorder today?"
12. Ask AI Assistant: "Summarize this month's sales."
13. Show forecasting page.
14. Show Power BI report/docs.
15. Explain cost optimization.

Tasks:
1. Audit existing documentation for gaps.
2. Update README.
3. Add docs/ARCHITECTURE.md with diagram.
4. Add docs/CASE_STUDY.md.
5. Add docs/DEMO_SCRIPT.md.
6. Ensure all docs link to each other cleanly.
7. Ensure final documentation matches the actual implementation.

Acceptance checks:
- A reviewer can understand the project without asking for explanation.
- Documentation matches current commands and features.
- Business value is clearly explained.
- Hybrid local-first design is clearly explained.
- Final demo flow is documented.

Report back:
- Docs changed.
- Final run/test status.
- Remaining optional enhancements.
```

## Part 18 Prompt: Final End-To-End Verification

```text
Read PRD.md, EXECUTION_FLOW_ANALYSIS.md, AGENT_STEP_BY_STEP_PROMPTS.md, and current code.

Build Part 18: Final end-to-end verification.

Goal:
Verify the whole product against the PRD completion definition.

Do not add new features unless needed to fix a requirement gap.

Verification checklist:
1. Local SQL database stores all core data.
2. Admin can log in.
3. Staff can log in.
4. Role-based access is enforced.
5. Products can be managed.
6. Suppliers can be managed.
7. Inventory can be viewed by product, branch, category, and supplier.
8. Manual stock adjustment works and creates stock movement.
9. Sales entry works.
10. Sales reduce inventory.
11. Sales dashboard shows real KPIs.
12. Inventory dashboard shows real stock values.
13. Low-stock alerts work.
14. Reorder recommendations work.
15. Purchase order creation works.
16. Purchase order approval works.
17. Purchase order receiving increases inventory.
18. Forecasting output is available.
19. AI assistant answers database-backed questions.
20. AI assistant does not invent numbers.
21. Power BI support exists through views or exports and documentation.
22. Remote access documentation exists and keeps database local.
23. Backup/restore documentation exists.
24. README and case study are complete.

Tasks:
1. Run available automated tests.
2. Run lint/build checks if configured.
3. Manually inspect key workflows if automated coverage is incomplete.
4. Compare implementation against PRD.md.
5. Compare implementation against EXECUTION_FLOW_ANALYSIS.md.
6. Fix any blocking gaps.
7. Create a final status report in docs/FINAL_VERIFICATION.md.

Acceptance checks:
- Tests pass or known failures are documented with reason.
- Critical business workflow works end to end.
- Final verification report exists.
- Remaining optional enhancements are clearly separated from MVP gaps.

Report back:
- Commands run.
- Test results.
- Requirement gaps fixed.
- Remaining non-blocking improvements.
```

## Quick Build Sequence

Use this exact order:

1. Global Build Context Prompt
2. Part 0: Repository Setup And Technical Foundation
3. Part 1: Database Schema And Migrations
4. Part 2: Realistic Seed Data
5. Part 3: Backend Auth, RBAC, And Audit Foundation
6. Part 4: Frontend App Shell, Login, And Navigation
7. Part 5: Master Data Management
8. Part 6: Inventory Engine And Stock Movement Ledger
9. Part 7: Sales Engine With Inventory Updates
10. Part 8: KPI Services And Core Dashboards
11. Part 9: Reorder Recommendation Engine
12. Part 10: Purchase Order Workflow
13. Part 11: Forecasting And Demand Prediction
14. Part 12: AI Assistant With Database-Backed Tools
15. Part 13: Exports And Power BI Integration
16. Part 14: Remote Access And Hybrid Deployment Documentation
17. Part 15: Backup, Restore, And Reliability
18. Part 16: Testing And QA Hardening
19. Part 17: Final Documentation And Portfolio Packaging
20. Part 18: Final End-To-End Verification

## Agent Handoff Template

Ask the agent to finish every part with this format:

```text
Part completed:

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

Next recommended part:
- ...
```

## Do Not Skip These

- Do not skip seed data. Empty dashboards make the project look weak.
- Do not skip stock movements. Inventory must be auditable.
- Do not skip backend permission checks. Frontend route hiding is not security.
- Do not skip purchase receiving logic. Purchase orders must affect stock only when received.
- Do not skip AI data tools. The assistant must not invent numbers.
- Do not skip Power BI support. This project is partly a BI portfolio project.
- Do not skip remote access documentation. The hybrid design is one of the strongest points.
- Do not skip final packaging. The project must be understandable as a consulting-style case study.

