import { useCallback, useMemo, useState } from "react";
import {
  CloudOff,
  Database,
  Download,
  ExternalLink,
  FileSpreadsheet,
  RefreshCw,
  ShieldCheck,
  TableProperties,
} from "lucide-react";

import { ApiError } from "../api/client";
import { downloadExport, type ExportKind } from "../api/exports";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, MetricCard } from "../components/ui";
import type { PageMetric } from "../types";

type ReportingView = {
  name: string;
  source: string;
  recommendedPage: string;
  purpose: string;
};

type ExportAction = {
  kind: ExportKind;
  label: string;
  description: string;
};

const REPORTING_VIEWS: ReportingView[] = [
  {
    name: "vw_sales_summary",
    source: "sales, sale_items, branches",
    recommendedPage: "Executive Overview",
    purpose: "Daily revenue, gross profit, units, transactions, and average order value by branch.",
  },
  {
    name: "vw_sales_by_product",
    source: "sales, products, categories, suppliers",
    recommendedPage: "Sales Performance",
    purpose: "Product-level revenue, units sold, and gross profit for ranking and contribution analysis.",
  },
  {
    name: "vw_sales_by_category",
    source: "sales, categories",
    recommendedPage: "Sales Performance",
    purpose: "Category revenue mix, unit movement, and gross profit comparison.",
  },
  {
    name: "vw_inventory_health",
    source: "inventory, products, suppliers",
    recommendedPage: "Inventory Health",
    purpose: "Stock value, low-stock flag, quantity on order, and health status by product and branch.",
  },
  {
    name: "vw_low_stock",
    source: "inventory, products",
    recommendedPage: "Inventory Health",
    purpose: "Focused reorder risk table for product-branch rows at or below threshold.",
  },
  {
    name: "vw_purchase_order_status",
    source: "purchase_orders",
    recommendedPage: "Supplier and Purchase Orders",
    purpose: "Order counts and value by status, branch, and supplier.",
  },
  {
    name: "vw_supplier_performance",
    source: "suppliers, purchase_orders",
    recommendedPage: "Supplier and Purchase Orders",
    purpose: "Supplier product coverage, order value, open order exposure, and received quantity.",
  },
  {
    name: "vw_forecast_summary",
    source: "forecasts",
    recommendedPage: "Forecast and Recommendations",
    purpose: "Stored forecast totals, planning bands, scope labels, and model names.",
  },
];

const EXPORT_ACTIONS: ExportAction[] = [
  {
    kind: "sales",
    label: "Sales CSV",
    description: "Line-level sales with branch, category, revenue, discount, and gross profit fields.",
  },
  {
    kind: "inventory",
    label: "Inventory CSV",
    description: "Current stock, low-stock flag, stock value, supplier, and branch fields.",
  },
  {
    kind: "purchase-orders",
    label: "Purchase Orders CSV",
    description: "Purchase order line items with status, supplier, quantities, costs, and approvals.",
  },
  {
    kind: "forecasts",
    label: "Forecasts CSV",
    description: "Stored forecast scopes, horizons, values, confidence bands, and model names.",
  },
];

const REFRESH_STEPS = [
  "Run local migrations so the reporting views exist in PostgreSQL.",
  "Connect Power BI Desktop to the local database or import CSV files from this page.",
  "Refresh after seed data, sales, inventory adjustments, purchase order receiving, or forecast runs.",
  "Keep operational actions in this web dashboard; use Power BI for reporting and presentation.",
];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Could not download the export. Check that the backend is running.";
}

export function PowerBIReportsPage() {
  const { token, user } = useAuth();
  const [activeExport, setActiveExport] = useState<ExportKind | null>(null);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const metrics = useMemo<PageMetric[]>(
    () => [
      {
        label: "Reporting Views",
        value: "8 ready",
        detail: "Power BI Desktop can read local SQL views.",
        tone: "blue",
      },
      {
        label: "CSV Exports",
        value: "4 endpoints",
        detail: "Sales, inventory, purchase orders, and forecasts.",
        tone: "green",
      },
      {
        label: "Permission Scope",
        value: "Backend enforced",
        detail: "Exports use the same auth and branch rules.",
        tone: "amber",
      },
      {
        label: "Cloud Cost",
        value: "No paid DB",
        detail: "MVP reports run from local PostgreSQL or CSV.",
        tone: "slate",
      },
    ],
    [],
  );

  const handleDownload = useCallback(
    async (kind: ExportKind) => {
      if (!token) return;
      setActiveExport(kind);
      setExportMessage(null);
      setExportError(null);
      try {
        await downloadExport(token, kind);
        setExportMessage(`${EXPORT_ACTIONS.find((item) => item.kind === kind)?.label ?? "Export"} downloaded.`);
      } catch (error) {
        setExportError(errorMessage(error));
      } finally {
        setActiveExport(null);
      }
    },
    [token],
  );

  return (
    <section className="page-stack" aria-labelledby="powerbi-title">
      <div className="page-header">
        <div>
          <p className="eyebrow">Executive reporting</p>
          <h2 id="powerbi-title">Power BI reports</h2>
          <p className="page-description">
            Prepare local PostgreSQL reporting views and authenticated CSV files for Power BI
            Desktop. The web dashboard remains the place for sales, stock, and purchase order
            actions.
          </p>
        </div>
        <div className="page-header-side">
          <span className="role-scope">{user?.role === "admin" ? "Admin reporting" : "Analyst reporting"}</span>
          <a className="action-button secondary" href="/docs/POWER_BI_SETUP.md" rel="noreferrer" target="_blank">
            <ExternalLink aria-hidden="true" size={16} />
            Setup guide
          </a>
        </div>
      </div>

      <section className="metric-grid" aria-label="Power BI integration metrics">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} metric={metric} />
        ))}
      </section>

      {exportError ? <ErrorState message={exportError} title="Export failed" /> : null}
      {exportMessage ? (
        <div className="state-panel success">
          <FileSpreadsheet aria-hidden="true" size={22} />
          <p>{exportMessage}</p>
        </div>
      ) : null}

      <section className="powerbi-grid">
        <article className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">CSV files</p>
              <h3>Authenticated exports</h3>
            </div>
            <Download aria-hidden="true" size={20} />
          </div>
          <div className="export-button-grid">
            {EXPORT_ACTIONS.map((item) => (
              <button
                className="export-card-button"
                disabled={activeExport !== null}
                key={item.kind}
                onClick={() => void handleDownload(item.kind)}
                type="button"
              >
                <span>
                  <FileSpreadsheet aria-hidden="true" size={18} />
                  <strong>{item.label}</strong>
                </span>
                <p>{item.description}</p>
                <b>{activeExport === item.kind ? "Preparing file" : "Download CSV"}</b>
              </button>
            ))}
          </div>
        </article>

        <aside className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Refresh workflow</p>
              <h3>Desktop reporting steps</h3>
            </div>
            <RefreshCw aria-hidden="true" size={20} />
          </div>
          <ol className="refresh-list">
            {REFRESH_STEPS.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          <div className="powerbi-note">
            <ShieldCheck aria-hidden="true" size={18} />
            <span>API exports respect role and branch permissions. Direct database exposure is not required.</span>
          </div>
          <div className="powerbi-note">
            <CloudOff aria-hidden="true" size={18} />
            <span>Power BI Desktop can run locally for the MVP without Power BI Service or a cloud database.</span>
          </div>
        </aside>

        <article className="panel wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">SQL reporting layer</p>
              <h3>Views for Power BI Desktop</h3>
            </div>
            <Database aria-hidden="true" size={20} />
          </div>
          <div className="table-shell powerbi-table">
            <table>
              <thead>
                <tr>
                  <th>View</th>
                  <th>Source</th>
                  <th>Power BI page</th>
                  <th>Purpose</th>
                </tr>
              </thead>
              <tbody>
                {REPORTING_VIEWS.map((view) => (
                  <tr key={view.name}>
                    <td>
                      <strong>{view.name}</strong>
                    </td>
                    <td>{view.source}</td>
                    <td>{view.recommendedPage}</td>
                    <td>{view.purpose}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Report pages</p>
              <h3>Recommended workbook layout</h3>
            </div>
            <TableProperties aria-hidden="true" size={20} />
          </div>
          <div className="compact-list powerbi-pages">
            {[
              "Executive Overview",
              "Sales Performance",
              "Inventory Health",
              "Supplier and Purchase Orders",
              "Forecast and Recommendations",
            ].map((page) => (
              <article key={page}>
                <strong>{page}</strong>
                <span>Use local views or CSV imports, then refresh after operational changes.</span>
              </article>
            ))}
          </div>
        </article>
      </section>
    </section>
  );
}
