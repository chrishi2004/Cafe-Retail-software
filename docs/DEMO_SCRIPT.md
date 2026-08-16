# Demo Script

## Purpose

Use this script for a GitHub demo video, interview walkthrough, class presentation, or portfolio review.

Target length:

- Short version: 5 to 7 minutes.
- Full version: 10 to 15 minutes.

## Pre-Demo Setup

1. Start PostgreSQL.
2. Run backend migrations.
3. Reset seed data.
4. Start backend.
5. Start frontend.

Commands:

```powershell
cd backend
.venv\Scripts\Activate.ps1
alembic upgrade head
python -m scripts.seed --reset
uvicorn app.main:app --reload
```

In another terminal:

```powershell
cd frontend
npm run dev
```

Open:

```text
http://localhost:5173
```

Admin login:

```text
admin@hybridretail.test
RetailDemo@123
```

## Demo Narrative

### 1. Explain The Business Problem

Say:

"This project solves a common small-retail problem: owners need remote visibility into stock, sales, orders, and performance, but a fully hosted ERP or cloud database can be too expensive. The system keeps the core database local, then exposes only an authenticated web dashboard and API for remote access."

Show:

- README title and short summary.
- Case study if you want a business-first opening.

### 2. Show The Hybrid Architecture

Open:

- [ARCHITECTURE.md](ARCHITECTURE.md)

Say:

"The key architecture rule is that the browser never connects directly to PostgreSQL. Remote admins go through a tunnel or private network to the dashboard/API. The backend handles authentication, role checks, branch scope, and all database access."

Point out:

- Local PostgreSQL.
- FastAPI backend.
- React dashboard.
- Power BI reporting views or CSV exports.
- Remote access through Cloudflare Tunnel, Tailscale, or ngrok.

### 3. Log In As Admin

Open the app and log in:

```text
admin@hybridretail.test
RetailDemo@123
```

Say:

"The seeded demo includes Admin, Store Manager, Staff, and Analyst roles. Permissions are enforced by the backend, not only by hiding frontend navigation."

Show:

- Sidebar navigation.
- Top bar user role.
- Dashboard shell.

### 4. Show Overview Dashboard

Open:

- Overview

Say:

"The overview dashboard gives a business owner a fast read on revenue, gross profit, units sold, average order value, stock value, low-stock count, pending purchase orders, and top products."

Point out:

- KPI cards.
- Sales trend.
- Revenue by category.
- Top products.
- Low-stock table.
- Branch performance.

### 5. Show Sales Summary

Open:

- Sales Summary

Say:

"Sales metrics are calculated from the database through backend services. The frontend is not hardcoding KPI values."

Show:

- Date range filters.
- Branch/category/product filters.
- Revenue, gross profit, units sold.
- Top product ranking.
- Sales trend chart.

### 6. Show Inventory

Open:

- Inventory

Say:

"Inventory is tracked per product and branch. Each row shows current quantity, reorder threshold, target stock, supplier, category, stock value, and low-stock status."

Show:

- Search.
- Branch/category/supplier filters.
- Low-stock filter.
- Stock movement history.

Optional:

- Perform a manual stock adjustment as Admin.
- Confirm the movement appears in stock movement history.

### 7. Show Low-Stock Recommendations

Open:

- Low Stock and Reorder

Say:

"Recommendations use current stock, target stock, recent sales velocity, and supplier lead time. The suggested quantity is never negative."

Show:

- Priority badges: critical, high, medium, low.
- Current stock.
- Threshold.
- Target stock.
- Average daily sales.
- Lead time.
- Suggested reorder quantity.

### 8. Create Purchase Order From Recommendation

On Low Stock and Reorder:

1. Select one or more recommendations.
2. Override quantity if useful.
3. Create purchase order draft.

Say:

"The system groups selected products by supplier and branch and creates draft purchase orders. Creating the draft does not increase available inventory."

### 9. Approve Purchase Order

Open:

- Purchase Orders

Steps:

1. Open the draft purchase order.
2. Submit for approval.
3. Approve as Admin.
4. Mark as ordered.

Say:

"The purchase order workflow is controlled by status transitions. Only authorized users can approve orders."

Point out:

- Draft.
- Pending Approval.
- Approved.
- Ordered.

### 10. Receive Purchase Order And Show Stock Update

In the purchase order detail:

1. Receive full or partial quantity.
2. Confirm status becomes Partially Received or Received.
3. Return to Inventory.
4. Confirm quantity on hand increased.
5. Open stock movement history.

Say:

"Available stock only increases when the order is received. Receiving creates `purchase_received` stock movement records, so inventory remains auditable."

### 11. Ask AI Assistant: Reorder Question

Open:

- AI Assistant

Ask:

```text
Which products should I reorder today?
```

Say:

"The assistant answers through backend data tools. It is not allowed to invent numbers. Reorder answers are based on the same recommendation engine used by the dashboard."

Point out:

- Suggested products.
- Priority.
- Quantities.
- Supplier names.
- Confirmation note for write actions.

### 12. Ask AI Assistant: Sales Summary

Ask:

```text
Summarize this month's sales.
```

Say:

"This answer comes from the sales dashboard service. If a role is branch-scoped, the assistant only sees that user's allowed branch data."

Optional write guardrail demo:

```text
Approve a purchase order now.
```

Expected result:

- Assistant says confirmation and a permission-checked workflow are required.
- No purchase order is changed from chat.

### 13. Show Forecasting Page

Open:

- Forecasting

Run:

- 7 day forecast.
- 30 day forecast.
- Demand forecast by product if useful.

Say:

"The MVP forecasting model is intentionally explainable. It uses historical sales, moving averages, and trend logic. If there is not enough data, the page shows a clear insufficient-data state instead of failing."

Show:

- Historical vs forecast chart.
- Forecast value.
- Trend label.
- Explanation.

### 14. Show Power BI Report Or Docs

Open:

- Power BI Reports page in the app.
- [POWER_BI_SETUP.md](POWER_BI_SETUP.md)

Say:

"Power BI is supported through local SQL reporting views or authenticated CSV exports. Operational actions stay in the dashboard; Power BI is for executive reporting and presentation."

Point out:

- Reporting views.
- CSV export endpoints.
- Recommended Power BI pages.
- `powerbi/screenshots/` folder for report screenshots.

### 15. Explain Cost Optimization

Say:

"The cost optimization is the heart of the project. The business does not need a paid cloud database for the MVP. PostgreSQL stays local, backups are local, Power BI can connect locally, and remote users reach only the authenticated dashboard/API through a tunnel or private network."

Mention:

- Remote access docs.
- Backup and restore docs.
- Security checklist.
- Database port stays private.

## Short Demo Version

Use this condensed path:

1. Architecture.
2. Admin login.
3. Overview dashboard.
4. Inventory low-stock filter.
5. Reorder recommendations.
6. Create purchase order draft.
7. Approve and receive order.
8. AI reorder question.
9. Forecasting.
10. Power BI docs.
11. Cost optimization summary.

## Screenshots To Capture During Demo

Capture:

- Overview dashboard.
- Sales Summary dashboard.
- Inventory table with low-stock rows.
- Low Stock and Reorder page.
- Purchase order detail after receiving.
- Forecasting page.
- AI Assistant response.
- Power BI Reports page or Power BI Desktop report.
- Architecture diagram from docs.

See [SCREENSHOTS.md](SCREENSHOTS.md).

## Closing Pitch

Say:

"This is a consulting-style full-stack BI project. It combines SQL data modeling, operational workflows, dashboards, forecasting, AI guardrails, reporting exports, remote access strategy, and local-first cost control. The result is not just a nice dashboard; it is an end-to-end retail workflow where sales, stock, orders, forecasts, and AI answers all use the same local business data."

## Related Docs

- [Architecture](ARCHITECTURE.md)
- [Case Study](CASE_STUDY.md)
- [Setup Guide](SETUP_GUIDE.md)
- [Power BI Setup](POWER_BI_SETUP.md)
- [Remote Access](REMOTE_ACCESS.md)
- [Backup And Restore](BACKUP_RESTORE.md)
- [QA Checklist](QA_CHECKLIST.md)
- [Screenshots Guide](SCREENSHOTS.md)
