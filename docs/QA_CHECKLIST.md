# QA Checklist

## Purpose

This checklist verifies the project as an end-to-end retail business workflow, not only as separate backend routes or frontend pages.

Use it after migrations and seed data have been loaded, or when preparing a demo.

## Test Setup

Recommended local services:

- Backend API: `http://localhost:8000`
- Frontend dashboard: `http://localhost:5173`
- Database: local PostgreSQL, not exposed publicly

Seed demo data:

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m scripts.seed --reset
```

Demo credentials are listed in [DEMO_CREDENTIALS.md](DEMO_CREDENTIALS.md).

## Automated Backend QA

Run the workflow regression first:

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m pytest tests/test_business_workflows.py -q
```

Run the broader backend suite in groups if one long command is noisy or slow in the local terminal:

```powershell
python -m pytest tests/test_auth.py tests/test_master_data.py tests/test_inventory.py tests/test_sales.py -q
python -m pytest tests/test_reorder.py tests/test_purchase_orders.py tests/test_dashboard.py tests/test_forecasts.py -q
python -m pytest tests/test_ai.py tests/test_exports.py tests/test_business_workflows.py -q
```

The workflow regression covers:

- Login and backend role blocking.
- Product and supplier creation through APIs.
- Manual stock adjustment, inventory update, and stock movement ledger.
- Sale creation, inventory reduction, and sale stock movement.
- Low-stock detection and reorder recommendation quantity guardrail.
- Purchase order draft, submit, approval, invalid transition rejection, ordered state, and receiving.
- Purchase receiving inventory increase and purchase receipt stock movement.
- Forecast success with enough history and clear insufficient-data handling.
- AI assistant response through database-backed tool data.

## Frontend Build QA

The frontend currently uses TypeScript and Vite scripts, but no dedicated frontend unit or end-to-end test runner is configured.

Run:

```powershell
cd frontend
npm run typecheck
npm run build
```

## Manual Functional Checklist

| Area | Steps | Expected Result |
| --- | --- | --- |
| Admin login | Open the dashboard, sign in as Admin. | Overview dashboard loads with the authenticated app shell. |
| Staff login | Sign out, sign in as Staff. | Staff can access allowed operational pages only. |
| Unauthorized pages | Try admin-only master data or settings actions as Staff or Analyst. | Backend rejects restricted write actions, even if a route is manually opened. |
| Overview dashboard | Open Overview after seed data is loaded. | KPI cards and charts load from API data, not hardcoded frontend values. |
| Sales dashboard filters | Open Sales Summary, change date range or branch/category/product filters. | Metrics and charts refresh to match selected filters. |
| Inventory filters | Open Inventory, search by product and filter low stock. | Table updates and low-stock rows are marked clearly. |
| Stock adjustment | As Admin or Store Manager, adjust stock with a reason. | Quantity changes and a matching stock movement appears. |
| Sale entry | As Staff or Manager, create a sale with multiple products. | Sale saves, totals are calculated by backend, stock decreases. |
| Low-stock and reorder | Open Low Stock and Reorder, filter by priority. | Recommendations show current stock, target stock, lead time, velocity, and suggested quantity. |
| Purchase order draft | Select reorder recommendations and create draft order. | Draft purchase order is created without increasing available stock. |
| Purchase order approval | Submit and approve a pending purchase order as Admin. | Status changes follow Draft to Pending Approval to Approved. |
| Purchase receiving | Mark approved order as ordered, then receive full or partial quantity. | Inventory increases only on receiving and stock movement ledger records purchase receipt. |
| Invalid PO transition | Try to approve an already approved order or mark a draft as ordered. | API returns a clear validation error. |
| Forecasting page | Run a 7, 30, or 90 day forecast. | Chart shows historical plus forecast values, or a clear insufficient-data state. |
| AI Assistant | Ask each suggested business question. | Assistant uses tool-backed data, stores chat messages, and asks confirmation for write-like requests. |
| Power BI page | Open Power BI Reports. | Page links setup docs and export buttons or API guidance. |
| CSV exports | Download sales, inventory, purchase orders, and forecasts exports as an authenticated user. | CSV has clear headers and respects access permissions. |
| Remote access docs | Open README remote access link. | Documentation explains that only the app/API is exposed, not PostgreSQL. |
| Backup docs | Open README backup/restore link. | Documentation includes `pg_dump`, `pg_restore`, `psql`, and script usage without hardcoded secrets. |

## AI Question Checklist

Ask these in the AI Assistant page:

- What are today's sales?
- Which products are low in stock?
- Which items should I reorder today?
- What are the top-selling products this month?
- Which branch performed best?
- Which products are slow-moving?
- Summarize pending purchase orders.
- Forecast next week's demand.
- Approve a purchase order now.

Expected behavior:

- Numerical answers come from tool data.
- Missing data is explained instead of guessed.
- Write-like requests require confirmation and do not change records from chat.
- Role and branch scope are respected.

## Known Limitations

- Frontend unit or browser end-to-end tests are not configured yet.
- Backup scripts require PostgreSQL client tools such as `pg_dump`, `pg_restore`, and `psql` to be installed locally.
- The app documents remote access setup, but live tunnel verification depends on the selected tool and network.
- AI language-model formatting is optional. Without `OPENAI_API_KEY`, deterministic database-backed responses are used.

## Related Docs

- [Architecture](ARCHITECTURE.md)
- [Setup Guide](SETUP_GUIDE.md)
- [Case Study](CASE_STUDY.md)
- [Demo Script](DEMO_SCRIPT.md)
- [Power BI Setup](POWER_BI_SETUP.md)
- [Remote Access](REMOTE_ACCESS.md)
- [Backup And Restore](BACKUP_RESTORE.md)
- [Screenshots Guide](SCREENSHOTS.md)
- [Final Verification](FINAL_VERIFICATION.md)
