import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckSquare, RefreshCw, ShoppingCart } from "lucide-react";

import { ApiError } from "../api/client";
import { listBranches, listCategories, listSuppliers } from "../api/masterData";
import { createPurchaseOrdersFromRecommendations } from "../api/purchaseOrders";
import { listReorderRecommendations } from "../api/reorder";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, LoadingState, MetricCard } from "../components/ui";
import type {
  Branch,
  Category,
  PurchaseOrderDraft,
  ReorderPriority,
  ReorderRecommendation,
  Supplier,
  UserRole,
} from "../types";
import { formatCurrency, formatQuantity, formatStatus, inputDateDaysAgo } from "../utils/format";

const PRIORITIES: ReorderPriority[] = ["critical", "high", "medium", "low"];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Could not complete the request. Check that the backend is running.";
}

function recommendationKey(recommendation: ReorderRecommendation): string {
  return `${recommendation.product_id}:${recommendation.branch_id}`;
}

function canCreateDraftOrders(role: UserRole): boolean {
  return role === "admin" || role === "store_manager";
}

function priorityTone(priority: ReorderPriority): string {
  return `priority-badge ${priority}`;
}

export function LowStockReorderPage() {
  const { token, user } = useAuth();
  const [recommendations, setRecommendations] = useState<ReorderRecommendation[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [branchId, setBranchId] = useState(0);
  const [categoryId, setCategoryId] = useState(0);
  const [supplierId, setSupplierId] = useState(0);
  const [priority, setPriority] = useState<ReorderPriority | "">("");
  const [lookbackDays, setLookbackDays] = useState(30);
  const [asOfDate, setAsOfDate] = useState(() => inputDateDaysAgo(0));
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(() => new Set());
  const [quantityOverrides, setQuantityOverrides] = useState<Record<string, string>>({});
  const [createdOrders, setCreatedOrders] = useState<PurchaseOrderDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const visibleBranches = useMemo(() => {
    if (!user || user.role === "admin" || user.role === "analyst") {
      return branches;
    }
    return branches.filter((branch) => branch.id === user.branch_id);
  }, [branches, user]);

  const authorizedToCreate = Boolean(user && canCreateDraftOrders(user.role));

  useEffect(() => {
    if (user && user.role !== "admin" && user.role !== "analyst" && user.branch_id && branchId !== user.branch_id) {
      setBranchId(user.branch_id);
    }
  }, [branchId, user]);

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

  const loadRecommendations = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const rows = await listReorderRecommendations(token, {
        branchId: branchId || undefined,
        categoryId: categoryId || undefined,
        supplierId: supplierId || undefined,
        priority: priority || undefined,
        lookbackDays,
        asOfDate,
      });
      setRecommendations(rows);
      setQuantityOverrides((current) => {
        const next = { ...current };
        rows.forEach((row) => {
          const key = recommendationKey(row);
          if (next[key] === undefined) {
            next[key] = row.suggested_reorder_quantity;
          }
        });
        return next;
      });
      setSelectedKeys((current) => {
        const validKeys = new Set(rows.map(recommendationKey));
        return new Set([...current].filter((key) => validKeys.has(key)));
      });
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [asOfDate, branchId, categoryId, lookbackDays, priority, supplierId, token]);

  useEffect(() => {
    void loadOptions().catch((optionsError) => setError(errorMessage(optionsError)));
  }, [loadOptions]);

  useEffect(() => {
    void loadRecommendations();
  }, [loadRecommendations]);

  const priorityCounts = useMemo(() => {
    return recommendations.reduce<Record<ReorderPriority, number>>(
      (counts, recommendation) => {
        counts[recommendation.priority] += 1;
        return counts;
      },
      { critical: 0, high: 0, medium: 0, low: 0 },
    );
  }, [recommendations]);

  const selectedRecommendations = useMemo(() => {
    return recommendations.filter((recommendation) => selectedKeys.has(recommendationKey(recommendation)));
  }, [recommendations, selectedKeys]);

  const selectedEstimatedCost = selectedRecommendations.reduce((sum, recommendation) => {
    const override = Number(quantityOverrides[recommendationKey(recommendation)] ?? recommendation.suggested_reorder_quantity);
    return sum + Math.max(override, 0) * Number(recommendation.unit_cost);
  }, 0);

  const toggleRecommendation = (recommendation: ReorderRecommendation) => {
    const key = recommendationKey(recommendation);
    setSelectedKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const selectPriorityItems = () => {
    setSelectedKeys(
      new Set(
        recommendations
          .filter((recommendation) => recommendation.priority === "critical" || recommendation.priority === "high")
          .map(recommendationKey),
      ),
    );
  };

  const createDraftOrders = async () => {
    if (!token || selectedRecommendations.length === 0) return;
    setSaving(true);
    setError(null);
    setCreatedOrders([]);
    try {
      const orders = await createPurchaseOrdersFromRecommendations(token, {
        items: selectedRecommendations.map((recommendation) => ({
          product_id: recommendation.product_id,
          branch_id: recommendation.branch_id,
          quantity_ordered:
            quantityOverrides[recommendationKey(recommendation)] || recommendation.suggested_reorder_quantity,
        })),
      });
      setCreatedOrders(orders);
      setSelectedKeys(new Set());
    } catch (createError) {
      setError(errorMessage(createError));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="page-stack" aria-labelledby="reorder-title">
      <div className="page-header">
        <div>
          <p className="eyebrow">Purchasing signal</p>
          <h2 id="reorder-title">Low stock and reorder</h2>
          <p className="page-description">
            Prioritize reorder decisions from current stock, recent sales velocity, target stock,
            supplier lead time, and existing quantity on order.
          </p>
        </div>
        <div className="page-header-side">
          <span className="role-scope">
            {authorizedToCreate ? "Draft PO creation enabled" : "Read-only recommendations"}
          </span>
          <button className="action-button secondary" onClick={() => void loadRecommendations()} type="button">
            <RefreshCw aria-hidden="true" size={16} />
            Refresh
          </button>
        </div>
      </div>

      <div className="filter-bar dashboard-filter-bar">
        <div className="filter-actions">
          <select
            aria-label="Filter reorder recommendations by branch"
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
            aria-label="Filter reorder recommendations by category"
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
            aria-label="Filter reorder recommendations by supplier"
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
          <select
            aria-label="Filter reorder recommendations by priority"
            onChange={(event) => setPriority(event.target.value as ReorderPriority | "")}
            value={priority}
          >
            <option value="">All priorities</option>
            {PRIORITIES.map((priorityOption) => (
              <option key={priorityOption} value={priorityOption}>
                {formatStatus(priorityOption)}
              </option>
            ))}
          </select>
          <label className="date-filter">
            Sales window
            <input
              min={1}
              max={365}
              onChange={(event) => setLookbackDays(Number(event.target.value))}
              type="number"
              value={lookbackDays}
            />
          </label>
          <label className="date-filter">
            As of
            <input onChange={(event) => setAsOfDate(event.target.value)} type="date" value={asOfDate} />
          </label>
        </div>
      </div>

      <section className="metric-grid">
        <MetricCard
          metric={{
            label: "Critical",
            value: String(priorityCounts.critical),
            detail: "Zero stock or runout before lead time",
            tone: "rose",
          }}
        />
        <MetricCard
          metric={{
            label: "High Priority",
            value: String(priorityCounts.high),
            detail: "At or below reorder threshold",
            tone: "amber",
          }}
        />
        <MetricCard
          metric={{
            label: "Selected Items",
            value: String(selectedRecommendations.length),
            detail: "Rows selected for draft orders",
            tone: "blue",
          }}
        />
        <MetricCard
          metric={{
            label: "Selected Cost",
            value: formatCurrency(selectedEstimatedCost),
            detail: "Override quantity x unit cost",
            tone: "green",
          }}
        />
      </section>

      {error ? <ErrorState message={error} title="Reorder action failed" /> : null}
      {createdOrders.length > 0 ? (
        <div className="success-panel">
          Created {createdOrders.length} draft purchase order{createdOrders.length === 1 ? "" : "s"}:{" "}
          {createdOrders.map((order) => order.po_number).join(", ")}.
        </div>
      ) : null}

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Recommendation list</p>
            <h3>Reorder recommendations</h3>
          </div>
          <div className="table-actions">
            <button onClick={selectPriorityItems} type="button">
              <CheckSquare aria-hidden="true" size={14} />
              Select critical/high
            </button>
            <button
              disabled={!authorizedToCreate || saving || selectedRecommendations.length === 0}
              onClick={() => void createDraftOrders()}
              type="button"
            >
              <ShoppingCart aria-hidden="true" size={14} />
              {saving ? "Creating" : "Create draft PO"}
            </button>
          </div>
        </div>

        {loading ? <LoadingState label="Loading reorder recommendations" /> : null}
        {!loading && recommendations.length === 0 ? (
          <EmptyState title="No recommendations" message="Try a different branch, supplier, or priority filter." />
        ) : null}
        {!loading && recommendations.length > 0 ? (
          <div className="table-shell reorder-table">
            <table>
              <thead>
                <tr>
                  <th>Select</th>
                  <th>Priority</th>
                  <th>Product</th>
                  <th>Branch</th>
                  <th>Supplier</th>
                  <th>Current / Threshold</th>
                  <th>On Order</th>
                  <th>Avg Daily Sales</th>
                  <th>Lead Time Demand</th>
                  <th>Days Left</th>
                  <th>Suggested Qty</th>
                  <th>Override Qty</th>
                  <th>Est. Cost</th>
                </tr>
              </thead>
              <tbody>
                {recommendations.map((recommendation) => {
                  const key = recommendationKey(recommendation);
                  const selected = selectedKeys.has(key);
                  const overrideQuantity = quantityOverrides[key] ?? recommendation.suggested_reorder_quantity;
                  const estimatedCost = Math.max(Number(overrideQuantity) || 0, 0) * Number(recommendation.unit_cost);
                  return (
                    <tr className={selected ? "selected-row" : ""} key={key}>
                      <td>
                        <input
                          aria-label={`Select ${recommendation.product_name}`}
                          checked={selected}
                          disabled={!authorizedToCreate}
                          onChange={() => toggleRecommendation(recommendation)}
                          type="checkbox"
                        />
                      </td>
                      <td>
                        <span className={priorityTone(recommendation.priority)}>
                          {formatStatus(recommendation.priority)}
                        </span>
                      </td>
                      <td>
                        <strong>{recommendation.product_name}</strong>
                        <span className="subtle-cell">{recommendation.product_sku}</span>
                      </td>
                      <td>{recommendation.branch_name}</td>
                      <td>{recommendation.supplier_name}</td>
                      <td>
                        {formatQuantity(recommendation.current_stock)} /{" "}
                        {formatQuantity(recommendation.reorder_threshold)}
                      </td>
                      <td>{formatQuantity(recommendation.quantity_on_order)}</td>
                      <td>{formatQuantity(recommendation.average_daily_sales)}</td>
                      <td>{formatQuantity(recommendation.expected_demand_during_lead_time)}</td>
                      <td>
                        {recommendation.days_until_stockout === null
                          ? "No recent sales"
                          : `${formatQuantity(recommendation.days_until_stockout)} days`}
                      </td>
                      <td>{formatQuantity(recommendation.suggested_reorder_quantity)}</td>
                      <td>
                        <input
                          aria-label={`Override quantity for ${recommendation.product_name}`}
                          disabled={!authorizedToCreate}
                          inputMode="decimal"
                          onChange={(event) =>
                            setQuantityOverrides((current) => ({
                              ...current,
                              [key]: event.target.value,
                            }))
                          }
                          type="text"
                          value={overrideQuantity}
                        />
                      </td>
                      <td>{formatCurrency(estimatedCost)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </section>
  );
}
