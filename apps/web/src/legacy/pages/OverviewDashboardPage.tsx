import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ApiError } from "../api/client";
import { getOverviewDashboard } from "../api/dashboard";
import { listBranches, listCategories, listProducts } from "../api/masterData";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, LoadingState, MetricCard } from "../components/ui";
import type { Branch, Category, OverviewDashboard, Product } from "../types";
import {
  formatCurrency,
  formatDate,
  formatPercent,
  formatQuantity,
  inputDateDaysAgo,
} from "../utils/format";

const HEALTH_COLORS = ["#2f8f63", "#c47a19", "#c04354", "#667085"];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Could not load dashboard data. Check that the backend is running.";
}

function numberValue(value: string): number {
  return Number(value);
}

function formatShortCurrency(value: number): string {
  return formatCurrency(value);
}

export function OverviewDashboardPage() {
  const { token, user } = useAuth();
  const [dashboard, setDashboard] = useState<OverviewDashboard | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [branchId, setBranchId] = useState(0);
  const [categoryId, setCategoryId] = useState(0);
  const [productId, setProductId] = useState(0);
  const [startDate, setStartDate] = useState(() => inputDateDaysAgo(30));
  const [endDate, setEndDate] = useState(() => inputDateDaysAgo(0));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const visibleBranches = useMemo(() => {
    if (!user || user.role === "admin" || user.role === "analyst") {
      return branches;
    }
    return branches.filter((branch) => branch.id === user.branch_id);
  }, [branches, user]);

  useEffect(() => {
    if (user && user.role !== "admin" && user.role !== "analyst" && user.branch_id && branchId !== user.branch_id) {
      setBranchId(user.branch_id);
    }
  }, [branchId, user]);

  const loadOptions = useCallback(async () => {
    if (!token) return;
    const [branchRows, categoryRows, productRows] = await Promise.all([
      listBranches(token, { includeInactive: false }),
      listCategories(token),
      listProducts(token, { includeInactive: false }),
    ]);
    setBranches(branchRows);
    setCategories(categoryRows);
    setProducts(productRows);
  }, [token]);

  const loadDashboard = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      setDashboard(
        await getOverviewDashboard(token, {
          branchId: branchId || undefined,
          categoryId: categoryId || undefined,
          productId: productId || undefined,
          startDate,
          endDate,
        }),
      );
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [branchId, categoryId, endDate, productId, startDate, token]);

  useEffect(() => {
    void loadOptions().catch((optionsError) => setError(errorMessage(optionsError)));
  }, [loadOptions]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const trendData = useMemo(
    () =>
      dashboard?.sales_trend.map((point) => ({
        date: formatDate(point.date),
        revenue: numberValue(point.revenue),
        grossProfit: numberValue(point.gross_profit),
      })) ?? [],
    [dashboard],
  );

  const categoryData = useMemo(
    () =>
      dashboard?.revenue_by_category.slice(0, 7).map((point) => ({
        name: point.category_name,
        revenue: numberValue(point.revenue),
      })) ?? [],
    [dashboard],
  );

  const branchData = useMemo(
    () =>
      dashboard?.branch_performance.map((point) => ({
        name: point.branch_name,
        revenue: numberValue(point.revenue),
        profit: numberValue(point.gross_profit),
      })) ?? [],
    [dashboard],
  );

  const inventoryHealthData = useMemo(
    () =>
      dashboard?.inventory_health.map((point) => ({
        name: point.status,
        value: point.product_count,
      })) ?? [],
    [dashboard],
  );

  return (
    <section className="page-stack" aria-labelledby="overview-title">
      <div className="page-header">
        <div>
          <p className="eyebrow">Executive view</p>
          <h2 id="overview-title">Overview dashboard</h2>
          <p className="page-description">
            Monitor real sales, margin, inventory health, branch performance, and open purchase
            order pressure from backend KPI services.
          </p>
        </div>
        <div className="page-header-side">
          <span className="role-scope">Live database KPIs</span>
          <button className="action-button secondary" onClick={() => void loadDashboard()} type="button">
            <RefreshCw aria-hidden="true" size={16} />
            Refresh
          </button>
        </div>
      </div>

      <div className="filter-bar dashboard-filter-bar">
        <div className="filter-actions">
          <select
            aria-label="Filter overview by branch"
            onChange={(event) => setBranchId(Number(event.target.value))}
            value={branchId}
          >
            <option value={0}>All accessible branches</option>
            {visibleBranches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter overview by category"
            onChange={(event) => setCategoryId(Number(event.target.value))}
            value={categoryId}
          >
            <option value={0}>All categories</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter overview by product"
            onChange={(event) => setProductId(Number(event.target.value))}
            value={productId}
          >
            <option value={0}>All products</option>
            {products.map((product) => (
              <option key={product.id} value={product.id}>
                {product.name}
              </option>
            ))}
          </select>
          <label className="date-filter">
            Start
            <input onChange={(event) => setStartDate(event.target.value)} type="date" value={startDate} />
          </label>
          <label className="date-filter">
            End
            <input onChange={(event) => setEndDate(event.target.value)} type="date" value={endDate} />
          </label>
        </div>
      </div>

      {error ? <ErrorState message={error} title="Dashboard load failed" /> : null}
      {loading && !dashboard ? <LoadingState label="Loading dashboard KPIs" /> : null}

      {dashboard ? (
        <>
          <section className="metric-grid" aria-label="Overview KPIs">
            <MetricCard
              metric={{
                label: "Total Revenue",
                value: formatCurrency(dashboard.kpis.sales.revenue),
                detail: `${formatPercent(dashboard.kpis.sales.sales_growth_percent)} vs previous period`,
                tone: "green",
              }}
            />
            <MetricCard
              metric={{
                label: "Gross Profit",
                value: formatCurrency(dashboard.kpis.sales.gross_profit),
                detail: `${formatPercent(dashboard.kpis.sales.gross_margin_percent)} gross margin`,
                tone: "blue",
              }}
            />
            <MetricCard
              metric={{
                label: "Stock Value",
                value: formatCurrency(dashboard.kpis.inventory.current_stock_value),
                detail: `${formatQuantity(dashboard.kpis.inventory.total_quantity_on_hand)} units on hand`,
                tone: "slate",
              }}
            />
            <MetricCard
              metric={{
                label: "Low-Stock Items",
                value: String(dashboard.kpis.inventory.low_stock_product_count),
                detail: "Product-branch rows at or below threshold",
                tone: "amber",
              }}
            />
            <MetricCard
              metric={{
                label: "Pending Orders",
                value: String(dashboard.kpis.purchase_orders.pending_purchase_orders),
                detail: `${formatCurrency(dashboard.kpis.purchase_orders.total_open_order_value)} open value`,
                tone: "rose",
              }}
            />
            <MetricCard
              metric={{
                label: "Units Sold",
                value: formatQuantity(dashboard.kpis.sales.units_sold),
                detail: `${dashboard.kpis.sales.transaction_count} transactions`,
                tone: "green",
              }}
            />
            <MetricCard
              metric={{
                label: "Average Order",
                value: formatCurrency(dashboard.kpis.sales.average_order_value),
                detail: "Revenue per transaction",
                tone: "blue",
              }}
            />
            <MetricCard
              metric={{
                label: "Top Product",
                value: dashboard.kpis.top_selling_product?.product_name ?? "No sales",
                detail: dashboard.kpis.top_selling_product
                  ? `${formatQuantity(dashboard.kpis.top_selling_product.units_sold)} units sold`
                  : "No product sales in this range",
                tone: "slate",
              }}
            />
          </section>

          <section className="dashboard-grid">
            <article className="panel chart-panel wide">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Sales trend</p>
                  <h3>Revenue and gross profit</h3>
                </div>
              </div>
              {trendData.length === 0 ? (
                <EmptyState title="No sales trend" message="Adjust filters or record sales for this period." />
              ) : (
                <ResponsiveContainer height={280} width="100%">
                  <LineChart data={trendData}>
                    <CartesianGrid stroke="#e7ebf1" vertical={false} />
                    <XAxis dataKey="date" />
                    <YAxis tickFormatter={formatShortCurrency} width={78} />
                    <Tooltip formatter={(value) => formatCurrency(Number(value))} />
                    <Line dataKey="revenue" name="Revenue" stroke="#2f8f63" strokeWidth={2} type="monotone" />
                    <Line dataKey="grossProfit" name="Gross profit" stroke="#276fbf" strokeWidth={2} type="monotone" />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </article>

            <article className="panel chart-panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Inventory health</p>
                  <h3>Stock status mix</h3>
                </div>
              </div>
              {inventoryHealthData.length === 0 ? (
                <EmptyState title="No inventory" message="Stock rows will appear once inventory exists." />
              ) : (
                <ResponsiveContainer height={280} width="100%">
                  <PieChart>
                    <Pie data={inventoryHealthData} dataKey="value" innerRadius={58} nameKey="name" outerRadius={95}>
                      {inventoryHealthData.map((entry, index) => (
                        <Cell fill={HEALTH_COLORS[index % HEALTH_COLORS.length]} key={entry.name} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </article>

            <article className="panel chart-panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Category revenue</p>
                  <h3>Revenue by category</h3>
                </div>
              </div>
              {categoryData.length === 0 ? (
                <EmptyState title="No category revenue" message="Category sales will appear here." />
              ) : (
                <ResponsiveContainer height={270} width="100%">
                  <BarChart data={categoryData}>
                    <CartesianGrid stroke="#e7ebf1" vertical={false} />
                    <XAxis dataKey="name" />
                    <YAxis tickFormatter={formatShortCurrency} width={76} />
                    <Tooltip formatter={(value) => formatCurrency(Number(value))} />
                    <Bar dataKey="revenue" fill="#c47a19" name="Revenue" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </article>

            <article className="panel chart-panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Branch performance</p>
                  <h3>Revenue by branch</h3>
                </div>
              </div>
              {branchData.length === 0 ? (
                <EmptyState title="No branch sales" message="Branch revenue will appear here." />
              ) : (
                <ResponsiveContainer height={270} width="100%">
                  <BarChart data={branchData}>
                    <CartesianGrid stroke="#e7ebf1" vertical={false} />
                    <XAxis dataKey="name" />
                    <YAxis tickFormatter={formatShortCurrency} width={76} />
                    <Tooltip formatter={(value) => formatCurrency(Number(value))} />
                    <Bar dataKey="revenue" fill="#276fbf" name="Revenue" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </article>

            <article className="panel wide">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Product ranking</p>
                  <h3>Top-selling products</h3>
                </div>
              </div>
              <div className="table-shell">
                <table>
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>Category</th>
                      <th>Units</th>
                      <th>Revenue</th>
                      <th>Gross Profit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.top_products.map((product) => (
                      <tr key={product.product_id}>
                        <td>
                          <strong>{product.product_name}</strong>
                          <span className="subtle-cell">{product.product_sku}</span>
                        </td>
                        <td>{product.category_name}</td>
                        <td>{formatQuantity(product.units_sold)}</td>
                        <td>{formatCurrency(product.revenue)}</td>
                        <td>{formatCurrency(product.gross_profit)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {dashboard.top_products.length === 0 ? (
                  <EmptyState title="No product ranking" message="No product sales match the filters." />
                ) : null}
              </div>
            </article>

            <article className="panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Stock risk</p>
                  <h3>Critical low-stock items</h3>
                </div>
              </div>
              <div className="compact-list">
                {dashboard.low_stock_items.slice(0, 8).map((item) => (
                  <article key={`${item.product_id}-${item.branch_id}`}>
                    <div>
                      <strong>{item.product_name}</strong>
                      <span>{item.branch_name}</span>
                    </div>
                    <b>
                      {formatQuantity(item.quantity_on_hand)} / {formatQuantity(item.reorder_threshold)}
                    </b>
                  </article>
                ))}
              </div>
              {dashboard.low_stock_items.length === 0 ? (
                <EmptyState title="No low stock" message="All filtered stock is above threshold." />
              ) : null}
            </article>
          </section>
        </>
      ) : null}
    </section>
  );
}
