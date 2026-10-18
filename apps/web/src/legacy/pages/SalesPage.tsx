import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Eye, Plus, ReceiptText, RefreshCw, Send, Trash2 } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ApiError } from "../api/client";
import { getSalesDashboard } from "../api/dashboard";
import { listInventory } from "../api/inventory";
import { listBranches, listCategories, listProducts } from "../api/masterData";
import { createSale, getSale, listSales } from "../api/sales";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, LoadingState, MetricCard } from "../components/ui";
import type {
  Branch,
  Category,
  InventoryItem,
  Product,
  Sale,
  SaleListItem,
  SalesDashboard,
  SalesKpi,
  SalesTrendPoint,
  UserRole,
} from "../types";

type SaleFormLine = {
  productId: number;
  quantity: string;
  discountAmount: string;
};

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Could not complete the request. Check that the backend is running.";
}

function canCreateSales(role: UserRole): boolean {
  return role === "admin" || role === "store_manager" || role === "staff";
}

function inputDateDaysAgo(daysAgo: number): string {
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  return date.toISOString().slice(0, 10);
}

function formatCurrency(value: string | number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function formatQuantity(value: string | number): string {
  return Number(value).toLocaleString("en-IN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString([], {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
  });
}

function formatPercent(value: string | null): string {
  if (value === null) {
    return "No prior period";
  }
  const numberValue = Number(value);
  return `${numberValue > 0 ? "+" : ""}${numberValue.toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  })}%`;
}

function blankLine(): SaleFormLine {
  return {
    productId: 0,
    quantity: "1.00",
    discountAmount: "0.00",
  };
}

function emptySummary(): SalesKpi {
  return {
    revenue: "0.00",
    gross_profit: "0.00",
    gross_margin_percent: null,
    units_sold: "0.00",
    transaction_count: 0,
    average_order_value: "0.00",
    sales_growth_percent: null,
    previous_period_revenue: "0.00",
  };
}

export function SalesPage() {
  const { token, user } = useAuth();
  const [branches, setBranches] = useState<Branch[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [inventoryRows, setInventoryRows] = useState<InventoryItem[]>([]);
  const [sales, setSales] = useState<SaleListItem[]>([]);
  const [summary, setSummary] = useState<SalesKpi>(() => emptySummary());
  const [dashboard, setDashboard] = useState<SalesDashboard | null>(null);
  const [trends, setTrends] = useState<SalesTrendPoint[]>([]);
  const [selectedSale, setSelectedSale] = useState<Sale | null>(null);
  const [branchId, setBranchId] = useState(0);
  const [categoryId, setCategoryId] = useState(0);
  const [productId, setProductId] = useState(0);
  const [startDate, setStartDate] = useState(() => inputDateDaysAgo(30));
  const [endDate, setEndDate] = useState(() => inputDateDaysAgo(0));
  const [saleLines, setSaleLines] = useState<SaleFormLine[]>(() => [blankLine()]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const visibleBranches = useMemo(() => {
    if (!user || user.role === "admin" || user.role === "analyst") {
      return branches;
    }
    return branches.filter((branch) => branch.id === user.branch_id);
  }, [branches, user]);

  const authorizedToCreate = Boolean(user && canCreateSales(user.role));

  const productById = useMemo(() => {
    return new Map(products.map((product) => [product.id, product]));
  }, [products]);

  const stockByProductId = useMemo(() => {
    const map = new Map<number, InventoryItem>();
    inventoryRows.forEach((row) => map.set(row.product_id, row));
    return map;
  }, [inventoryRows]);

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

  const loadInventoryRows = useCallback(async () => {
    if (!token || branchId === 0) {
      setInventoryRows([]);
      return;
    }
    setInventoryRows(await listInventory(token, { branchId }));
  }, [branchId, token]);

  const loadSalesWorkspace = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const options = {
        branchId: branchId || undefined,
        categoryId: categoryId || undefined,
        productId: productId || undefined,
        startDate,
        endDate,
      };
      const [saleRows, dashboardData] = await Promise.all([
        listSales(token, { ...options, limit: 100 }),
        getSalesDashboard(token, options),
      ]);
      setSales(saleRows);
      setSummary(dashboardData.summary);
      setDashboard(dashboardData);
      setTrends(dashboardData.sales_trend.slice(-14));
      if (selectedSale && !saleRows.some((sale) => sale.id === selectedSale.id)) {
        setSelectedSale(null);
      }
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [branchId, categoryId, endDate, productId, selectedSale, startDate, token]);

  useEffect(() => {
    void loadOptions().catch((optionsError) => setError(errorMessage(optionsError)));
  }, [loadOptions]);

  useEffect(() => {
    void loadInventoryRows().catch((inventoryError) => setError(errorMessage(inventoryError)));
  }, [loadInventoryRows]);

  useEffect(() => {
    void loadSalesWorkspace();
  }, [loadSalesWorkspace]);

  const updateLine = (index: number, changes: Partial<SaleFormLine>) => {
    setSaleLines((current) =>
      current.map((line, lineIndex) => (lineIndex === index ? { ...line, ...changes } : line)),
    );
  };

  const removeLine = (index: number) => {
    setSaleLines((current) => (current.length === 1 ? current : current.filter((_line, lineIndex) => lineIndex !== index)));
  };

  const saleEstimate = useMemo(() => {
    const subtotal = saleLines.reduce((sum, line) => {
      const product = productById.get(line.productId);
      if (!product) return sum;
      const quantity = Number(line.quantity) || 0;
      const discount = Number(line.discountAmount) || 0;
      return sum + Math.max(Number(product.selling_price) * quantity - discount, 0);
    }, 0);
    const tax = subtotal * 0.05;
    return {
      subtotal,
      tax,
      total: subtotal + tax,
    };
  }, [productById, saleLines]);

  const submitSale = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) return;
    if (!authorizedToCreate) {
      setError("Your role is read-only for sales entry.");
      return;
    }
    if (!branchId) {
      setError("Select a branch before recording a sale.");
      return;
    }
    const items = saleLines
      .filter((line) => line.productId > 0)
      .map((line) => ({
        product_id: line.productId,
        quantity: line.quantity,
        discount_amount: line.discountAmount || "0.00",
      }));
    if (items.length === 0) {
      setError("Add at least one product line before recording a sale.");
      return;
    }

    setSaving(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const sale = await createSale(token, {
        branch_id: branchId,
        tax_rate: "0.05",
        items,
      });
      setSelectedSale(sale);
      setSaleLines([blankLine()]);
      setSuccessMessage(`Sale ${sale.sale_number} recorded. Backend total: ${formatCurrency(sale.total_amount)}.`);
      await Promise.all([loadSalesWorkspace(), loadInventoryRows()]);
    } catch (saleError) {
      setError(errorMessage(saleError));
    } finally {
      setSaving(false);
    }
  };

  const openSaleDetail = async (saleId: number) => {
    if (!token) return;
    setDetailLoading(true);
    setError(null);
    try {
      setSelectedSale(await getSale(token, saleId));
    } catch (detailError) {
      setError(errorMessage(detailError));
    } finally {
      setDetailLoading(false);
    }
  };

  const trendChartData = useMemo(
    () =>
      trends.map((point) => ({
        date: new Date(`${point.date}T00:00:00`).toLocaleDateString([], { day: "2-digit", month: "short" }),
        revenue: Number(point.revenue),
        grossProfit: Number(point.gross_profit),
      })),
    [trends],
  );

  const categoryChartData = useMemo(
    () =>
      dashboard?.revenue_by_category.slice(0, 7).map((point) => ({
        name: point.category_name,
        revenue: Number(point.revenue),
      })) ?? [],
    [dashboard],
  );

  const branchChartData = useMemo(
    () =>
      dashboard?.branch_performance.map((point) => ({
        name: point.branch_name,
        revenue: Number(point.revenue),
      })) ?? [],
    [dashboard],
  );

  return (
    <section className="page-stack">
      <div className="page-header">
        <div>
          <p className="eyebrow">Sales engine</p>
          <h2>Sales entry and summary</h2>
          <p className="page-description">
            Record branch sales with multiple items, let the backend calculate totals, and keep stock
            reductions tied to sale movement records.
          </p>
        </div>
        <div className="page-header-side">
          <span className="role-scope">
            {authorizedToCreate ? "Sales entry enabled" : "Read-only sales view"}
          </span>
        </div>
      </div>

      <div className="filter-bar sales-filter-bar">
        <div className="filter-actions">
          <select
            aria-label="Filter sales by branch"
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
            aria-label="Filter sales by category"
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
            aria-label="Filter sales by product"
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
          <button className="filter-chip" onClick={() => void loadSalesWorkspace()} type="button">
            <RefreshCw aria-hidden="true" size={15} />
            Refresh
          </button>
        </div>
      </div>

      <section className="metric-grid">
        <MetricCard
          metric={{
            label: "Revenue",
            value: formatCurrency(summary.revenue),
            detail: `${formatPercent(summary.sales_growth_percent)} vs previous period`,
            tone: "green",
          }}
        />
        <MetricCard
          metric={{
            label: "Gross Profit",
            value: formatCurrency(summary.gross_profit),
            detail: `${formatPercent(summary.gross_margin_percent)} gross margin`,
            tone: "blue",
          }}
        />
        <MetricCard
          metric={{
            label: "Units Sold",
            value: formatQuantity(summary.units_sold),
            detail: "Across selected filters",
            tone: "amber",
          }}
        />
        <MetricCard
          metric={{
            label: "Average Order",
            value: formatCurrency(summary.average_order_value),
            detail: `${summary.transaction_count} transactions`,
            tone: "slate",
          }}
        />
      </section>

      {error ? <ErrorState message={error} title="Sales action failed" /> : null}
      {successMessage ? <div className="success-panel">{successMessage}</div> : null}

      {dashboard ? (
        <section className="dashboard-grid">
          <article className="panel chart-panel wide">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Sales trend</p>
                <h3>Revenue and gross profit</h3>
              </div>
            </div>
            {trendChartData.length === 0 ? (
              <EmptyState title="No trend data" message="Record sales or adjust the date range." />
            ) : (
              <ResponsiveContainer height={280} width="100%">
                <LineChart data={trendChartData}>
                  <CartesianGrid stroke="#e7ebf1" vertical={false} />
                  <XAxis dataKey="date" />
                  <YAxis tickFormatter={(value) => formatCurrency(Number(value))} width={78} />
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
                <p className="eyebrow">Category mix</p>
                <h3>Revenue by category</h3>
              </div>
            </div>
            {categoryChartData.length === 0 ? (
              <EmptyState title="No category sales" message="Category revenue appears after matching sales." />
            ) : (
              <ResponsiveContainer height={280} width="100%">
                <BarChart data={categoryChartData}>
                  <CartesianGrid stroke="#e7ebf1" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis tickFormatter={(value) => formatCurrency(Number(value))} width={78} />
                  <Tooltip formatter={(value) => formatCurrency(Number(value))} />
                  <Bar dataKey="revenue" fill="#c47a19" name="Revenue" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </article>

          <article className="panel chart-panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Branches</p>
                <h3>Branch performance</h3>
              </div>
            </div>
            {branchChartData.length === 0 ? (
              <EmptyState title="No branch sales" message="Branch comparison appears after sales are recorded." />
            ) : (
              <ResponsiveContainer height={280} width="100%">
                <BarChart data={branchChartData}>
                  <CartesianGrid stroke="#e7ebf1" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis tickFormatter={(value) => formatCurrency(Number(value))} width={78} />
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
                <h3>Best-selling products</h3>
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
            </div>
          </article>
        </section>
      ) : null}

      <section className="sales-grid">
        <article className="panel sale-entry-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Record sale</p>
              <h3>Manual sale entry</h3>
            </div>
            <ReceiptText aria-hidden="true" size={18} />
          </div>
          <form className="master-form" onSubmit={submitSale}>
            <label>
              Sale branch
              <select
                disabled={!authorizedToCreate}
                onChange={(event) => setBranchId(Number(event.target.value))}
                required
                value={branchId}
              >
                <option value={0}>Select branch</option>
                {visibleBranches.map((branch) => (
                  <option key={branch.id} value={branch.id}>
                    {branch.name}
                  </option>
                ))}
              </select>
            </label>

            <div className="sale-line-list">
              {saleLines.map((line, index) => {
                const product = productById.get(line.productId);
                const stock = stockByProductId.get(line.productId);
                const lineTotal = product
                  ? Math.max(Number(product.selling_price) * (Number(line.quantity) || 0) - (Number(line.discountAmount) || 0), 0)
                  : 0;
                return (
                  <div className="sale-line-grid" key={`${index}-${line.productId}`}>
                    <label>
                      Product
                      <select
                        disabled={!authorizedToCreate}
                        onChange={(event) => updateLine(index, { productId: Number(event.target.value) })}
                        required
                        value={line.productId}
                      >
                        <option value={0}>Select product</option>
                        {products.map((productOption) => (
                          <option key={productOption.id} value={productOption.id}>
                            {productOption.name} ({productOption.sku})
                          </option>
                        ))}
                      </select>
                      {product ? (
                        <span className="field-note">
                          {formatCurrency(product.selling_price)} each
                          {stock ? `, ${formatQuantity(stock.quantity_on_hand)} available` : ""}
                        </span>
                      ) : null}
                    </label>
                    <label>
                      Quantity
                      <input
                        disabled={!authorizedToCreate}
                        inputMode="decimal"
                        minLength={1}
                        onChange={(event) => updateLine(index, { quantity: event.target.value })}
                        required
                        type="text"
                        value={line.quantity}
                      />
                    </label>
                    <label>
                      Discount
                      <input
                        disabled={!authorizedToCreate}
                        inputMode="decimal"
                        onChange={(event) => updateLine(index, { discountAmount: event.target.value })}
                        required
                        type="text"
                        value={line.discountAmount}
                      />
                    </label>
                    <div className="line-total">
                      <span>Est. line total</span>
                      <strong>{formatCurrency(lineTotal)}</strong>
                    </div>
                    <button
                      aria-label="Remove sale line"
                      className="icon-button remove-line"
                      disabled={!authorizedToCreate || saleLines.length === 1}
                      onClick={() => removeLine(index)}
                      type="button"
                    >
                      <Trash2 aria-hidden="true" size={16} />
                    </button>
                  </div>
                );
              })}
            </div>

            <div className="sale-form-actions">
              <div className="sale-estimate">
                <span>Estimated subtotal {formatCurrency(saleEstimate.subtotal)}</span>
                <span>Estimated tax {formatCurrency(saleEstimate.tax)}</span>
                <strong>Estimated total {formatCurrency(saleEstimate.total)}</strong>
              </div>
              <div className="sale-button-row">
                <button
                  className="action-button secondary"
                  disabled={!authorizedToCreate}
                  onClick={() => setSaleLines((current) => [...current, blankLine()])}
                  type="button"
                >
                  <Plus aria-hidden="true" size={16} />
                  Add item
                </button>
                <button className="action-button primary" disabled={!authorizedToCreate || saving} type="submit">
                  <Send aria-hidden="true" size={16} />
                  {saving ? "Recording" : "Record sale"}
                </button>
              </div>
            </div>
          </form>
        </article>

        <aside className="panel sales-side-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Trend</p>
              <h3>Recent sales days</h3>
            </div>
          </div>
          {trends.length === 0 ? (
            <EmptyState title="No trend data" message="Record sales or adjust the date filter to see daily movement." />
          ) : (
            <div className="trend-list">
              {trends.map((point) => (
                <article key={point.date}>
                  <span>{new Date(`${point.date}T00:00:00`).toLocaleDateString([], { day: "2-digit", month: "short" })}</span>
                  <strong>{formatCurrency(point.revenue)}</strong>
                  <b>{formatQuantity(point.units_sold)} units</b>
                </article>
              ))}
            </div>
          )}
        </aside>
      </section>

      <section className="sales-grid">
        <article className="panel wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Sales ledger</p>
              <h3>Recent sales</h3>
            </div>
          </div>
          {loading ? <LoadingState label="Loading sales" /> : null}
          {!loading && sales.length === 0 ? (
            <EmptyState title="No sales found" message="Try changing the branch or date range." />
          ) : null}
          {!loading && sales.length > 0 ? (
            <div className="table-shell sales-table">
              <table>
                <thead>
                  <tr>
                    <th>Sale</th>
                    <th>Branch</th>
                    <th>Date</th>
                    <th>Items</th>
                    <th>Revenue</th>
                    <th>Gross Profit</th>
                    <th>Total</th>
                    <th>Created By</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sales.map((sale) => (
                    <tr className={selectedSale?.id === sale.id ? "selected-row" : ""} key={sale.id}>
                      <td>
                        <strong>{sale.sale_number}</strong>
                        <span className="subtle-cell">{formatQuantity(sale.units_sold)} units sold</span>
                      </td>
                      <td>{sale.branch_name}</td>
                      <td>{formatDateTime(sale.sale_datetime)}</td>
                      <td>{sale.item_count}</td>
                      <td>{formatCurrency(sale.subtotal)}</td>
                      <td>{formatCurrency(sale.gross_profit)}</td>
                      <td>{formatCurrency(sale.total_amount)}</td>
                      <td>{sale.created_by_name}</td>
                      <td>
                        <div className="table-actions">
                          <button onClick={() => void openSaleDetail(sale.id)} type="button">
                            <Eye aria-hidden="true" size={14} />
                            Detail
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </article>

        <aside className="panel sales-side-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Sale detail</p>
              <h3>{selectedSale ? selectedSale.sale_number : "Select a sale"}</h3>
            </div>
          </div>
          {detailLoading ? <LoadingState label="Loading sale detail" /> : null}
          {!detailLoading && !selectedSale ? (
            <EmptyState title="No sale selected" message="Open a sale to inspect its line items and backend totals." />
          ) : null}
          {!detailLoading && selectedSale ? (
            <div className="detail-stack">
              <div className="detail-list">
                <div>
                  <span>Branch</span>
                  <strong>{selectedSale.branch_name}</strong>
                </div>
                <div>
                  <span>Revenue</span>
                  <strong>{formatCurrency(selectedSale.subtotal)}</strong>
                </div>
                <div>
                  <span>Tax</span>
                  <strong>{formatCurrency(selectedSale.tax_total)}</strong>
                </div>
                <div>
                  <span>Total</span>
                  <strong>{formatCurrency(selectedSale.total_amount)}</strong>
                </div>
              </div>
              <div className="sale-detail-lines">
                {selectedSale.items.map((item) => (
                  <article key={item.id}>
                    <div>
                      <strong>{item.product_name}</strong>
                      <span>{item.product_sku}</span>
                    </div>
                    <b>{formatQuantity(item.quantity)} x {formatCurrency(item.unit_price)}</b>
                    <p>
                      Line {formatCurrency(item.line_total)} | Profit {formatCurrency(item.gross_profit)}
                    </p>
                  </article>
                ))}
              </div>
            </div>
          ) : null}
        </aside>
      </section>
    </section>
  );
}
