import type { PageAction, PageMetric, RouteKey, TableColumn, TableRow, UserRole } from "../types";
import { canCreateOperationalRecords } from "../navigation";

export type DashboardRouteKey = Exclude<RouteKey, "products" | "customers" | "pos" | "suppliers" | "categories" | "branches">;

type PageDefinition = {
  eyebrow: string;
  title: string;
  description: string;
  metrics: PageMetric[];
  filters: string[];
  columns: TableColumn[];
  rows: TableRow[];
  actions: (role: UserRole) => PageAction[];
  emptyTitle: string;
  emptyMessage: string;
};

const pendingMetric: PageMetric = {
  label: "Connected KPI",
  value: "Awaiting API",
  detail: "This card will use backend calculations in the dashboard services part.",
  tone: "slate",
};

export const PAGE_DEFINITIONS: Record<DashboardRouteKey, PageDefinition> = {
  overview: {
    eyebrow: "Executive view",
    title: "Overview dashboard",
    description:
      "Monitor revenue, profit, stock health, pending orders, and branch performance from one operational screen.",
    metrics: [
      { label: "Total Revenue", value: "Awaiting API", detail: "From sales summary endpoint", tone: "green" },
      { label: "Stock Value", value: "Awaiting API", detail: "From inventory valuation", tone: "blue" },
      { label: "Low-Stock Items", value: "Awaiting API", detail: "From reorder service", tone: "amber" },
      { label: "Pending Orders", value: "Awaiting API", detail: "From purchase order workflow", tone: "rose" },
    ],
    filters: ["Date range", "Branch", "Category"],
    columns: [
      { key: "metric", label: "Focus Area" },
      { key: "source", label: "Data Source" },
      { key: "status", label: "Build Status" },
    ],
    rows: [
      { metric: "Sales trend", source: "sales, sale_items", status: "Dashboard service pending" },
      { metric: "Inventory health", source: "inventory, products", status: "Inventory API pending" },
      { metric: "Order queue", source: "purchase_orders", status: "Workflow API ready" },
    ],
    actions: () => [{ label: "Refresh", tone: "secondary" }],
    emptyTitle: "Dashboard data is not connected yet",
    emptyMessage: "The shell is ready; KPI endpoints will fill this area in the dashboard slice.",
  },
  sales: {
    eyebrow: "Sales operations",
    title: "Sales summary",
    description:
      "Review revenue, units sold, average order value, product ranking, and branch performance.",
    metrics: [
      { label: "Revenue", value: "Awaiting API", detail: "Selected date range", tone: "green" },
      { label: "Gross Profit", value: "Awaiting API", detail: "Revenue minus cost", tone: "blue" },
      { label: "Units Sold", value: "Awaiting API", detail: "Sale item quantities", tone: "amber" },
      { label: "Average Order Value", value: "Awaiting API", detail: "Revenue per sale", tone: "slate" },
    ],
    filters: ["Date range", "Branch", "Product", "Staff"],
    columns: [
      { key: "view", label: "View" },
      { key: "scope", label: "Scope" },
      { key: "next", label: "Next Build Step" },
    ],
    rows: [
      { view: "Daily sales", scope: "Branch and staff", next: "Sales engine API" },
      { view: "Top products", scope: "Product and category", next: "Sales ranking query" },
      { view: "Profit trend", scope: "Time series", next: "Dashboard service" },
    ],
    actions: (role) =>
      canCreateOperationalRecords(role)
        ? [
            { label: "Add Sale", tone: "primary" },
            { label: "Import CSV", tone: "secondary" },
          ]
        : [{ label: "Export Summary", tone: "secondary" }],
    emptyTitle: "No sales rows loaded",
    emptyMessage: "Sales tables are seeded; API endpoints will connect this view next.",
  },
  inventory: {
    eyebrow: "Remote stock control",
    title: "Inventory",
    description:
      "Track current stock by product and branch, stock value, movement history, and items already on order.",
    metrics: [
      { label: "Stock On Hand", value: "Awaiting API", detail: "Product by branch inventory", tone: "blue" },
      { label: "Reserved Stock", value: "Awaiting API", detail: "Reserved quantities", tone: "slate" },
      { label: "On Order", value: "Awaiting API", detail: "Open purchase orders", tone: "amber" },
      { label: "Stock Value", value: "Awaiting API", detail: "Quantity times unit cost", tone: "green" },
    ],
    filters: ["Search product", "Branch", "Category", "Supplier", "Low-stock only"],
    columns: [
      { key: "view", label: "View" },
      { key: "rule", label: "Business Rule" },
      { key: "next", label: "Next Build Step" },
    ],
    rows: [
      { view: "Stock table", rule: "Inventory is product and branch scoped", next: "Inventory list API" },
      { view: "Movement ledger", rule: "Every stock change creates movement", next: "Movement API" },
      { view: "Adjustment modal", rule: "Reason is required", next: "Adjustment service" },
    ],
    actions: (role) =>
      canCreateOperationalRecords(role)
        ? [{ label: "Adjust Stock", tone: "primary" }]
        : [{ label: "Export Inventory", tone: "secondary" }],
    emptyTitle: "Inventory endpoint pending",
    emptyMessage: "Seed data already has product and branch stock records for this page.",
  },
  "low-stock": {
    eyebrow: "Purchasing signal",
    title: "Low stock and reorder",
    description:
      "Combine current stock, target stock, sales velocity, and supplier lead time to prioritize reorder actions.",
    metrics: [
      { label: "Critical Items", value: "Awaiting API", detail: "Zero or runout risk", tone: "rose" },
      { label: "High Priority", value: "Awaiting API", detail: "Below threshold", tone: "amber" },
      { label: "Supplier Lead Time", value: "Awaiting API", detail: "Average days", tone: "blue" },
      { label: "Suggested Quantity", value: "Awaiting API", detail: "Target plus demand", tone: "green" },
    ],
    filters: ["Priority", "Branch", "Supplier", "Category"],
    columns: [
      { key: "product", label: "Product" },
      { key: "logic", label: "Recommendation Logic" },
      { key: "status", label: "Status" },
    ],
    rows: [
      { product: "Low-stock products", logic: "Quantity <= reorder threshold", status: "Recommendation API ready" },
      { product: "Fast movers", logic: "Sales velocity affects priority", status: "Sales velocity query ready" },
      { product: "Supplier groups", logic: "Order drafts grouped by supplier", status: "Draft PO creation ready" },
    ],
    actions: (role) =>
      role === "analyst"
        ? [{ label: "Export Recommendations", tone: "secondary" }]
        : [{ label: "Create Order Draft", tone: "primary" }],
    emptyTitle: "No recommendations found",
    emptyMessage: "Adjust filters or seed data to review reorder recommendations.",
  },
  "purchase-orders": {
    eyebrow: "Order workflow",
    title: "Purchase orders",
    description:
      "Manage draft, pending, approved, ordered, partially received, received, and cancelled purchase orders.",
    metrics: [
      { label: "Pending Approval", value: "Connected", detail: "Admin approval queue", tone: "amber" },
      { label: "Ordered", value: "Connected", detail: "Awaiting supplier", tone: "blue" },
      { label: "Overdue", value: "Connected", detail: "Past expected delivery", tone: "rose" },
      { label: "Received", value: "Connected", detail: "Closed receiving flow", tone: "green" },
    ],
    filters: ["Status", "Supplier", "Branch", "Expected delivery"],
    columns: [
      { key: "status", label: "Status" },
      { key: "inventory", label: "Inventory Rule" },
      { key: "audit", label: "Audit Rule" },
    ],
    rows: [
      { status: "Created", inventory: "Does not increase stock", audit: "Log creator and timestamp" },
      { status: "Approved", inventory: "Still not available stock", audit: "Log approval" },
      { status: "Received", inventory: "Increases stock on hand", audit: "Log receipt" },
    ],
    actions: (role) =>
      role === "analyst"
        ? [{ label: "Export Orders", tone: "secondary" }]
        : [
            { label: "New Purchase Order", tone: "primary" },
            { label: "Review Queue", tone: "secondary" },
          ],
    emptyTitle: "No purchase orders found",
    emptyMessage: "Create a draft order or adjust the current filters.",
  },
  forecasting: {
    eyebrow: "Demand planning",
    title: "Forecasting",
    description:
      "Run explainable forecasts from historical sales, starting with moving averages and trend summaries.",
    metrics: [
      { label: "Forecast Horizon", value: "7 to 90 days", detail: "Connected selector", tone: "blue" },
      { label: "Model", value: "Moving average", detail: "MVP approach", tone: "slate" },
      { label: "Trend", value: "Connected", detail: "Increasing, stable, or decreasing", tone: "amber" },
      { label: "Forecasted Demand", value: "Stored", detail: "Saved forecast output", tone: "green" },
    ],
    filters: ["Horizon", "Product", "Category", "Branch"],
    columns: [
      { key: "forecast", label: "Forecast Type" },
      { key: "source", label: "Source Data" },
      { key: "guardrail", label: "Guardrail" },
    ],
    rows: [
      { forecast: "Revenue", source: "sales", guardrail: "Handle insufficient history" },
      { forecast: "Product demand", source: "sale_items", guardrail: "Explain trend" },
      { forecast: "Branch demand", source: "sales by branch", guardrail: "Respect branch scope" },
    ],
    actions: () => [{ label: "Run Forecast", tone: "primary" }],
    emptyTitle: "No forecast selected",
    emptyMessage: "Run a forecast to draw the historical and predicted sales chart.",
  },
  "ai-assistant": {
    eyebrow: "Business assistant",
    title: "AI assistant",
    description:
      "Ask business questions about sales, stock, suppliers, orders, forecasts, and reorder recommendations.",
    metrics: [
      { label: "Mode", value: "Read-only", detail: "No invented numbers", tone: "blue" },
      { label: "Writes", value: "Confirmation", detail: "Required before changes", tone: "amber" },
      { label: "Scope", value: "Role-aware", detail: "Uses backend permissions", tone: "green" },
      { label: "Provider", value: "Configurable", detail: "OpenAI optional", tone: "slate" },
    ],
    filters: ["Question type", "Branch scope", "Data source"],
    columns: [
      { key: "question", label: "Sample Question" },
      { key: "tool", label: "Required Tool" },
      { key: "rule", label: "Guardrail" },
    ],
    rows: [
      { question: "Which products should I reorder today?", tool: "Reorder recommendations", rule: "Use real data" },
      { question: "Summarize this month's sales", tool: "Sales summary", rule: "No guessing" },
      { question: "Create a draft PO", tool: "Purchase order action", rule: "Ask confirmation" },
    ],
    actions: () => [{ label: "Start Chat", tone: "primary" }],
    emptyTitle: "No chat selected",
    emptyMessage: "The connected assistant stores chat history and shows which backend tool answered.",
  },
  "power-bi": {
    eyebrow: "Executive reporting",
    title: "Power BI reports",
    description:
      "Prepare reporting views or CSV exports for Power BI Desktop while operational changes stay inside the web app.",
    metrics: [
      { label: "Data Source", value: "Local SQL", detail: "Default architecture", tone: "blue" },
      { label: "Refresh", value: "Manual", detail: "Power BI Desktop", tone: "slate" },
      { label: "Views", value: "Planned", detail: "Sales, inventory, orders", tone: "amber" },
      { label: "Exports", value: "Planned", detail: "CSV endpoint support", tone: "green" },
    ],
    filters: ["Report page", "Refresh status", "Export type"],
    columns: [
      { key: "report", label: "Report Page" },
      { key: "source", label: "Source" },
      { key: "status", label: "Status" },
    ],
    rows: [
      { report: "Executive Overview", source: "Reporting views", status: "Pending" },
      { report: "Inventory Health", source: "Inventory view", status: "Pending" },
      { report: "Supplier Orders", source: "Purchase order view", status: "Pending" },
    ],
    actions: () => [{ label: "Open Report Guide", tone: "secondary" }],
    emptyTitle: "Power BI assets pending",
    emptyMessage: "This page will link report files, screenshots, and refresh instructions.",
  },
  settings: {
    eyebrow: "Administration",
    title: "Settings",
    description:
      "Manage users, branches, thresholds, backup guidance, AI configuration, and remote access status.",
    metrics: [
      { label: "Users", value: "Admin only", detail: "Role and branch assignment", tone: "blue" },
      { label: "Branches", value: "Admin only", detail: "Store configuration", tone: "green" },
      { label: "Backups", value: "Planned", detail: "Local database safety", tone: "amber" },
      { label: "Remote Access", value: "Planned", detail: "Tunnel setup", tone: "slate" },
    ],
    filters: ["Setting group", "Status", "Access level"],
    columns: [
      { key: "setting", label: "Setting" },
      { key: "access", label: "Access" },
      { key: "next", label: "Next Build Step" },
    ],
    rows: [
      { setting: "User roles", access: "Admin", next: "User management API" },
      { setting: "Branch setup", access: "Admin", next: "Branch CRUD" },
      { setting: "Remote access", access: "Admin", next: "Deployment docs" },
    ],
    actions: () => [{ label: "Manage Users", tone: "primary" }],
    emptyTitle: "Settings APIs pending",
    emptyMessage: "Admin-only configuration screens will connect as modules mature.",
  },
};
