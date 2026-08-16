# Power BI Setup Guide

This guide explains how to build executive reports for the AI-Powered Hybrid Retail Inventory, Sales Analytics, and Remote Order Management System.

Power BI is used for reporting and presentation. Operational actions such as sales entry, stock adjustment, purchase order approval, receiving, and AI-assisted actions stay inside the web dashboard and backend API.

## Reporting Architecture

- Main business database: local PostgreSQL.
- Default reporting path: Power BI Desktop connects to local SQL reporting views.
- Alternative reporting path: authenticated CSV exports from the web API.
- Remote admin access: web app/API only. Do not expose the database directly over the internet.
- MVP cloud cost: no paid cloud database or paid BI service is required.

## Option A: Connect Power BI Desktop to Local PostgreSQL

1. Run the backend migrations so the reporting views exist.

```powershell
cd backend
.venv\Scripts\Activate.ps1
alembic upgrade head
```

2. Confirm the local database is available.

```text
postgresql+psycopg://postgres:postgres@localhost:5432/hybrid_retail_bi
```

3. Open Power BI Desktop.
4. Choose **Get Data**.
5. Select **PostgreSQL database**.
6. Enter:

```text
Server: localhost
Database: hybrid_retail_bi
```

7. Use **Import** mode for a simple portfolio demo.
8. Select the reporting views listed below.
9. Build relationships only if needed. The views are already shaped for reporting pages.
10. Refresh the report after running seed data, recording sales, receiving purchase orders, or running forecasts.

Microsoft reference: [Power Query PostgreSQL connector](https://learn.microsoft.com/en-us/power-query/connectors/postgresql)

## Option B: Import CSV Exports

Use CSV exports when you want a portable report file or do not want Power BI Desktop to connect directly to PostgreSQL.

Authenticated export endpoints:

```text
GET /api/exports/sales
GET /api/exports/inventory
GET /api/exports/purchase-orders
GET /api/exports/forecasts
```

The web app Power BI Reports page provides download buttons for the same files.

Recommended workflow:

1. Log in as Admin or Analyst.
2. Open **Power BI Reports** in the dashboard.
3. Download the needed CSV files.
4. In Power BI Desktop, choose **Get Data > Text/CSV**.
5. Import each file and set data types.
6. Refresh by downloading new CSV files after business data changes.

Microsoft reference: [Power Query Text/CSV connector](https://learn.microsoft.com/en-us/power-query/connectors/text-csv)

## Reporting Views

| View | Purpose | Recommended Power BI Page |
| --- | --- | --- |
| `vw_sales_summary` | Daily revenue, gross profit, units sold, transaction count, and average order value by branch. | Executive Overview |
| `vw_sales_by_product` | Product-level revenue, units, gross profit, category, supplier, and branch. | Sales Performance |
| `vw_sales_by_category` | Category revenue mix, gross profit, units, and product counts. | Sales Performance |
| `vw_inventory_health` | Current stock, stock value, reorder threshold, quantity on order, low-stock flag, and stock status. | Inventory Health |
| `vw_low_stock` | Product-branch rows at or below reorder threshold. | Inventory Health |
| `vw_purchase_order_status` | Purchase order count and value by status, supplier, and branch. | Supplier and Purchase Orders |
| `vw_supplier_performance` | Supplier product coverage, order value, open order value, ordered quantity, and received quantity. | Supplier and Purchase Orders |
| `vw_forecast_summary` | Stored forecast scopes, forecast values, confidence bands, horizon dates, and model names. | Forecast and Recommendations |

## Recommended Report Pages

1. Executive Overview
2. Sales Performance
3. Inventory Health
4. Supplier and Purchase Orders
5. Forecast and Recommendations

## Suggested Fields And Measures

Use the views directly for simple visuals, then create measures for executive KPIs.

Common measures:

```DAX
Total Revenue = SUM(vw_sales_summary[revenue])
Gross Profit = SUM(vw_sales_summary[gross_profit])
Gross Margin % = DIVIDE([Gross Profit], [Total Revenue])
Units Sold = SUM(vw_sales_summary[units_sold])
Transactions = SUM(vw_sales_summary[transaction_count])
Average Order Value = DIVIDE([Total Revenue], [Transactions])
Current Stock Value = SUM(vw_inventory_health[stock_value])
Low Stock Count = COUNTROWS(FILTER(vw_inventory_health, vw_inventory_health[is_low_stock] = 1))
Open Purchase Order Value = SUM(vw_supplier_performance[open_order_value])
Forecast Value = SUM(vw_forecast_summary[forecast_value])
```

Useful slicers:

- Date
- Branch
- Category
- Supplier
- Product
- Purchase order status
- Forecast type
- Stock status

## Page Build Notes

Executive Overview:

- KPI cards: total revenue, gross profit, gross margin percent, stock value, low-stock count, open order value.
- Charts: revenue trend, revenue by branch, inventory health mix, pending purchase order value.

Sales Performance:

- Product ranking by revenue, units sold, and gross profit.
- Category revenue mix.
- Branch performance comparison.

Inventory Health:

- Low-stock table from `vw_low_stock`.
- Stock value by category and branch.
- Stock status mix from `vw_inventory_health`.

Supplier and Purchase Orders:

- Purchase order value by status.
- Supplier open order value.
- Ordered quantity vs received quantity.

Forecast and Recommendations:

- Forecast value by scope and horizon.
- Confidence low/high band if you build a line or range visual.
- Latest forecast table by product, category, branch, and model.

## Screenshots Folder

Store portfolio screenshots or exported report images in:

```text
powerbi/screenshots/
```

Suggested screenshots:

- Executive overview report page.
- Inventory health page.
- Supplier and purchase order page.
- Forecast page.

## Security Notes

- Keep PostgreSQL bound to local/private network access for the MVP.
- Do not publish PostgreSQL credentials in the frontend or screenshots.
- Use backend export APIs for role-aware CSV downloads.
- If remote reporting is required later, prefer a secure tunnel/VPN workflow and document it separately.
- The web app and backend remain the source of truth for operational changes.

## Troubleshooting

- If views are missing, run `alembic upgrade head`.
- If PostgreSQL does not appear in Power BI Desktop, install the required local database provider prompted by Power BI.
- If CSV columns load as text, set types in Power Query before building measures.
- If exports fail, confirm the backend is running and the logged-in user has Admin, Store Manager, or Analyst reporting access.

## Related Docs

- [Architecture](ARCHITECTURE.md)
- [Setup Guide](SETUP_GUIDE.md)
- [Case Study](CASE_STUDY.md)
- [Demo Script](DEMO_SCRIPT.md)
- [Screenshots Guide](SCREENSHOTS.md)
- [QA Checklist](QA_CHECKLIST.md)
