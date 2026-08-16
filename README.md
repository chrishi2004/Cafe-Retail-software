# AI-Powered Hybrid Retail Inventory, Sales Analytics, and Remote Order Management System

A full-stack portfolio project that solves a practical small-retail problem: owners need remote visibility into stock, sales, purchase orders, forecasts, and business performance, but do not want the recurring cost of a fully hosted cloud database.

The system keeps the main business database local and exposes only an authenticated web dashboard/API for remote access through Cloudflare Tunnel, Tailscale, or ngrok. It combines retail operations, business intelligence, forecasting, AI-assisted analysis, Power BI reporting support, backup guidance, and workflow-level QA.

## Business Problem

Small and medium retail businesses often run inventory, sales, suppliers, and purchase orders through disconnected spreadsheets or manual checks. That creates stockouts, late ordering, slow sales reporting, poor visibility for remote owners, and unnecessary cloud cost.

This project presents a consulting-style solution: a local-first operational system with secure remote dashboard access, data-backed reorder decisions, AI business answers, Power BI reporting, and a clear recovery path.

## Solution Summary

The application lets an Admin or owner:

- Log in remotely through the web dashboard.
- Check live inventory by branch, product, category, supplier, and low-stock status.
- Review sales KPIs, trends, gross profit, branch performance, top products, and slow-moving stock.
- Record sales and reduce inventory through transactional backend logic.
- Generate reorder recommendations using stock, target levels, sales velocity, and supplier lead time.
- Create purchase order drafts from recommendations, approve orders, mark them ordered, and receive stock.
- Run explainable forecasts using historical sales.
- Ask an AI assistant business questions that use backend data tools instead of invented numbers.
- Export CSV data or connect Power BI Desktop to local SQL reporting views.
- Keep PostgreSQL local and private while documenting remote dashboard access.
- Back up and restore the local database with documented PostgreSQL commands and helper scripts.

## Core Features

- Authentication with bearer tokens, logout invalidation, current user lookup, role checks, and branch scope.
- Roles: Admin, Store Manager, Staff, Analyst.
- Master data management for products, categories, suppliers, and branches.
- Inventory table, low-stock detection, manual adjustments, and stock movement ledger.
- Sales entry with multiple items, server-side totals, stock validation, inventory reduction, and audit logs.
- KPI dashboards for overview, sales, inventory, and purchase orders.
- Reorder recommendation engine with critical, high, medium, and low priorities.
- Purchase order workflow: Draft, Pending Approval, Approved, Ordered, Partially Received, Received, Cancelled.
- Forecasting service using moving average plus simple trend logic.
- AI Assistant with safe tools for sales, low stock, reorder, top products, branch performance, slow-moving stock, pending purchase orders, and forecasts.
- Reporting SQL views and authenticated CSV exports for Power BI.
- Remote access, backup/restore, QA, demo, and portfolio documentation.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | FastAPI, Python, SQLAlchemy |
| Database | Local PostgreSQL |
| Migrations | Alembic |
| Frontend | React, TypeScript, Vite |
| Charts | Recharts |
| Icons | lucide-react |
| AI | Backend tool layer first, optional OpenAI API formatting |
| BI | Power BI Desktop through local SQL views or CSV exports |
| Remote access | Cloudflare Tunnel, Tailscale, or ngrok |
| Backup | PostgreSQL `pg_dump`, `pg_restore`, `psql`, PowerShell helpers |

## Hybrid Local-First Architecture

Core rule: remote users access the dashboard/API only. The browser never connects directly to PostgreSQL.

```mermaid
flowchart LR
    Staff["Store staff or manager"] --> Frontend["React dashboard"]
    Admin["Remote admin browser"] --> Tunnel["Cloudflare Tunnel, Tailscale, or ngrok"]
    Tunnel --> Frontend
    Frontend --> API["FastAPI backend API"]
    API --> Auth["Auth, RBAC, branch scope"]
    API --> DB[("Local PostgreSQL")]
    API --> Services["Dashboard, inventory, sales, reorder, PO, forecast, AI services"]
    Services --> DB
    API --> Exports["CSV export APIs"]
    PowerBI["Power BI Desktop"] --> Views["Local SQL reporting views"]
    Views --> DB
    Backup["Backup scripts"] --> DB
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full architecture, component map, business flows, and data rules.

## Project Structure

```text
backend/    FastAPI API, SQLAlchemy models, Alembic migrations, tests, seed script
frontend/   React TypeScript dashboard, API clients, authenticated pages
docs/       Setup, architecture, case study, demo script, QA, reporting, remote access, backup
powerbi/    Power BI placeholders and screenshot folder
scripts/    PostgreSQL backup and restore helper scripts
```

## Quick Start

For a detailed setup walkthrough, use [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md).

### 1. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy ..\.env.example .env
uvicorn app.main:app --reload
```

Health check:

```text
http://localhost:8000/api/health
```

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Dashboard:

```text
http://localhost:5173
```

### 3. Local Database

Default local PostgreSQL URL:

```text
postgresql+psycopg://postgres:postgres@localhost:5432/hybrid_retail_bi
```

Run migrations:

```powershell
cd backend
.venv\Scripts\Activate.ps1
alembic upgrade head
```

Seed realistic demo data:

```powershell
python -m scripts.seed --reset
```

The seed now also prepares the billing add-on foundation: demo business profile, branch GST/state records, GST rates `0%`, `5%`, `12%`, `18%`, `28%`, payment modes, print template placeholders, and the default invoice sequence `INV-2026-00001`.

## Demo Credentials

All seeded demo users use this development-only password:

```text
RetailDemo@123
```

| Role | Email | Scope |
| --- | --- | --- |
| Admin | `admin@hybridretail.test` | All branches |
| Store Manager | `manager.central@hybridretail.test` | Central Market |
| Staff | `staff.north@hybridretail.test` | Northside Express |
| Staff | `staff.lakeside@hybridretail.test` | Lakeside Daily |
| Analyst | `analyst@hybridretail.test` | Read-only reporting |

See [docs/DEMO_CREDENTIALS.md](docs/DEMO_CREDENTIALS.md). Change these before using the app outside a local demo.

Development GST profile: `Hybrid Retail Demo Private Limited`, PAN `ABCDE1234F`, primary GSTIN `29ABCDE1234F1Z5`. GST/e-invoice/e-way bill features are demo operational aids and must be reviewed by a CA/GST expert before real filing or production use.

## Main API Surface

All endpoints are prefixed with `/api`.

```text
GET  /health

POST /auth/login
POST /auth/logout
GET  /auth/me

GET  /products
POST /products
GET  /products/{id}
PUT  /products/{id}
PATCH /products/{id}/deactivate

GET  /categories
POST /categories
PUT  /categories/{id}

GET  /suppliers
POST /suppliers
GET  /suppliers/{id}
PUT  /suppliers/{id}

GET  /branches
POST /branches
PUT  /branches/{id}

GET  /inventory
GET  /inventory/low-stock
GET  /inventory/reorder-recommendations
POST /inventory/adjustments
GET  /inventory/movements
GET  /inventory/{product_id}

GET  /sales
POST /sales
GET  /sales/summary
GET  /sales/trends
GET  /sales/{sale_id}

GET  /dashboard/overview
GET  /dashboard/sales
GET  /dashboard/inventory
GET  /dashboard/purchase-orders

GET  /purchase-orders
POST /purchase-orders
POST /purchase-orders/from-recommendations
GET  /purchase-orders/{id}
PUT  /purchase-orders/{id}
POST /purchase-orders/{id}/submit
POST /purchase-orders/{id}/approve
POST /purchase-orders/{id}/cancel
POST /purchase-orders/{id}/mark-ordered
POST /purchase-orders/{id}/receive

POST /forecasts/run
GET  /forecasts
GET  /forecasts/products/{product_id}

POST /ai/chat
GET  /ai/sessions
GET  /ai/sessions/{session_id}

GET  /exports/sales
GET  /exports/inventory
GET  /exports/purchase-orders
GET  /exports/forecasts
```

## Business Rules Implemented

- Sales reduce inventory.
- Purchase order creation does not increase available inventory.
- Purchase order receiving increases inventory.
- Every stock change creates a stock movement record.
- Manual stock adjustments require a reason.
- Reorder quantity uses target stock, current stock, average daily sales, and supplier lead time, and is never negative.
- Dashboard metrics are calculated from backend/database data, not hardcoded frontend values.
- AI numerical answers use backend data tools.
- AI write-like requests require confirmation and do not mutate records through chat.
- Backend role and branch scope checks enforce permissions.

## Forecasting And AI

Forecasting supports 7, 30, and 90 day horizons for revenue, units, and product demand where data exists. The model intentionally starts explainable: recent moving averages plus simple trend adjustment, with a clear insufficient-data state.

The AI assistant is read-oriented in the MVP. It can answer:

- What are today's sales?
- Which products are low in stock?
- Which items should I reorder today?
- What are the top-selling products this month?
- Which branch performed best?
- Which products are slow-moving?
- Summarize pending purchase orders.
- Forecast next week's demand.

Optional OpenAI settings:

```text
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
```

If no key is configured, deterministic database-backed responses still work.

## Power BI Reporting

Power BI is for executive reporting and presentation. Operational actions stay in the web app/API.

Reporting views:

```text
vw_sales_summary
vw_sales_by_product
vw_sales_by_category
vw_inventory_health
vw_low_stock
vw_purchase_order_status
vw_supplier_performance
vw_forecast_summary
```

See [docs/POWER_BI_SETUP.md](docs/POWER_BI_SETUP.md) for PostgreSQL connection steps, CSV export workflow, recommended report pages, and suggested measures.

## Remote Access

The database remains local and private. Remote access should expose only the authenticated dashboard/API.

Recommended options:

- Cloudflare Tunnel for a polished public portfolio demo URL.
- Tailscale for private access from trusted devices.
- ngrok for temporary demos.

See [docs/REMOTE_ACCESS.md](docs/REMOTE_ACCESS.md).

## Backup And Restore

The local PostgreSQL database is the system of record. Backup files should stay out of git.

```powershell
.\scripts\backup_postgres.ps1
.\scripts\restore_postgres.ps1 -BackupFile .\backups\postgres\YYYY-MM\hybrid_retail_bi_YYYYMMDD_HHMMSS.dump -Clean -Confirm:$false
```

See [docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md) for manual and scripted workflows.

## QA And Testing

Workflow regression:

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m pytest tests/test_business_workflows.py -q
```

Broader backend regression:

```powershell
python -m pytest tests/test_auth.py tests/test_master_data.py tests/test_inventory.py tests/test_sales.py -q
python -m pytest tests/test_reorder.py tests/test_purchase_orders.py tests/test_dashboard.py tests/test_forecasts.py -q
python -m pytest tests/test_ai.py tests/test_exports.py tests/test_business_workflows.py -q
```

Frontend checks:

```powershell
cd frontend
npm run typecheck
npm run build
```

See [docs/QA_CHECKLIST.md](docs/QA_CHECKLIST.md) for manual workflow testing and known limitations.

## Portfolio And Demo Docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): system architecture, component map, business flows, and security rules.
- [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md): local installation, database setup, migrations, seed data, and troubleshooting.
- [docs/CASE_STUDY.md](docs/CASE_STUDY.md): consulting-style business case study.
- [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md): interview and portfolio walkthrough script.
- [docs/SCREENSHOTS.md](docs/SCREENSHOTS.md): screenshot capture plan and placeholder guidance.
- [docs/POWER_BI_SETUP.md](docs/POWER_BI_SETUP.md): Power BI reporting setup.
- [docs/REMOTE_ACCESS.md](docs/REMOTE_ACCESS.md): remote dashboard access while keeping PostgreSQL private.
- [docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md): backup, restore, and reliability guide.
- [docs/QA_CHECKLIST.md](docs/QA_CHECKLIST.md): automated and manual QA checklist.
- [docs/FINAL_VERIFICATION.md](docs/FINAL_VERIFICATION.md): final PRD completion verification report.
- [docs/DEMO_CREDENTIALS.md](docs/DEMO_CREDENTIALS.md): seed user accounts.

Planning documents:

- [PRD.md](PRD.md)
- [EXECUTION_FLOW_ANALYSIS.md](EXECUTION_FLOW_ANALYSIS.md)
- [AGENT_STEP_BY_STEP_PROMPTS.md](AGENT_STEP_BY_STEP_PROMPTS.md)

Planned multi-venture Retail and Cafe expansion (not yet implemented):

- [PRD_MULTI_VENTURE_CAFE_EXPANSION.md](PRD_MULTI_VENTURE_CAFE_EXPANSION.md): product contract for venture isolation, Cafe operations, QR ordering, and owner governance.
- [PRD_HYBRID_CLOUD_CONTINUITY_ADDENDUM.md](PRD_HYBRID_CLOUD_CONTINUITY_ADDENDUM.md): approved Vercel, Supabase, Local Hub, automatic queue resume, and outage-continuity contract.
- [TRD_MULTI_VENTURE_CAFE_EXPANSION.md](TRD_MULTI_VENTURE_CAFE_EXPANSION.md): schema, authorization, API, transaction, tax-mode, and security design.
- [TRD_HYBRID_CLOUD_CONTINUITY.md](TRD_HYBRID_CLOUD_CONTINUITY.md): cloud/local data authority, durable synchronization, writer fencing, restart, and recovery design.
- [docs/MULTI_VENTURE_CAFE_IMPLEMENTATION_PHASES.md](docs/MULTI_VENTURE_CAFE_IMPLEMENTATION_PHASES.md): gated implementation order and tests for every phase.
- [docs/HYBRID_CLOUD_CONTINUITY_IMPLEMENTATION_PHASES.md](docs/HYBRID_CLOUD_CONTINUITY_IMPLEMENTATION_PHASES.md): required Vercel, Supabase, Local Hub, and failure-recovery gates integrated into the Cafe phases.
- [docs/HYBRID_DEPLOYMENT_FOUNDATION.md](docs/HYBRID_DEPLOYMENT_FOUNDATION.md): HC0 runtime modes, migration separation, Vercel project roots, Local Hub service design, and credential boundaries.
- [AGENT_STEP_BY_STEP_PROMPTS_MULTI_VENTURE_CAFE.md](AGENT_STEP_BY_STEP_PROMPTS_MULTI_VENTURE_CAFE.md): copy-paste execution prompts for Phases 0 through 11.
- [Multi-Venture Cafe Phase Prompts PDF](output/pdf/MULTI_VENTURE_CAFE_PHASE_PROMPTS.pdf): original formatted playbook; it predates the hybrid continuity addenda and must not be executed without the newer documents and HC gates.

## Portfolio Resume Description

AI-Powered Hybrid Business Intelligence Platform for Retail Inventory, Sales Forecasting, and Remote Order Management.

Built a cost-optimized full-stack retail management system with local PostgreSQL storage, secure remote dashboard access, role-based operations, inventory and sales workflows, stock movement ledger, reorder recommendations, purchase order lifecycle, forecasting, AI business assistant, Power BI reporting support, and backup/restore documentation.

## Current MVP Status

The MVP is implemented across backend, frontend, database migrations, seed data, dashboards, forecasting, AI, Power BI exports, remote access docs, backup docs, and QA hardening. Remaining optional enhancements include frontend end-to-end tests, a polished Power BI `.pbix` file with screenshots, a production reverse proxy configuration, and advanced forecasting models.
