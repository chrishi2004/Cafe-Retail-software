# Backend

FastAPI service for the Hybrid Retail BI system.

The approved hybrid expansion supports two fail-closed profiles from this backend directory:

- Local Hub: `app.main:app`, with all existing operational routes and local PostgreSQL.
- Cloud gateway: `server:app`, with only explicitly approved cloud routes and Supabase coordination storage.

HC0 established the deployment boundary and HC1 added durable local synchronization. See [Hybrid Deployment Foundation](../docs/HYBRID_DEPLOYMENT_FOUNDATION.md).

## Run Locally

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

The response includes `deployment_mode=local_hub`.

## Operational hosted deployment

`server.py` is reserved for the restricted Vercel cloud gateway and must remain
configured with `DEPLOYMENT_MODE=cloud_gateway`. It does not expose login or
the full operational API by design.

For a full hosted dashboard/API deployment, use `operational_server:app` (or
`app.main:app`) on a host that supports a persistent FastAPI service:

```powershell
uvicorn operational_server:app --host 0.0.0.0 --port $env:PORT
```

Configure that service with `DEPLOYMENT_MODE=local_hub`, a private operational
PostgreSQL URL, a production `SECRET_KEY`, and the deployed frontend origin.
Point the frontend's `VITE_API_BASE_URL` at this operational service. Keep the
Vercel cloud gateway separately configured with `DEPLOYMENT_MODE=cloud_gateway`
for HC2-HC4 coordination routes.

## Migration Boundaries

Existing Local Hub migrations:

```powershell
alembic -c alembic.ini upgrade head
```

Independent Supabase coordination migrations, after setting `CLOUD_MIGRATION_DATABASE_URL`:

```powershell
alembic -c alembic_cloud.ini upgrade head
```

The cloud migration history remains independent from the Local Hub Alembic chain.

## Seed Demo Data

After P1 multi-venture migrations, use the ownership-aware seed entry point. It creates one Business
Group, the Retail demo venture, a minimal Cafe venture/branch, and then the existing rich Retail demo
data. It does not create public QR ordering or Cafe orders.

```powershell
python scripts/seed_multi_venture.py
```

To replace existing development business data:

```powershell
python scripts/seed_multi_venture.py --reset
```

The older `python -m scripts.seed` generator is retained as the deterministic Retail data source, but
the P1+ entry point above is required because it establishes company ownership before inserting
company-scoped records.

## Auth Endpoints

```text
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

Authenticated requests use:

```text
Authorization: Bearer <access_token>
```

## Master Data Endpoints

Admin write endpoints are available for products, categories, suppliers, and branches:

```text
/api/products
/api/categories
/api/suppliers
/api/branches
```

## Inventory Endpoints

```text
GET  /api/inventory
GET  /api/inventory/{product_id}
GET  /api/inventory/low-stock
POST /api/inventory/adjustments
GET  /api/inventory/movements
```

## Sales Endpoints

Sales creation is transactional: the API writes the sale and line items, reduces inventory, records
sale stock movements, and creates an audit log together.

```text
GET  /api/sales
POST /api/sales
GET  /api/sales/{sale_id}
GET  /api/sales/summary
GET  /api/sales/trends
```

## Dashboard Endpoints

Dashboard endpoints calculate KPIs from database records and enforce branch scope through backend
permissions. P2 strengthens this to shared company + branch ScopeContext enforcement.

```text
GET /api/dashboard/overview
GET /api/dashboard/sales
GET /api/dashboard/inventory
GET /api/dashboard/purchase-orders
```

KPI definitions:

- Revenue: sale item line totals after discounts.
- Gross profit: revenue minus product unit cost for sold quantities.
- Gross margin percent: gross profit divided by revenue.
- Stock value: quantity on hand multiplied by unit cost.
- Low-stock count: product-branch inventory rows at or below reorder threshold.
- Slow-moving stock: stock on hand with no sales in the selected dashboard period.

## Reorder Recommendation Endpoints

Reorder recommendations combine current stock, recent average daily sales, target stock,
supplier lead time, and reorder threshold priority.

```text
GET  /api/inventory/reorder-recommendations
POST /api/purchase-orders/from-recommendations
```

Formula:

```text
suggested reorder quantity = target stock level - current quantity on hand + expected demand during supplier lead time
expected demand during lead time = average daily sales * supplier lead time days
```

Suggested quantity is clamped to zero or above. Draft purchase order creation groups selected
recommendations by supplier and branch, keeps inventory unchanged, and writes audit logs.

## Purchase Order Workflow Endpoints

```text
GET  /api/purchase-orders
POST /api/purchase-orders
GET  /api/purchase-orders/{id}
PUT  /api/purchase-orders/{id}
POST /api/purchase-orders/{id}/submit
POST /api/purchase-orders/{id}/approve
POST /api/purchase-orders/{id}/cancel
POST /api/purchase-orders/{id}/mark-ordered
POST /api/purchase-orders/{id}/receive
```

Draft creation and editing do not increase available stock. Marking an approved order as ordered
adds remaining quantities to `inventory.quantity_on_order`. Receiving an ordered purchase order
increases `quantity_on_hand`, reduces `quantity_on_order`, writes `purchase_received` stock
movements, and audit logs the action. Approval is admin-only.

## Forecasting Endpoints

```text
POST /api/forecasts/run
GET  /api/forecasts
GET  /api/forecasts/products/{product_id}
```

Forecasts use a moving-average baseline plus a simple trend adjustment from historical sales.
Supported horizons are 7, 30, and 90 days. Forecast runs store the horizon total in the
`forecasts` table and return chart-ready historical and forecast points. If a product, branch, or
category does not have enough history, the API returns a clear insufficient-data response instead
of failing.

## AI Assistant Endpoints

```text
POST /api/ai/chat
GET  /api/ai/sessions
GET  /api/ai/sessions/{session_id}
```

The assistant routes common retail questions to safe backend tools:

- `get_sales_summary`
- `get_low_stock_items`
- `get_top_products`
- `get_slow_moving_products`
- `get_pending_purchase_orders`
- `get_reorder_recommendations`
- `get_forecast_summary`

Chat sessions and messages are stored in the local database. Reporting roles can use the assistant,
while Staff is denied by backend role checks. Answers use real service/database outputs; write-like
requests return a confirmation-required response and do not execute operational changes.

Set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` to enable language-response formatting. Without
an API key, deterministic tool-backed responses are returned.

## Export And Power BI Endpoints

Power BI support uses local reporting views plus authenticated CSV export endpoints. Staff users are
denied export access; Admin, Store Manager, and Analyst users are scoped by backend permissions.

```text
GET /api/exports/sales
GET /api/exports/inventory
GET /api/exports/purchase-orders
GET /api/exports/forecasts
```

Reporting views created by Alembic:

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

Run `alembic upgrade head` after pulling this part so Power BI Desktop can connect to the local
PostgreSQL views. The frontend Power BI Reports page links setup instructions and exposes CSV
download buttons.

## Tests

```powershell
python -m pytest
```
