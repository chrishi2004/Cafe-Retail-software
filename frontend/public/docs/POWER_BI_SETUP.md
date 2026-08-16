# Power BI Setup Guide

This browser-accessible copy mirrors the project guide at `docs/POWER_BI_SETUP.md`.

Use Power BI for reporting and presentation only. Sales entry, stock changes, purchase order approval, receiving, and AI-assisted actions stay inside the web dashboard and backend API.

## Direct Local PostgreSQL Workflow

1. Run migrations:

```powershell
cd backend
.venv\Scripts\Activate.ps1
alembic upgrade head
```

2. Open Power BI Desktop.
3. Choose **Get Data > PostgreSQL database**.
4. Use:

```text
Server: localhost
Database: hybrid_retail_bi
```

5. Import these views:

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

Microsoft reference: https://learn.microsoft.com/en-us/power-query/connectors/postgresql

## CSV Workflow

Use the web dashboard export buttons or these authenticated API paths:

```text
GET /api/exports/sales
GET /api/exports/inventory
GET /api/exports/purchase-orders
GET /api/exports/forecasts
```

Then import files in Power BI Desktop with **Get Data > Text/CSV**.

Microsoft reference: https://learn.microsoft.com/en-us/power-query/connectors/text-csv

## Recommended Report Pages

- Executive Overview
- Sales Performance
- Inventory Health
- Supplier and Purchase Orders
- Forecast and Recommendations

## Security Notes

- Keep the main database local.
- Do not expose PostgreSQL directly for remote admin access.
- Use backend APIs for role-aware exports.
- No paid cloud database or paid BI service is required for the MVP.
