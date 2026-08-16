# Product Requirements Document

## Project Name

AI-Powered Hybrid Retail Inventory, Sales Analytics, and Remote Order Management System

## Short Name

Hybrid Retail BI and Order Management System

## Document Purpose

This PRD defines the complete project scope, business logic, user flows, technical architecture, data model, dashboard requirements, AI assistant behavior, and implementation expectations for building the system.

It is written for two audiences:

- The project owner/student, to understand the complete product clearly.
- An AI coding agent or developer, to build the product without missing key requirements.

## 1. Product Summary

The product is a cost-optimized business intelligence and inventory management system for small and medium retail businesses. It stores operational data locally to reduce cloud cost while allowing an admin to remotely access a secure web dashboard for monitoring stock, sales, purchase orders, suppliers, forecasts, and business performance.

The system combines:

- Local SQL database storage
- Remote web-based admin dashboard
- Sales and inventory analytics
- Power BI executive dashboard
- AI chatbot for business questions and automation
- Forecasting for sales and demand planning
- Purchase order creation and remote approval
- Low-stock alerts and reorder recommendations
- Full-stack implementation with backend, frontend, database, and optional cloud access layer

The product should feel like a real consulting-style solution for a retail client that wants better visibility, faster decisions, and lower infrastructure cost.

## 2. Business Problem

Many small retail businesses track sales, inventory, suppliers, and orders manually or across disconnected spreadsheets. This creates problems such as:

- Admins cannot check stock remotely.
- Store owners do not know which products are selling well.
- Purchase orders are often placed late.
- Low-stock items are missed until customers ask for them.
- Slow-moving inventory blocks money.
- Sales summaries take manual effort.
- Cloud systems may be too expensive for small businesses.
- Business decisions are made without clear dashboards or forecasts.

This product solves these problems by offering a hybrid local-first system with remote dashboard access and business analytics.

## 3. Product Vision

Build a practical business platform where a retail admin can open a web dashboard from anywhere, check current stock, review sales performance, get reorder suggestions, ask an AI assistant business questions, and place or approve purchase orders remotely while keeping the main database locally hosted to reduce cloud cost.

## 4. Product Goals

### Business Goals

- Help retail admins monitor business performance remotely.
- Reduce stockouts through low-stock alerts and reorder suggestions.
- Improve purchase decisions using sales trends and demand forecasts.
- Reduce dependence on expensive cloud databases.
- Present the project as a consulting-friendly business technology solution.

### User Goals

- Admin can view real-time or near-real-time stock remotely.
- Admin can view sales summaries by day, week, month, product, category, and branch.
- Admin can identify top-selling and slow-moving products.
- Admin can create purchase orders from the dashboard.
- Admin can ask the AI assistant questions about sales, stock, suppliers, and orders.
- Store staff can enter or upload sales and stock data locally.

### Technical Goals

- Store all core business data in a local SQL database.
- Provide web dashboard access through a backend API.
- Keep cloud usage minimal.
- Support Power BI reporting.
- Support forecasting and AI assistant features.
- Keep the architecture simple enough for a portfolio project but realistic enough for business use.

## 5. Non-Goals

The first version should not try to become a complete enterprise ERP.

Out of scope for MVP:

- Online customer shopping website
- Payment gateway integration
- Barcode scanner hardware integration
- Accounting software integration
- Payroll management
- Multi-country tax handling
- Advanced warehouse route optimization
- Native mobile apps
- Fully hosted cloud database as the default architecture

These can be future enhancements after the main system is complete.

## 6. Target Users

### Primary User: Business Admin / Owner

The admin owns or manages the retail business. They need remote access to sales, stock, suppliers, and order decisions.

Needs:

- Check stock remotely.
- Review sales performance.
- Approve or place purchase orders.
- See alerts and forecasts.
- Ask natural-language business questions.

### Secondary User: Store Manager

The store manager handles daily operations at a store or branch.

Needs:

- Update stock.
- Enter sales records.
- Review low-stock items.
- Create purchase order requests.
- Track local branch performance.

### Secondary User: Staff / Data Entry User

The staff user enters daily sales and stock updates.

Needs:

- Add sales records.
- Update inventory counts.
- Import CSV data.
- Avoid complex dashboard/admin controls.

### Optional User: Consultant / Analyst

The consultant or analyst uses the system to demonstrate business insights.

Needs:

- View Power BI reports.
- Analyze KPIs.
- Export summaries.
- Present recommendations.

## 7. User Roles and Permissions

### Admin

Admin can:

- View all dashboards.
- Manage products, categories, suppliers, and branches.
- View all sales and stock data.
- Create, approve, reject, and close purchase orders.
- View forecasts and AI insights.
- Configure alert thresholds.
- Export data.
- Manage users and roles.

### Store Manager

Store manager can:

- View assigned branch dashboard.
- Add and edit sales records for assigned branch.
- Update stock for assigned branch.
- Create purchase order requests.
- View low-stock alerts for assigned branch.
- View limited forecasts for assigned branch.

### Staff

Staff can:

- Add sales data.
- Update stock counts if permitted.
- Upload CSV files if permitted.
- View simple confirmation screens.

### Analyst

Analyst can:

- View dashboards and Power BI reports.
- Export reports.
- View forecasts.
- Cannot create orders unless given permission.

## 8. High-Level Product Scope

The system must include these major modules:

1. Authentication and role-based access
2. Product and category management
3. Local SQL database storage
4. Inventory and stock tracking
5. Sales recording and sales summaries
6. Supplier/vendor management
7. Purchase order creation and remote approval
8. Low-stock alerts and reorder recommendations
9. Forecasting and demand prediction
10. AI chatbot for business automation
11. Power BI dashboard/report support
12. Remote admin web dashboard
13. Reports, exports, and audit logs
14. Backup and restore support

## 9. Core User Journeys

### Journey 1: Admin Checks Stock Remotely

1. Admin opens the remote dashboard URL.
2. Admin logs in securely.
3. Admin lands on the overview dashboard.
4. Admin opens the Inventory page.
5. Admin filters by branch, category, or product.
6. Admin views current stock, stock value, low-stock items, and reorder suggestions.
7. Admin opens a product detail page to view sales history and supplier information.

Expected result:

- Admin can understand stock status without being physically present at the store.

### Journey 2: Admin Reviews Sales Summary

1. Admin logs in.
2. Admin opens Sales Summary.
3. Admin selects date range: today, this week, this month, custom.
4. Admin views total revenue, total profit, units sold, average order value, and sales trend.
5. Admin filters by branch, category, product, or staff.
6. Admin exports summary or opens Power BI report.

Expected result:

- Admin understands business performance quickly.

### Journey 3: System Suggests Reorder Items

1. System checks current stock levels.
2. System compares current stock with reorder threshold and recent sales velocity.
3. System identifies low-stock or fast-moving items.
4. System calculates suggested reorder quantity.
5. Admin sees recommended items on dashboard.
6. Admin converts recommendation into a purchase order.

Expected result:

- Purchase decisions become data-driven.

### Journey 4: Admin Places Purchase Order Remotely

1. Admin opens Low Stock Alerts or Purchase Orders.
2. Admin selects one or more products.
3. System pre-fills supplier, current stock, reorder threshold, suggested quantity, and estimated cost.
4. Admin edits quantity if needed.
5. Admin creates purchase order.
6. Purchase order status becomes Draft or Pending.
7. Admin approves the order.
8. System updates purchase order status and records audit log.

Expected result:

- Admin can place or approve orders remotely.

### Journey 5: Staff Enters Daily Sales

1. Staff logs into the local web app or dashboard.
2. Staff opens Add Sale or uploads CSV.
3. Staff enters products sold, quantity, price, discount, date, and branch.
4. System saves sale records locally.
5. System reduces inventory stock.
6. Dashboard updates summary metrics.

Expected result:

- Sales and stock remain updated in the local database.

### Journey 6: Admin Asks AI Assistant

1. Admin opens AI Assistant.
2. Admin asks: "Which products should I reorder today?"
3. AI assistant queries relevant sales, stock, and supplier data.
4. AI responds with clear recommendations and reasoning.
5. AI may provide a link or action to create a draft purchase order.

Expected result:

- Admin receives business-friendly explanations from data.

## 10. Functional Requirements

### 10.1 Authentication and User Management

Requirement ID: AUTH-001

The system must allow users to log in with email/username and password.

Acceptance criteria:

- User can log in with valid credentials.
- Invalid credentials show a clear error.
- Passwords are stored securely using hashing.
- User session expires after a configurable time.

Requirement ID: AUTH-002

The system must support role-based access control.

Acceptance criteria:

- Admin has full access.
- Store Manager sees only assigned branch data unless configured otherwise.
- Staff has limited data entry access.
- Analyst has read-only reporting access.

Requirement ID: AUTH-003

The system should maintain an audit log for important actions.

Acceptance criteria:

- Login attempts, order creation, order approval, stock updates, product updates, and user changes are logged.
- Logs include user, action, timestamp, and affected record.

### 10.2 Product and Category Management

Requirement ID: PROD-001

The system must allow admins to create, view, update, and deactivate products.

Product fields:

- Product ID
- SKU
- Product name
- Category
- Description
- Unit cost
- Selling price
- Supplier
- Reorder threshold
- Target stock level
- Active/inactive status

Acceptance criteria:

- Admin can add a new product.
- Admin can edit product details.
- Product SKU must be unique.
- Inactive products do not appear in new sales entry by default.

Requirement ID: PROD-002

The system must support product categories.

Acceptance criteria:

- Admin can create and edit categories.
- Products can be filtered by category.
- Dashboard can show sales by category.

### 10.3 Inventory and Stock Tracking

Requirement ID: INV-001

The system must store current stock for each product and branch.

Stock fields:

- Product
- Branch/store
- Quantity on hand
- Quantity reserved, optional
- Quantity on order
- Last updated timestamp

Acceptance criteria:

- Admin can view stock by product, branch, and category.
- Stock updates when sales are recorded.
- Stock updates when purchase orders are received.

Requirement ID: INV-002

The system must support manual stock adjustments.

Adjustment reasons:

- Damage
- Lost item
- Stock count correction
- Return
- Transfer
- Other

Acceptance criteria:

- User can enter adjustment quantity and reason.
- Adjustment is logged.
- Stock quantity changes correctly.

Requirement ID: INV-003

The system must detect low-stock items.

Acceptance criteria:

- Product is marked low-stock when quantity on hand is less than or equal to reorder threshold.
- Low-stock list is visible on dashboard.
- Low-stock items can be filtered by branch, category, and supplier.

### 10.4 Sales Management

Requirement ID: SALES-001

The system must allow sales records to be created manually.

Sales fields:

- Sale ID
- Sale date and time
- Branch
- Product
- Quantity sold
- Unit selling price
- Discount
- Tax, optional
- Total amount
- Staff/user

Acceptance criteria:

- Staff or manager can add a sale.
- Inventory decreases after sale is saved.
- Total amount is calculated correctly.

Requirement ID: SALES-002

The system must allow CSV import for sales data.

Acceptance criteria:

- User can upload CSV in a defined format.
- System validates required columns.
- Invalid rows are shown with error messages.
- Valid rows are inserted into the database.

Requirement ID: SALES-003

The system must show sales summaries.

Sales summaries must include:

- Total revenue
- Gross profit
- Units sold
- Number of transactions
- Average order value
- Sales by product
- Sales by category
- Sales by branch
- Sales trend over time

Acceptance criteria:

- Admin can filter by date range.
- Admin can filter by branch, category, and product.
- Values update based on filters.

### 10.5 Supplier Management

Requirement ID: SUP-001

The system must allow admins to manage suppliers.

Supplier fields:

- Supplier ID
- Supplier name
- Contact person
- Email
- Phone
- Address
- Payment terms
- Lead time in days
- Active/inactive status

Acceptance criteria:

- Admin can create and edit suppliers.
- Products can be linked to suppliers.
- Purchase orders can be grouped by supplier.

### 10.6 Purchase Order Management

Requirement ID: PO-001

The system must allow admins and permitted managers to create purchase orders.

Purchase order fields:

- Purchase order ID
- Supplier
- Branch
- Order date
- Expected delivery date
- Status
- Line items
- Total estimated cost
- Created by
- Approved by

Line item fields:

- Product
- Quantity ordered
- Unit cost
- Line total

Acceptance criteria:

- User can create purchase order manually.
- User can create purchase order from reorder recommendations.
- Purchase order status starts as Draft or Pending Approval.

Requirement ID: PO-002

The system must support purchase order statuses.

Statuses:

- Draft
- Pending Approval
- Approved
- Ordered
- Partially Received
- Received
- Cancelled

Acceptance criteria:

- Admin can approve or reject pending orders.
- Receiving stock updates inventory.
- Cancelled orders do not update stock.

Requirement ID: PO-003

The system must support remote order placement and approval.

Acceptance criteria:

- Admin can access purchase orders from the remote dashboard.
- Admin can create, approve, or cancel purchase orders remotely.
- All remote actions are audit logged.

### 10.7 Reorder Recommendation Engine

Requirement ID: REORDER-001

The system must calculate reorder recommendations.

Basic formula:

Suggested reorder quantity = target stock level - current quantity on hand + expected demand during supplier lead time

Expected demand during lead time can be calculated using average daily sales multiplied by supplier lead time.

Acceptance criteria:

- System shows suggested reorder quantity for low-stock products.
- Suggested quantity is never negative.
- Admin can override suggested quantity.

Requirement ID: REORDER-002

The system must identify priority items.

Priority levels:

- Critical: stock is zero or expected to run out before supplier lead time
- High: stock is below reorder threshold
- Medium: stock is near reorder threshold
- Low: stock is healthy

Acceptance criteria:

- Dashboard shows priority badges.
- Admin can sort by priority.

### 10.8 Dashboard and Analytics

Requirement ID: DASH-001

The system must provide an Overview Dashboard.

Overview dashboard cards:

- Total revenue
- Gross profit
- Units sold
- Current stock value
- Low-stock products count
- Pending purchase orders
- Top-selling product
- Forecasted next period sales

Charts:

- Sales trend line chart
- Revenue by category bar chart
- Top products table
- Low-stock table
- Branch performance chart

Acceptance criteria:

- Dashboard loads after login.
- Metrics update based on selected date range and filters.
- Dashboard is responsive for desktop and tablet.

Requirement ID: DASH-002

The system must provide an Inventory Dashboard.

Inventory dashboard must include:

- Product stock table
- Low-stock alerts
- Stock value by category
- Dead stock or slow-moving stock
- Stock movement history
- Products on order

Acceptance criteria:

- Admin can search products.
- Admin can filter by branch, category, supplier, and low-stock status.

Requirement ID: DASH-003

The system must provide a Sales Dashboard.

Sales dashboard must include:

- Revenue trend
- Profit trend
- Units sold trend
- Sales by product
- Sales by category
- Sales by branch
- Best-selling products
- Slow-selling products

Acceptance criteria:

- Admin can compare current period vs previous period.
- Dashboard shows percentage change.

Requirement ID: DASH-004

The system must provide a Purchase Orders Dashboard.

Purchase order dashboard must include:

- Pending orders
- Approved orders
- Overdue expected deliveries
- Orders by supplier
- Total order value
- Recently received orders

Acceptance criteria:

- Admin can open order details.
- Admin can approve, cancel, or mark received depending on role.

### 10.9 Forecasting and Demand Prediction

Requirement ID: FORECAST-001

The system must forecast future sales using historical sales data.

Forecast dimensions:

- Product-level forecast
- Category-level forecast
- Branch-level forecast
- Overall revenue forecast

Acceptance criteria:

- Admin can select forecast horizon, such as 7 days, 30 days, or 90 days.
- System shows forecasted demand and confidence indicators if available.
- Forecast output is stored or cached for dashboard use.

Requirement ID: FORECAST-002

The forecasting model must be explainable at a basic business level.

Acceptance criteria:

- System shows historical trend used for forecast.
- System shows whether sales are increasing, decreasing, or stable.
- AI assistant can summarize forecast meaning in plain language.

Suggested tools:

- Python
- pandas
- scikit-learn
- statsmodels
- Prophet, optional

### 10.10 AI Chatbot for Business Automation

Requirement ID: AI-001

The system must include an AI assistant accessible from the admin dashboard.

The assistant should answer questions about:

- Current stock
- Low-stock items
- Sales summaries
- Product performance
- Supplier details
- Purchase orders
- Forecasts
- Reorder suggestions

Acceptance criteria:

- Admin can type a business question.
- Assistant responds with data-based answers.
- Assistant does not invent numbers if data is missing.
- Assistant clearly states when it cannot answer due to missing data.

Requirement ID: AI-002

The AI assistant must support business action suggestions.

Example actions:

- Suggest products to reorder.
- Suggest purchase order draft.
- Summarize monthly sales.
- Explain why revenue changed.
- Identify slow-moving products.

Acceptance criteria:

- Assistant can provide recommendations with reasoning.
- Assistant asks for confirmation before creating or changing important records.
- Assistant does not approve orders automatically unless explicitly confirmed by an authorized admin.

Requirement ID: AI-003

The AI assistant must follow safety and data rules.

Rules:

- Do not expose data to unauthorized roles.
- Do not claim certainty for forecasts.
- Do not delete records.
- Do not modify stock or orders without confirmation.
- Do not make up supplier, sales, or stock values.
- Always use retrieved database values when answering numerical questions.

### 10.11 Power BI Integration

Requirement ID: PBI-001

The project must include Power BI reporting support.

Accepted approaches:

- Power BI Desktop connects directly to local SQL database.
- Power BI imports exported CSV files.
- Power BI connects to a read-only reporting view.

Acceptance criteria:

- Power BI report can show sales, inventory, and order KPIs.
- Report can be refreshed from local data.
- Report includes executive dashboard pages.

Recommended Power BI pages:

- Executive Overview
- Sales Performance
- Inventory Health
- Supplier and Purchase Orders
- Forecast and Recommendations

### 10.12 Reports and Exports

Requirement ID: REP-001

The system must allow exports.

Export formats:

- CSV
- Excel, optional
- PDF, optional

Exportable data:

- Sales summary
- Inventory list
- Low-stock list
- Purchase orders
- Supplier list
- Forecast output

Acceptance criteria:

- Admin can export filtered data.
- Exported data matches dashboard filters.

### 10.13 Remote Access and Hybrid Local Storage

Requirement ID: REMOTE-001

The system must store the main database locally.

Acceptance criteria:

- Core data remains in local PostgreSQL, MySQL, or SQL Server Express.
- The system does not require a paid cloud database for MVP.

Requirement ID: REMOTE-002

The system must support remote dashboard access.

Accepted options:

- Cloudflare Tunnel
- Tailscale
- ngrok for demo use
- Lightweight VPS reverse proxy, optional

Acceptance criteria:

- Admin can open the dashboard remotely.
- Remote access reaches the local backend securely.
- Public access must require authentication.

Requirement ID: REMOTE-003

The remote dashboard must not expose the database directly.

Acceptance criteria:

- Browser talks to backend API.
- Backend talks to local database.
- Database port is not publicly exposed.

### 10.14 Backup and Restore

Requirement ID: BACKUP-001

The system should support local database backups.

Acceptance criteria:

- Admin can trigger or schedule backup, or documentation explains backup command.
- Backup file includes all business data.
- Restore process is documented.

Recommended approach:

- PostgreSQL pg_dump for backups
- Scheduled local backup folder
- Optional encrypted external backup

## 11. Data Model

The implementation may adjust field names, but the following entities should be represented.

### users

- id
- name
- email
- password_hash
- role
- branch_id, nullable
- is_active
- created_at
- updated_at

### branches

- id
- name
- address
- city
- manager_name
- is_active
- created_at
- updated_at

### categories

- id
- name
- description
- created_at
- updated_at

### suppliers

- id
- name
- contact_person
- email
- phone
- address
- payment_terms
- lead_time_days
- is_active
- created_at
- updated_at

### products

- id
- sku
- name
- description
- category_id
- supplier_id
- unit_cost
- selling_price
- reorder_threshold
- target_stock_level
- is_active
- created_at
- updated_at

### inventory

- id
- product_id
- branch_id
- quantity_on_hand
- quantity_reserved
- quantity_on_order
- last_updated_at

### stock_movements

- id
- product_id
- branch_id
- movement_type
- quantity_change
- reason
- reference_type
- reference_id
- created_by
- created_at

Movement types:

- sale
- purchase_received
- manual_adjustment
- return
- transfer

### sales

- id
- sale_number
- branch_id
- sale_datetime
- subtotal
- discount_total
- tax_total
- total_amount
- created_by
- created_at

### sale_items

- id
- sale_id
- product_id
- quantity
- unit_price
- discount_amount
- line_total

### purchase_orders

- id
- po_number
- supplier_id
- branch_id
- status
- order_date
- expected_delivery_date
- total_amount
- created_by
- approved_by
- approved_at
- created_at
- updated_at

### purchase_order_items

- id
- purchase_order_id
- product_id
- quantity_ordered
- quantity_received
- unit_cost
- line_total

### forecasts

- id
- product_id, nullable
- category_id, nullable
- branch_id, nullable
- forecast_type
- forecast_start_date
- forecast_end_date
- forecast_value
- confidence_low, optional
- confidence_high, optional
- model_name
- created_at

### ai_chat_sessions

- id
- user_id
- title
- created_at
- updated_at

### ai_chat_messages

- id
- session_id
- sender
- message
- metadata_json
- created_at

### audit_logs

- id
- user_id
- action
- entity_type
- entity_id
- old_value_json
- new_value_json
- ip_address
- created_at

## 12. Key Metrics and KPI Definitions

### Revenue

Revenue = sum of sale item line totals after discounts.

### Gross Profit

Gross profit = revenue - cost of goods sold.

Cost of goods sold = quantity sold * product unit cost.

### Gross Margin Percent

Gross margin percent = gross profit / revenue * 100.

### Units Sold

Units sold = sum of all sale item quantities.

### Average Order Value

Average order value = total revenue / number of sales.

### Stock Value

Stock value = quantity on hand * unit cost.

### Low-Stock Count

Low-stock count = number of active products where quantity on hand <= reorder threshold.

### Sales Growth Percent

Sales growth percent = (current period revenue - previous period revenue) / previous period revenue * 100.

### Inventory Turnover

Inventory turnover = cost of goods sold / average inventory value.

### Dead or Slow-Moving Stock

A product can be considered slow-moving if it has stock on hand but no sales in the selected period, such as the last 30, 60, or 90 days.

## 13. Dashboard Pages

### Page 1: Overview

Purpose:

Give admin a quick executive view of business health.

Must show:

- Total revenue
- Gross profit
- Units sold
- Average order value
- Current stock value
- Low-stock products count
- Pending purchase orders
- Sales trend
- Top-selling products
- Critical low-stock items

### Page 2: Sales Summary

Purpose:

Analyze sales performance.

Must show:

- Daily, weekly, monthly sales
- Sales by product
- Sales by category
- Sales by branch
- Profit trend
- Product ranking
- Comparison to previous period

### Page 3: Inventory and Stock

Purpose:

Manage stock remotely.

Must show:

- Product stock table
- Current stock by branch
- Low-stock alerts
- Stock value
- Reorder threshold
- Target stock level
- Quantity on order
- Last updated time

Actions:

- Search product
- Filter products
- View product details
- Create purchase order from product
- Adjust stock if role allows

### Page 4: Low-Stock and Reorder

Purpose:

Help admin decide what to order.

Must show:

- Critical stock items
- Suggested reorder quantity
- Supplier
- Supplier lead time
- Average daily sales
- Estimated runout date
- Priority level

Actions:

- Select products
- Generate purchase order draft
- Send for approval
- Approve purchase order

### Page 5: Purchase Orders

Purpose:

Manage purchasing workflow.

Must show:

- Purchase order list
- Status
- Supplier
- Branch
- Total amount
- Expected delivery date
- Created by
- Approved by

Actions:

- Create order
- Edit draft
- Approve
- Cancel
- Mark ordered
- Mark partially received
- Mark received

### Page 6: Suppliers

Purpose:

Track vendors and purchasing relationships.

Must show:

- Supplier list
- Contact details
- Lead time
- Linked products
- Total orders
- Pending orders

### Page 7: Forecasting

Purpose:

Predict future demand and sales.

Must show:

- Forecast chart
- Historical sales trend
- Forecast horizon selector
- Forecast by product/category/branch
- Demand recommendation

### Page 8: AI Assistant

Purpose:

Let admin ask business questions naturally.

Must support:

- Chat interface
- Suggested question buttons
- Data-backed answers
- Links to relevant dashboard pages
- Confirmation before creating records

### Page 9: Power BI Reports

Purpose:

Provide executive-level BI reporting.

Options:

- Embed Power BI report if available.
- Link to Power BI file.
- Show exported report snapshots.
- Provide instructions for refreshing Power BI Desktop.

### Page 10: Settings

Purpose:

Configure system.

Must include:

- User management
- Branch management
- Alert thresholds
- Backup settings
- AI settings
- Remote access status, optional

## 14. AI Assistant Behavior Specification

The AI assistant must behave like a business analyst for the retail admin.

### Assistant Capabilities

The assistant should answer:

- "What are today's sales?"
- "Which products are low in stock?"
- "Which items should I reorder today?"
- "What are the top-selling products this month?"
- "Which branch performed best?"
- "Which products are slow-moving?"
- "Summarize pending purchase orders."
- "Forecast next week's demand."
- "Why did sales drop compared to last month?"

### Data Access Rules

The assistant must retrieve actual values from the database or analytics layer. For numerical questions, it must not guess.

Correct behavior:

- "Total sales today are 42,500 based on 118 transactions."

Incorrect behavior:

- "Sales seem to be around 40,000" when no query was run.

### Action Rules

The assistant may suggest actions, but must ask confirmation before changing data.

Allowed without confirmation:

- Summarize data
- Recommend products to reorder
- Explain sales trends
- Show pending orders

Requires confirmation:

- Create purchase order
- Approve purchase order
- Cancel purchase order
- Adjust stock
- Update product threshold

Forbidden:

- Delete records
- Reveal data outside user's role
- Approve orders for unauthorized users
- Invent missing business data

### AI Response Style

Responses should be:

- Short but useful
- Business-friendly
- Based on data
- Clear about assumptions
- Clear about missing information

Example response:

"You should reorder 4 products today. Milk 1L is critical because only 3 units are left and average daily sales are 12 units. Bread is below threshold with 8 units left. I recommend creating a purchase order for Supplier A with an estimated total cost of 7,800."

## 15. Technical Architecture

### Architecture Type

Hybrid local-first architecture.

Core principle:

Keep the main database local to reduce cloud cost, and expose only the authenticated web dashboard/API for remote admin access.

### Recommended Stack

Frontend:

- React
- TypeScript, recommended
- Tailwind CSS or another consistent UI framework
- Chart library such as Recharts, ECharts, or Chart.js

Backend:

- FastAPI with Python, recommended
- Node.js/Express can also be used

Database:

- PostgreSQL local, recommended
- SQL Server Express or MySQL acceptable

Analytics:

- Python
- pandas
- scikit-learn
- statsmodels or Prophet optional

AI:

- OpenAI API for natural language assistant, optional
- Local LLM can be added later to reduce API cost

BI:

- Power BI Desktop
- Local SQL connection or CSV export

Remote Access:

- Cloudflare Tunnel, recommended
- Tailscale, recommended for private access
- ngrok for demos

Deployment:

- Local machine or local mini server
- Docker optional
- Lightweight cloud only for access layer if required

### Component Flow

1. User opens web dashboard in browser.
2. Browser sends request to backend API.
3. Backend authenticates user.
4. Backend queries local SQL database.
5. Backend returns dashboard data to frontend.
6. Forecasting service reads historical sales data and writes forecast output.
7. AI assistant uses safe tools/API routes to retrieve business data.
8. Power BI connects to local database or exported reporting files.
9. Remote access tool exposes frontend/backend securely without exposing database directly.

### Remote Access Options

Option A: Cloudflare Tunnel

- Best for demo and low-cost remote access.
- Public URL can point to local app.
- Requires authentication in the app.

Option B: Tailscale

- Best for private remote access.
- Only authorized devices can access dashboard.

Option C: ngrok

- Best for temporary demos.
- Not ideal for permanent production use.

## 16. API Requirements

The backend should provide REST API endpoints. GraphQL is optional but not required.

### Auth APIs

- POST /auth/login
- POST /auth/logout
- GET /auth/me

### Product APIs

- GET /products
- POST /products
- GET /products/{id}
- PUT /products/{id}
- PATCH /products/{id}/deactivate

### Inventory APIs

- GET /inventory
- GET /inventory/low-stock
- POST /inventory/adjustments
- GET /inventory/movements

### Sales APIs

- GET /sales
- POST /sales
- POST /sales/import
- GET /sales/summary
- GET /sales/trends

### Supplier APIs

- GET /suppliers
- POST /suppliers
- GET /suppliers/{id}
- PUT /suppliers/{id}

### Purchase Order APIs

- GET /purchase-orders
- POST /purchase-orders
- GET /purchase-orders/{id}
- PUT /purchase-orders/{id}
- POST /purchase-orders/{id}/submit
- POST /purchase-orders/{id}/approve
- POST /purchase-orders/{id}/cancel
- POST /purchase-orders/{id}/receive

### Forecast APIs

- GET /forecasts
- POST /forecasts/run
- GET /forecasts/products/{product_id}

### Dashboard APIs

- GET /dashboard/overview
- GET /dashboard/sales
- GET /dashboard/inventory
- GET /dashboard/purchase-orders

### AI Assistant APIs

- POST /ai/chat
- GET /ai/sessions
- GET /ai/sessions/{id}

### Export APIs

- GET /exports/sales
- GET /exports/inventory
- GET /exports/purchase-orders

## 17. Non-Functional Requirements

### Security

- Passwords must be hashed.
- Database must not be exposed publicly.
- Remote dashboard must require login.
- Role-based permissions must be enforced in backend, not only frontend.
- Important actions must be audit logged.
- API should validate all inputs.

### Performance

- Overview dashboard should load in under 3 seconds for sample project data.
- Tables should support pagination or search.
- Dashboard queries should use indexes or optimized SQL views.

### Reliability

- Local database should support backup.
- System should handle backend restart without data loss.
- Errors should be logged.

### Usability

- Dashboard should be easy to understand for non-technical business users.
- Admin should see key metrics immediately after login.
- Tables should support search and filters.
- Important actions should show confirmation messages.

### Maintainability

- Code should be modular.
- Business logic should not be duplicated across frontend and backend.
- Database schema should use clear relationships.
- API names should be consistent.

### Cost Optimization

- Main database remains local.
- Cloud database is not required for MVP.
- Remote access uses low-cost tools.
- AI API usage should be limited to assistant requests, not every dashboard load.

## 18. MVP Scope

The MVP must include:

1. User login with Admin and Staff roles
2. Local SQL database
3. Product and category management
4. Supplier management
5. Inventory tracking
6. Manual sales entry
7. Sales summary dashboard
8. Inventory dashboard
9. Low-stock alerts
10. Basic reorder suggestion
11. Purchase order creation and approval
12. Remote dashboard access setup documentation
13. Basic forecasting for sales or demand
14. AI assistant for read-only business questions
15. Power BI report connected to local data or sample export

## 19. Version 1 Enhancements

After MVP:

- CSV sales import
- More roles and branch permissions
- AI-assisted purchase order draft creation
- Forecasting by product and branch
- Power BI report polish
- Backup and restore UI
- Audit log viewer
- Export to Excel/PDF
- Better reorder algorithm using sales velocity and supplier lead time

## 20. Future Enhancements

Possible future features:

- Barcode scanner integration
- WhatsApp/email purchase order sending
- Customer management
- Returns management
- Mobile app
- Cloud sync backup
- Multi-store synchronization
- Accounting integration
- Supplier performance scoring
- Demand forecasting with seasonal patterns
- Local LLM for lower AI cost

## 21. Implementation Roadmap

### Phase 1: Foundation

- Set up repo structure.
- Choose stack.
- Create database schema.
- Add seed/sample retail data.
- Build authentication.
- Build basic frontend layout.

### Phase 2: Core Operations

- Product management.
- Supplier management.
- Inventory tracking.
- Sales entry.
- Stock movement logic.

### Phase 3: Dashboards

- Overview dashboard.
- Sales summary dashboard.
- Inventory dashboard.
- Low-stock alerts.
- Filters and search.

### Phase 4: Purchase Orders

- Purchase order creation.
- Approval workflow.
- Receive order workflow.
- Stock update after receiving.

### Phase 5: Analytics and Forecasting

- Sales trend analysis.
- Forecasting model.
- Reorder recommendation engine.
- Forecast dashboard.

### Phase 6: AI Assistant

- Chat UI.
- Backend AI endpoint.
- Safe data retrieval tools.
- Business question answering.
- Confirmation flow for actions.

### Phase 7: Power BI and Reporting

- Create reporting views or export files.
- Build Power BI dashboard.
- Document refresh process.

### Phase 8: Remote Access and Final Polish

- Configure Cloudflare Tunnel, Tailscale, or ngrok.
- Document local setup.
- Add backup guidance.
- Test full workflow.
- Prepare README and portfolio case study.

## 22. Testing Requirements

### Functional Tests

Test:

- Login works.
- Role permissions work.
- Product creation works.
- Sales entry reduces stock.
- Stock adjustment changes inventory.
- Low-stock alert appears correctly.
- Reorder suggestion calculates correctly.
- Purchase order creation works.
- Purchase order receiving increases stock.
- Dashboard filters work.

### AI Assistant Tests

Test:

- Assistant answers sales summary from database.
- Assistant answers low-stock questions from database.
- Assistant refuses or asks confirmation for write actions.
- Assistant does not invent values when data is missing.

### Forecasting Tests

Test:

- Forecast runs with sample historical data.
- Forecast output appears in dashboard.
- Forecast handles insufficient data gracefully.

### Security Tests

Test:

- Staff cannot access admin settings.
- Unauthenticated user cannot access API data.
- Database is not publicly exposed.
- Unauthorized user cannot approve purchase orders.

### Remote Access Tests

Test:

- Admin can access dashboard remotely.
- Login is required remotely.
- Dashboard API works through tunnel.
- Database port remains private.

## 23. Sample Data Requirements

The project should include sample data so dashboards look realistic.

Recommended sample dataset:

- 2 to 3 branches
- 5 to 8 categories
- 50 to 100 products
- 8 to 15 suppliers
- 6 to 12 months of sales history
- Inventory levels for all products
- 20 to 50 purchase orders
- Some low-stock products
- Some slow-moving products
- Some high-demand products

Example categories:

- Grocery
- Beverages
- Personal Care
- Household
- Snacks
- Dairy
- Stationery

## 24. Portfolio Deliverables

The final project should include:

- Working full-stack application
- Local SQL database schema
- Sample data
- Power BI dashboard file or screenshots
- Forecasting notebook or backend module
- AI assistant demo
- README with setup instructions
- Architecture diagram
- Business case study
- Screenshots of dashboard
- Explanation of cost-optimized hybrid design

## 25. Business Case Study Structure

The portfolio should present the project like a consulting case.

Recommended sections:

1. Client problem
2. Existing pain points
3. Proposed solution
4. Architecture
5. Key features
6. Business KPIs tracked
7. Dashboard screenshots
8. Forecasting and reorder logic
9. AI assistant examples
10. Cost optimization strategy
11. Expected business impact

Expected business impact examples:

- Faster stock visibility for admin
- Reduced stockout risk
- Better purchase planning
- Lower cloud infrastructure cost
- Faster weekly/monthly reporting
- Better sales and inventory decisions

## 26. AI Coding Agent Instructions

An AI coding agent building this project must follow these instructions:

1. Build the system as a hybrid local-first retail management platform.
2. Keep the main database local.
3. Do not design the default architecture around a paid cloud database.
4. Build a web dashboard for remote admin access.
5. Ensure the database is accessed only through backend APIs.
6. Implement authentication and backend role enforcement.
7. Include sales, inventory, suppliers, purchase orders, dashboards, forecasting, AI assistant, and Power BI support.
8. Keep MVP realistic and complete before adding advanced features.
9. Use sample data so dashboards are meaningful.
10. Make dashboards business-friendly, not just technical.
11. Use clear database relationships.
12. Avoid hardcoding business metrics in frontend only.
13. All important calculations should be in backend services, SQL views, or analytics modules.
14. The AI assistant must use retrieved data and must not invent numerical answers.
15. The AI assistant must ask confirmation before creating or modifying purchase orders, stock, or other business records.
16. Include documentation for local setup, database setup, Power BI connection, and remote access.

## 27. Recommended Final Resume Description

AI-Powered Hybrid Business Intelligence Platform for Retail Inventory, Sales Forecasting, and Remote Order Management

Built a cost-optimized full-stack retail management system with local SQL storage, remote admin dashboard, Power BI reporting, AI business assistant, sales forecasting, low-stock alerts, and purchase order automation. Designed a hybrid architecture to reduce cloud database cost while enabling secure remote access for business admins.

## 28. Completion Definition

The project is complete when:

- Admin can log in remotely.
- Admin can view stock and sales dashboards.
- Stock data is stored locally.
- Sales entries update inventory.
- Low-stock alerts appear correctly.
- Admin can create and approve purchase orders.
- Reorder suggestions are generated.
- Forecasting output is available.
- AI assistant answers business questions using real data.
- Power BI dashboard/report is available.
- Documentation explains setup, architecture, and business value.

