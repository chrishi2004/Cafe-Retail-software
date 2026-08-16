import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Eye, History, PackageCheck, RotateCw, Search, SlidersHorizontal, X } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ApiError } from "../api/client";
import { getInventoryDashboard } from "../api/dashboard";
import {
  createStockAdjustment,
  getProductInventory,
  listInventory,
  listLowStockInventory,
  listStockMovements,
} from "../api/inventory";
import { listBranches, listCategories, listSuppliers } from "../api/masterData";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, LoadingState, MetricCard } from "../components/ui";
import type {
  Branch,
  Category,
  InventoryDashboard,
  InventoryItem,
  ProductInventoryDetail,
  StockMovement,
  Supplier,
  UserRole,
} from "../types";

const HEALTH_COLORS = ["#2f8f63", "#c47a19", "#c04354", "#667085"];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Could not complete the request. Check that the backend is running.";
}

function canAdjustStock(role: UserRole): boolean {
  return role === "admin" || role === "store_manager";
}

function formatCurrency(value: string): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function formatQuantity(value: string): string {
  return Number(value).toLocaleString("en-IN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

function formatMovementType(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function inputDateDaysAgo(daysAgo: number): string {
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  return date.toISOString().slice(0, 10);
}

export function InventoryPage() {
  const { token, user } = useAuth();
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [dashboard, setDashboard] = useState<InventoryDashboard | null>(null);
  const [lowStockCount, setLowStockCount] = useState(0);
  const [movements, setMovements] = useState<StockMovement[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [selectedItem, setSelectedItem] = useState<InventoryItem | null>(null);
  const [detail, setDetail] = useState<ProductInventoryDetail | null>(null);
  const [search, setSearch] = useState("");
  const [branchId, setBranchId] = useState(0);
  const [categoryId, setCategoryId] = useState(0);
  const [supplierId, setSupplierId] = useState(0);
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const [startDate, setStartDate] = useState(() => inputDateDaysAgo(30));
  const [endDate, setEndDate] = useState(() => inputDateDaysAgo(0));
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [adjustmentOpen, setAdjustmentOpen] = useState(false);
  const [quantityChange, setQuantityChange] = useState("0.00");
  const [reason, setReason] = useState("");
  const [savingAdjustment, setSavingAdjustment] = useState(false);

  const visibleBranches = useMemo(() => {
    if (!user || user.role === "admin" || user.role === "analyst") {
      return branches;
    }
    return branches.filter((branch) => branch.id === user.branch_id);
  }, [branches, user]);

  const loadOptions = useCallback(async () => {
    if (!token) return;
    const [branchRows, categoryRows, supplierRows] = await Promise.all([
      listBranches(token, { includeInactive: false }),
      listCategories(token),
      listSuppliers(token, { includeInactive: false }),
    ]);
    setBranches(branchRows);
    setCategories(categoryRows);
    setSuppliers(supplierRows);
  }, [token]);

  const loadInventory = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const [inventoryRows, dashboardData] = await Promise.all([
        lowStockOnly
          ? listLowStockInventory(token, {
              branchId: branchId || undefined,
              categoryId: categoryId || undefined,
              supplierId: supplierId || undefined,
              search,
            })
          : listInventory(token, {
              branchId: branchId || undefined,
              categoryId: categoryId || undefined,
              supplierId: supplierId || undefined,
              search,
            }),
        getInventoryDashboard(token, {
          branchId: branchId || undefined,
          categoryId: categoryId || undefined,
          supplierId: supplierId || undefined,
          startDate,
          endDate,
        }),
      ]);
      setItems(inventoryRows);
      setDashboard(dashboardData);
      setLowStockCount(dashboardData.summary.low_stock_product_count);
      if (selectedItem && !inventoryRows.some((item) => item.id === selectedItem.id)) {
        setSelectedItem(null);
        setDetail(null);
      }
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [branchId, categoryId, endDate, lowStockOnly, search, selectedItem, startDate, supplierId, token]);

  const loadMovements = useCallback(async () => {
    if (!token) return;
    try {
      setMovements(
        await listStockMovements(token, {
          productId: selectedItem?.product_id,
          branchId: selectedItem?.branch_id,
          limit: 50,
        }),
      );
    } catch (movementError) {
      setError(errorMessage(movementError));
    }
  }, [selectedItem, token]);

  useEffect(() => {
    void loadOptions().catch((optionsError) => setError(errorMessage(optionsError)));
  }, [loadOptions]);

  useEffect(() => {
    void loadInventory();
  }, [loadInventory]);

  useEffect(() => {
    void loadMovements();
  }, [loadMovements]);

  useEffect(() => {
    if (!token || !selectedItem) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    getProductInventory(token, selectedItem.product_id)
      .then(setDetail)
      .catch((detailError) => setError(errorMessage(detailError)))
      .finally(() => setDetailLoading(false));
  }, [selectedItem, token]);

  const totalStockValue = items.reduce((sum, item) => sum + Number(item.stock_value), 0);
  const totalQuantity = items.reduce((sum, item) => sum + Number(item.quantity_on_hand), 0);
  const authorizedToAdjust = Boolean(user && canAdjustStock(user.role));
  const healthChartData = useMemo(
    () =>
      dashboard?.inventory_health.map((point) => ({
        name: point.status,
        value: point.product_count,
      })) ?? [],
    [dashboard],
  );
  const categoryValueData = useMemo(
    () =>
      dashboard?.stock_value_by_category.slice(0, 8).map((point) => ({
        name: point.category_name,
        value: Number(point.stock_value),
        lowStock: point.low_stock_count,
      })) ?? [],
    [dashboard],
  );

  const openAdjustment = (item: InventoryItem) => {
    setSelectedItem(item);
    setQuantityChange("0.00");
    setReason("");
    setAdjustmentOpen(true);
  };

  const submitAdjustment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !selectedItem) return;
    setSavingAdjustment(true);
    setError(null);
    try {
      const response = await createStockAdjustment(token, {
        product_id: selectedItem.product_id,
        branch_id: selectedItem.branch_id,
        quantity_change: quantityChange,
        reason,
      });
      setSelectedItem(response.inventory);
      setAdjustmentOpen(false);
      await loadInventory();
      await loadMovements();
    } catch (adjustmentError) {
      setError(errorMessage(adjustmentError));
    } finally {
      setSavingAdjustment(false);
    }
  };

  return (
    <section className="page-stack">
      <div className="page-header">
        <div>
          <p className="eyebrow">Inventory engine</p>
          <h2>Inventory and stock ledger</h2>
          <p className="page-description">
            Track product stock by branch, inspect low-stock status, and make auditable manual
            adjustments that always create stock movement records.
          </p>
        </div>
        <div className="page-header-side">
          <span className="role-scope">
            {authorizedToAdjust ? "Adjustment access enabled" : "Read-only inventory view"}
          </span>
        </div>
      </div>

      <div className="filter-bar inventory-filter-bar">
        <div className="search-shell">
          <Search aria-hidden="true" size={16} />
          <input
            aria-label="Search inventory"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search product, SKU, category, supplier"
            type="search"
            value={search}
          />
        </div>
        <div className="filter-actions">
          <select
            aria-label="Filter inventory by branch"
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
            aria-label="Filter inventory by category"
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
            aria-label="Filter inventory by supplier"
            onChange={(event) => setSupplierId(Number(event.target.value))}
            value={supplierId}
          >
            <option value={0}>All suppliers</option>
            {suppliers.map((supplier) => (
              <option key={supplier.id} value={supplier.id}>
                {supplier.name}
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
          <label className="checkbox-row compact">
            <input
              checked={lowStockOnly}
              onChange={(event) => setLowStockOnly(event.target.checked)}
              type="checkbox"
            />
            <span>Low-stock only</span>
          </label>
          <button className="filter-chip" onClick={() => void loadInventory()} type="button">
            <RotateCw aria-hidden="true" size={15} />
            Refresh
          </button>
        </div>
      </div>

      <section className="metric-grid">
        <MetricCard
          metric={{
            label: "Rows Loaded",
            value: String(items.length),
            detail: "Current inventory filter",
            tone: "blue",
          }}
        />
        <MetricCard
          metric={{
            label: "Low-Stock Items",
            value: String(lowStockCount),
            detail: "Quantity <= reorder threshold",
            tone: "amber",
          }}
        />
        <MetricCard
          metric={{
            label: "Units On Hand",
            value: formatQuantity(dashboard?.summary.total_quantity_on_hand ?? String(totalQuantity)),
            detail: "Current stock across dashboard filter",
            tone: "green",
          }}
        />
        <MetricCard
          metric={{
            label: "Stock Value",
            value: formatCurrency(dashboard?.summary.current_stock_value ?? String(totalStockValue)),
            detail: "Quantity x unit cost",
            tone: "slate",
          }}
        />
      </section>

      {error ? <ErrorState message={error} title="Inventory action failed" /> : null}

      {dashboard ? (
        <section className="dashboard-grid">
          <article className="panel chart-panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Inventory health</p>
                <h3>Stock status mix</h3>
              </div>
            </div>
            {healthChartData.length === 0 ? (
              <EmptyState title="No inventory health" message="Stock status appears when inventory rows exist." />
            ) : (
              <ResponsiveContainer height={270} width="100%">
                <PieChart>
                  <Pie data={healthChartData} dataKey="value" innerRadius={58} nameKey="name" outerRadius={94}>
                    {healthChartData.map((entry, index) => (
                      <Cell fill={HEALTH_COLORS[index % HEALTH_COLORS.length]} key={entry.name} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            )}
          </article>

          <article className="panel chart-panel wide">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Stock valuation</p>
                <h3>Stock value by category</h3>
              </div>
            </div>
            {categoryValueData.length === 0 ? (
              <EmptyState title="No category stock" message="Category stock value appears after inventory is loaded." />
            ) : (
              <ResponsiveContainer height={270} width="100%">
                <BarChart data={categoryValueData}>
                  <CartesianGrid stroke="#e7ebf1" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis tickFormatter={(value) => formatCurrency(String(value))} width={78} />
                  <Tooltip formatter={(value) => formatCurrency(String(value))} />
                  <Bar dataKey="value" fill="#276fbf" name="Stock value" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </article>

          <article className="panel wide">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Slow-moving stock</p>
                <h3>No sales in selected period</h3>
              </div>
            </div>
            <div className="table-shell">
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Branch</th>
                    <th>Supplier</th>
                    <th>On Hand</th>
                    <th>Stock Value</th>
                    <th>Last Sale</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.slow_moving_stock.map((item) => (
                    <tr key={`${item.product_id}-${item.branch_id}`}>
                      <td>
                        <strong>{item.product_name}</strong>
                        <span className="subtle-cell">{item.product_sku}</span>
                      </td>
                      <td>{item.branch_name}</td>
                      <td>{item.supplier_name}</td>
                      <td>{formatQuantity(item.quantity_on_hand)}</td>
                      <td>{formatCurrency(item.stock_value)}</td>
                      <td>{item.last_sale_date ?? "No sale found"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </section>
      ) : null}

      <section className="inventory-grid">
        <article className="panel wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Current stock</p>
              <h3>Inventory table</h3>
            </div>
          </div>
          {loading ? <LoadingState label="Loading inventory" /> : null}
          {!loading && items.length === 0 ? (
            <EmptyState
              title="No inventory rows found"
              message="Try changing filters or seed inventory for new products and branches."
            />
          ) : null}
          {!loading && items.length > 0 ? (
            <div className="table-shell inventory-table">
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Branch</th>
                    <th>Category</th>
                    <th>Supplier</th>
                    <th>On Hand</th>
                    <th>Threshold</th>
                    <th>Target</th>
                    <th>Stock Value</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr className={selectedItem?.id === item.id ? "selected-row" : ""} key={item.id}>
                      <td>
                        <strong>{item.product_name}</strong>
                        <span className="subtle-cell">{item.product_sku}</span>
                      </td>
                      <td>{item.branch_name}</td>
                      <td>{item.category_name}</td>
                      <td>{item.supplier_name}</td>
                      <td>{formatQuantity(item.quantity_on_hand)}</td>
                      <td>{formatQuantity(item.reorder_threshold)}</td>
                      <td>{formatQuantity(item.target_stock_level)}</td>
                      <td>{formatCurrency(item.stock_value)}</td>
                      <td>
                        <span className={item.is_low_stock ? "status-badge warning" : "status-badge ok"}>
                          {item.is_low_stock ? "Low stock" : "Healthy"}
                        </span>
                      </td>
                      <td>
                        <div className="table-actions">
                          <button onClick={() => setSelectedItem(item)} type="button">
                            <Eye aria-hidden="true" size={14} />
                            Detail
                          </button>
                          <button disabled={!authorizedToAdjust} onClick={() => openAdjustment(item)} type="button">
                            <SlidersHorizontal aria-hidden="true" size={14} />
                            Adjust
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

        <aside className="panel inventory-side-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Product detail</p>
              <h3>{selectedItem ? selectedItem.product_name : "Select an inventory row"}</h3>
            </div>
          </div>

          {!selectedItem ? (
            <EmptyState
              title="No product selected"
              message="Choose a row to inspect branch stock, thresholds, and recent movements."
            />
          ) : null}

          {selectedItem ? (
            <div className="detail-stack">
              {detailLoading ? <LoadingState label="Loading product detail" /> : null}
              {detail ? (
                <div className="detail-list">
                  <div>
                    <span>SKU</span>
                    <strong>{detail.product_sku}</strong>
                  </div>
                  <div>
                    <span>Total on hand</span>
                    <strong>{formatQuantity(detail.total_quantity_on_hand)}</strong>
                  </div>
                  <div>
                    <span>Total stock value</span>
                    <strong>{formatCurrency(detail.total_stock_value)}</strong>
                  </div>
                  <div>
                    <span>Low-stock branch</span>
                    <strong>{detail.is_low_stock_any_branch ? "Yes" : "No"}</strong>
                  </div>
                </div>
              ) : null}

              <button
                className="action-button primary full-width"
                disabled={!authorizedToAdjust}
                onClick={() => openAdjustment(selectedItem)}
                type="button"
              >
                <PackageCheck aria-hidden="true" size={16} />
                Adjust selected stock
              </button>

              <div>
                <div className="panel-header compact-heading">
                  <div>
                    <p className="eyebrow">Ledger</p>
                    <h3>Recent movements</h3>
                  </div>
                  <History aria-hidden="true" size={17} />
                </div>
                {movements.length === 0 ? (
                  <EmptyState
                    title="No movements yet"
                    message="Manual adjustments, sales, and purchase receipts will appear here."
                  />
                ) : (
                  <div className="movement-list">
                    {movements.map((movement) => (
                      <article key={movement.id}>
                        <div>
                          <strong>{formatMovementType(movement.movement_type)}</strong>
                          <span>{new Date(movement.created_at).toLocaleString()}</span>
                        </div>
                        <b>{formatQuantity(movement.quantity_change)}</b>
                        <p>{movement.reason ?? "No reason provided"}</p>
                      </article>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </aside>
      </section>

      {adjustmentOpen && selectedItem ? (
        <div className="modal-backdrop" role="presentation">
          <section className="modal-card" aria-labelledby="adjustment-title" role="dialog">
            <div className="modal-header">
              <div>
                <p className="eyebrow">Manual stock adjustment</p>
                <h3 id="adjustment-title">{selectedItem.product_name}</h3>
                <p className="page-description">{selectedItem.branch_name}</p>
              </div>
              <button
                aria-label="Close adjustment modal"
                className="icon-button"
                onClick={() => setAdjustmentOpen(false)}
                type="button"
              >
                <X aria-hidden="true" size={18} />
              </button>
            </div>
            <form className="master-form" onSubmit={submitAdjustment}>
              <label>
                Quantity change
                <input
                  required
                  inputMode="decimal"
                  step="0.01"
                  type="text"
                  value={quantityChange}
                  onChange={(event) => setQuantityChange(event.target.value)}
                />
              </label>
              <label>
                Reason
                <textarea
                  required
                  minLength={3}
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="Example: Cycle count correction"
                />
              </label>
              <div className="form-actions">
                <button className="action-button primary" disabled={savingAdjustment} type="submit">
                  {savingAdjustment ? "Saving" : "Save adjustment"}
                </button>
                <button
                  className="action-button secondary"
                  onClick={() => setAdjustmentOpen(false)}
                  type="button"
                >
                  Cancel
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </section>
  );
}
