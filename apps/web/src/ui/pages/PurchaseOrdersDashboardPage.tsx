import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  ClipboardList,
  Edit3,
  PackageCheck,
  Plus,
  RefreshCw,
  Send,
  Truck,
  X,
  XCircle,
} from "lucide-react";

import { ApiError } from "../api/client";
import { getPurchaseOrdersDashboard } from "../api/dashboard";
import { listBranches, listProducts, listSuppliers } from "../api/masterData";
import {
  approvePurchaseOrder,
  cancelPurchaseOrder,
  createPurchaseOrder,
  getPurchaseOrder,
  listPurchaseOrders,
  markPurchaseOrderOrdered,
  receivePurchaseOrder,
  submitPurchaseOrder,
  updatePurchaseOrder,
} from "../api/purchaseOrders";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, LoadingState, MetricCard } from "../components/ui";
import type {
  Branch,
  Product,
  PurchaseOrder,
  PurchaseOrderItem,
  PurchaseOrderListItem,
  PurchaseOrderPayload,
  PurchaseOrdersDashboard,
  PurchaseOrderStatus,
  Supplier,
  UserRole,
} from "../types";
import { formatCurrency, formatQuantity, formatStatus, inputDateDaysAgo } from "../utils/format";

const STATUSES: PurchaseOrderStatus[] = [
  "draft",
  "pending_approval",
  "approved",
  "ordered",
  "partially_received",
  "received",
  "cancelled",
];

const OPEN_STATUSES: PurchaseOrderStatus[] = [
  "draft",
  "pending_approval",
  "approved",
  "ordered",
  "partially_received",
];

type OrderLineForm = {
  product_id: number;
  quantity_ordered: string;
  unit_cost: string;
};

type OrderForm = {
  supplier_id: number;
  branch_id: number;
  order_date: string;
  expected_delivery_date: string;
  items: OrderLineForm[];
};

function emptyLine(): OrderLineForm {
  return { product_id: 0, quantity_ordered: "1.00", unit_cost: "" };
}

function emptyForm(branchId = 0): OrderForm {
  return {
    supplier_id: 0,
    branch_id: branchId,
    order_date: inputDateDaysAgo(0),
    expected_delivery_date: "",
    items: [emptyLine()],
  };
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Could not complete the purchase order request. Check that the backend is running.";
}

function canOperate(role: UserRole | undefined): boolean {
  return role === "admin" || role === "store_manager";
}

function statusBadgeClass(status: string): string {
  return `status-badge po-status-${status}`;
}

function productCost(products: Product[], productId: number): string {
  return products.find((product) => product.id === productId)?.unit_cost ?? "";
}

function cleanDate(value: string): string | null {
  return value.trim() ? value : null;
}

export function PurchaseOrdersDashboardPage() {
  const { token, user } = useAuth();
  const [dashboard, setDashboard] = useState<PurchaseOrdersDashboard | null>(null);
  const [orders, setOrders] = useState<PurchaseOrderListItem[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<PurchaseOrder | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [branchId, setBranchId] = useState(0);
  const [supplierId, setSupplierId] = useState(0);
  const [status, setStatus] = useState<PurchaseOrderStatus | "">("");
  const [search, setSearch] = useState("");
  const [form, setForm] = useState<OrderForm>(() => emptyForm(user?.branch_id ?? 0));
  const [editingId, setEditingId] = useState<number | null>(null);
  const [receiveModalOpen, setReceiveModalOpen] = useState(false);
  const [receiveQuantities, setReceiveQuantities] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const authorizedToWrite = canOperate(user?.role);
  const isAdmin = user?.role === "admin";

  const visibleBranches = useMemo(() => {
    if (!user || user.role === "admin" || user.role === "analyst") {
      return branches;
    }
    return branches.filter((branch) => branch.id === user.branch_id);
  }, [branches, user]);

  const formProducts = useMemo(() => {
    return products.filter((product) => product.is_active && product.supplier_id === form.supplier_id);
  }, [form.supplier_id, products]);

  useEffect(() => {
    if (user && user.role !== "admin" && user.role !== "analyst" && user.branch_id && branchId !== user.branch_id) {
      setBranchId(user.branch_id);
      setForm((current) => ({ ...current, branch_id: user.branch_id ?? current.branch_id }));
    }
  }, [branchId, user]);

  const loadOptions = useCallback(async () => {
    if (!token) return;
    const [branchRows, supplierRows, productRows] = await Promise.all([
      listBranches(token, { includeInactive: false }),
      listSuppliers(token, { includeInactive: false }),
      listProducts(token, { includeInactive: false }),
    ]);
    setBranches(branchRows);
    setSuppliers(supplierRows);
    setProducts(productRows);
  }, [token]);

  const loadDashboard = useCallback(async () => {
    if (!token) return;
    setDashboard(
      await getPurchaseOrdersDashboard(token, {
        branchId: branchId || undefined,
        startDate: inputDateDaysAgo(30),
        endDate: inputDateDaysAgo(0),
      }),
    );
  }, [branchId, token]);

  const loadOrders = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const rows = await listPurchaseOrders(token, {
        branchId: branchId || undefined,
        supplierId: supplierId || undefined,
        status,
        search,
        limit: 100,
      });
      setOrders(rows);
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [branchId, search, status, supplierId, token]);

  const reloadPageData = useCallback(async () => {
    try {
      await Promise.all([loadDashboard(), loadOrders()]);
    } catch (loadError) {
      setError(errorMessage(loadError));
    }
  }, [loadDashboard, loadOrders]);

  useEffect(() => {
    void loadOptions().catch((optionsError) => setError(errorMessage(optionsError)));
  }, [loadOptions]);

  useEffect(() => {
    void reloadPageData();
  }, [reloadPageData]);

  const resetForm = useCallback(() => {
    setEditingId(null);
    setForm(emptyForm(user?.role === "store_manager" ? user.branch_id ?? 0 : 0));
  }, [user]);

  const selectOrder = async (orderId: number) => {
    if (!token) return;
    setDetailLoading(true);
    setError(null);
    try {
      setSelectedOrder(await getPurchaseOrder(token, orderId));
    } catch (detailError) {
      setError(errorMessage(detailError));
    } finally {
      setDetailLoading(false);
    }
  };

  const buildPayload = (): PurchaseOrderPayload | null => {
    const items = form.items
      .filter((item) => item.product_id > 0 && Number(item.quantity_ordered) > 0)
      .map((item) => ({
        product_id: item.product_id,
        quantity_ordered: item.quantity_ordered,
        unit_cost: item.unit_cost || null,
      }));

    if (!form.supplier_id || !form.branch_id || items.length === 0) {
      setError("Select a supplier, branch, and at least one valid line item.");
      return null;
    }

    return {
      supplier_id: form.supplier_id,
      branch_id: form.branch_id,
      order_date: cleanDate(form.order_date),
      expected_delivery_date: cleanDate(form.expected_delivery_date),
      items,
    };
  };

  const handleSaveOrder = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !authorizedToWrite) return;
    const payload = buildPayload();
    if (!payload) return;

    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const savedOrder = editingId
        ? await updatePurchaseOrder(token, editingId, payload)
        : await createPurchaseOrder(token, payload);
      setSelectedOrder(savedOrder);
      setSuccess(`${savedOrder.po_number} saved as ${formatStatus(savedOrder.status)}.`);
      resetForm();
      await reloadPageData();
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (order: PurchaseOrder) => {
    setEditingId(order.id);
    setForm({
      supplier_id: order.supplier_id,
      branch_id: order.branch_id,
      order_date: order.order_date,
      expected_delivery_date: order.expected_delivery_date ?? "",
      items: order.items.map((item) => ({
        product_id: item.product_id,
        quantity_ordered: item.quantity_ordered,
        unit_cost: item.unit_cost,
      })),
    });
  };

  const updateLine = (index: number, patch: Partial<OrderLineForm>) => {
    setForm((current) => ({
      ...current,
      items: current.items.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    }));
  };

  const removeLine = (index: number) => {
    setForm((current) => ({
      ...current,
      items: current.items.length === 1 ? current.items : current.items.filter((_, itemIndex) => itemIndex !== index),
    }));
  };

  const runOrderAction = async (action: () => Promise<PurchaseOrder>, message: string) => {
    if (!token) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updatedOrder = await action();
      setSelectedOrder(updatedOrder);
      setSuccess(message);
      await reloadPageData();
    } catch (actionError) {
      setError(errorMessage(actionError));
    } finally {
      setSaving(false);
    }
  };

  const openReceiveModal = () => {
    if (!selectedOrder) return;
    const nextQuantities: Record<number, string> = {};
    selectedOrder.items.forEach((item) => {
      if (Number(item.remaining_quantity) > 0) {
        nextQuantities[item.id] = item.remaining_quantity;
      }
    });
    setReceiveQuantities(nextQuantities);
    setReceiveModalOpen(true);
  };

  const submitReceiving = async () => {
    if (!token || !selectedOrder) return;
    const items = Object.entries(receiveQuantities)
      .filter(([, value]) => Number(value) > 0)
      .map(([itemId, value]) => ({
        item_id: Number(itemId),
        quantity_received: value,
      }));
    if (items.length === 0) {
      setError("Enter at least one received quantity.");
      return;
    }
    setReceiveModalOpen(false);
    await runOrderAction(
      () => receivePurchaseOrder(token, selectedOrder.id, { items }),
      `${selectedOrder.po_number} receiving saved.`,
    );
  };

  const selectedStatus = selectedOrder?.status as PurchaseOrderStatus | undefined;
  const canSubmit = authorizedToWrite && selectedStatus === "draft";
  const canApprove = isAdmin && selectedStatus === "pending_approval";
  const canMarkOrdered = authorizedToWrite && selectedStatus === "approved";
  const canReceive = authorizedToWrite && (selectedStatus === "ordered" || selectedStatus === "partially_received");
  const canEdit = authorizedToWrite && selectedStatus === "draft";
  const canCancel =
    selectedOrder &&
    OPEN_STATUSES.includes(selectedStatus as PurchaseOrderStatus) &&
    (isAdmin || (user?.role === "store_manager" && ["draft", "pending_approval"].includes(selectedOrder.status)));

  return (
    <section className="page-stack" aria-labelledby="po-dashboard-title">
      <div className="page-header">
        <div>
          <p className="eyebrow">Order workflow</p>
          <h2 id="po-dashboard-title">Purchase orders</h2>
          <p className="page-description">
            Create draft purchase orders, submit them for approval, mark approved orders as placed,
            and receive stock into inventory with a stock movement ledger.
          </p>
        </div>
        <div className="page-header-side">
          <span className="role-scope">{authorizedToWrite ? "Order workflow enabled" : "Read-only order view"}</span>
          <button className="action-button secondary" onClick={() => void reloadPageData()} type="button">
            <RefreshCw aria-hidden="true" size={16} />
            Refresh
          </button>
        </div>
      </div>

      <div className="filter-bar dashboard-filter-bar">
        <div className="search-shell">
          <ClipboardList aria-hidden="true" size={16} />
          <input
            aria-label="Search purchase orders"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search PO, supplier, branch"
            type="search"
            value={search}
          />
        </div>
        <div className="filter-actions">
          <select
            aria-label="Filter purchase orders by branch"
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
            aria-label="Filter purchase orders by supplier"
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
            aria-label="Filter purchase orders by status"
            onChange={(event) => setStatus(event.target.value as PurchaseOrderStatus | "")}
            value={status}
          >
            <option value="">All statuses</option>
            {STATUSES.map((statusOption) => (
              <option key={statusOption} value={statusOption}>
                {formatStatus(statusOption)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {dashboard ? (
        <section className="metric-grid">
          <MetricCard
            metric={{
              label: "Pending Orders",
              value: String(dashboard.summary.pending_purchase_orders),
              detail: `${formatCurrency(dashboard.summary.total_open_order_value)} open value`,
              tone: "amber",
            }}
          />
          <MetricCard
            metric={{
              label: "Pending Approval",
              value: String(dashboard.summary.pending_approval_count),
              detail: "Awaiting admin approval",
              tone: "rose",
            }}
          />
          <MetricCard
            metric={{
              label: "Approved",
              value: String(dashboard.summary.approved_count),
              detail: "Ready to order",
              tone: "blue",
            }}
          />
          <MetricCard
            metric={{
              label: "Overdue",
              value: String(dashboard.summary.overdue_count),
              detail: "Past expected delivery",
              tone: "slate",
            }}
          />
        </section>
      ) : null}

      {error ? <ErrorState message={error} title="Purchase order action failed" /> : null}
      {success ? <div className="success-panel">{success}</div> : null}

      <section className="purchase-order-grid">
        <div className="page-stack">
          <article className="panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Order queue</p>
                <h3>Purchase order list</h3>
              </div>
            </div>
            {loading ? <LoadingState label="Loading purchase orders" /> : null}
            {!loading && orders.length === 0 ? (
              <EmptyState title="No purchase orders" message="Create a draft order or adjust filters." />
            ) : null}
            {!loading && orders.length > 0 ? (
              <div className="table-shell purchase-order-table">
                <table>
                  <thead>
                    <tr>
                      <th>PO</th>
                      <th>Supplier / Branch</th>
                      <th>Status</th>
                      <th>Ordered / Received</th>
                      <th>Expected</th>
                      <th>Total</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map((order) => (
                      <tr className={selectedOrder?.id === order.id ? "selected-row" : ""} key={order.id}>
                        <td>
                          <strong>{order.po_number}</strong>
                          <span className="subtle-cell">{order.order_date}</span>
                        </td>
                        <td>
                          {order.supplier_name}
                          <span className="subtle-cell">{order.branch_name}</span>
                        </td>
                        <td>
                          <span className={statusBadgeClass(order.status)}>{formatStatus(order.status)}</span>
                        </td>
                        <td>
                          {formatQuantity(order.total_quantity_ordered)} /{" "}
                          {formatQuantity(order.total_quantity_received)}
                        </td>
                        <td>{order.expected_delivery_date ?? "Not set"}</td>
                        <td>{formatCurrency(order.total_amount)}</td>
                        <td>
                          <div className="table-actions">
                            <button onClick={() => void selectOrder(order.id)} type="button">
                              View
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

          <article className="panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Selected order</p>
                <h3>{selectedOrder ? selectedOrder.po_number : "Order detail"}</h3>
              </div>
              {selectedOrder ? (
                <span className={statusBadgeClass(selectedOrder.status)}>{formatStatus(selectedOrder.status)}</span>
              ) : null}
            </div>

            {detailLoading ? <LoadingState label="Loading order detail" /> : null}
            {!detailLoading && !selectedOrder ? (
              <EmptyState title="No order selected" message="Select an order to approve, place, receive, or edit it." />
            ) : null}
            {!detailLoading && selectedOrder ? (
              <div className="detail-stack">
                <div className="table-actions">
                  <button disabled={!canEdit || saving} onClick={() => startEdit(selectedOrder)} type="button">
                    <Edit3 aria-hidden="true" size={14} />
                    Edit Draft
                  </button>
                  <button
                    disabled={!canSubmit || saving}
                    onClick={() =>
                      void runOrderAction(
                        () => submitPurchaseOrder(token ?? "", selectedOrder.id),
                        `${selectedOrder.po_number} submitted for approval.`,
                      )
                    }
                    type="button"
                  >
                    <Send aria-hidden="true" size={14} />
                    Submit
                  </button>
                  <button
                    disabled={!canApprove || saving}
                    onClick={() =>
                      void runOrderAction(
                        () => approvePurchaseOrder(token ?? "", selectedOrder.id),
                        `${selectedOrder.po_number} approved.`,
                      )
                    }
                    type="button"
                  >
                    <CheckCircle2 aria-hidden="true" size={14} />
                    Approve
                  </button>
                  <button
                    disabled={!canMarkOrdered || saving}
                    onClick={() =>
                      void runOrderAction(
                        () => markPurchaseOrderOrdered(token ?? "", selectedOrder.id),
                        `${selectedOrder.po_number} marked as ordered.`,
                      )
                    }
                    type="button"
                  >
                    <Truck aria-hidden="true" size={14} />
                    Mark Ordered
                  </button>
                  <button disabled={!canReceive || saving} onClick={openReceiveModal} type="button">
                    <PackageCheck aria-hidden="true" size={14} />
                    Receive
                  </button>
                  <button
                    disabled={!canCancel || saving}
                    onClick={() =>
                      void runOrderAction(
                        () => cancelPurchaseOrder(token ?? "", selectedOrder.id),
                        `${selectedOrder.po_number} cancelled.`,
                      )
                    }
                    type="button"
                  >
                    <XCircle aria-hidden="true" size={14} />
                    Cancel
                  </button>
                </div>

                <div className="detail-list">
                  <div>
                    <span>Supplier</span>
                    <strong>{selectedOrder.supplier_name}</strong>
                  </div>
                  <div>
                    <span>Branch</span>
                    <strong>{selectedOrder.branch_name}</strong>
                  </div>
                  <div>
                    <span>Created by</span>
                    <strong>{selectedOrder.created_by_name}</strong>
                  </div>
                  <div>
                    <span>Approved by</span>
                    <strong>{selectedOrder.approved_by_name ?? "Not approved"}</strong>
                  </div>
                </div>

                <div className="table-shell purchase-order-line-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Product</th>
                        <th>Ordered</th>
                        <th>Received</th>
                        <th>Remaining</th>
                        <th>Unit Cost</th>
                        <th>Line Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedOrder.items.map((item) => (
                        <tr key={item.id}>
                          <td>
                            <strong>{item.product_name}</strong>
                            <span className="subtle-cell">{item.product_sku}</span>
                          </td>
                          <td>{formatQuantity(item.quantity_ordered)}</td>
                          <td>{formatQuantity(item.quantity_received)}</td>
                          <td>{formatQuantity(item.remaining_quantity)}</td>
                          <td>{formatCurrency(item.unit_cost)}</td>
                          <td>{formatCurrency(item.line_total)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </article>
        </div>

        <aside className="panel purchase-order-form-panel">
          <form className="master-form" onSubmit={handleSaveOrder}>
            <div className="panel-header">
              <div>
                <p className="eyebrow">Manual order</p>
                <h3>{editingId ? "Edit draft" : "Create draft"}</h3>
              </div>
              {editingId ? (
                <button className="icon-button" onClick={resetForm} type="button" aria-label="Cancel editing">
                  <X aria-hidden="true" size={16} />
                </button>
              ) : null}
            </div>
            {!authorizedToWrite ? (
              <EmptyState title="Read-only access" message="This role can review orders but cannot create or edit them." />
            ) : (
              <>
                <label>
                  Branch
                  <select
                    required
                    value={form.branch_id}
                    onChange={(event) => setForm({ ...form, branch_id: Number(event.target.value) })}
                  >
                    <option value={0}>Select branch</option>
                    {visibleBranches.map((branch) => (
                      <option key={branch.id} value={branch.id}>
                        {branch.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Supplier
                  <select
                    required
                    value={form.supplier_id}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        supplier_id: Number(event.target.value),
                        items: [emptyLine()],
                      })
                    }
                  >
                    <option value={0}>Select supplier</option>
                    {suppliers.map((supplier) => (
                      <option key={supplier.id} value={supplier.id}>
                        {supplier.name}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="form-grid two">
                  <label>
                    Order date
                    <input
                      type="date"
                      value={form.order_date}
                      onChange={(event) => setForm({ ...form, order_date: event.target.value })}
                    />
                  </label>
                  <label>
                    Expected date
                    <input
                      type="date"
                      value={form.expected_delivery_date}
                      onChange={(event) => setForm({ ...form, expected_delivery_date: event.target.value })}
                    />
                  </label>
                </div>

                <div className="po-line-form-list">
                  {form.items.map((line, index) => (
                    <div className="po-line-form" key={`${index}-${line.product_id}`}>
                      <label>
                        Product
                        <select
                          required
                          value={line.product_id}
                          onChange={(event) => {
                            const productId = Number(event.target.value);
                            updateLine(index, {
                              product_id: productId,
                              unit_cost: productCost(products, productId),
                            });
                          }}
                        >
                          <option value={0}>Select product</option>
                          {formProducts.map((product) => (
                            <option key={product.id} value={product.id}>
                              {product.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="form-grid two">
                        <label>
                          Quantity
                          <input
                            min="0.01"
                            step="0.01"
                            type="number"
                            value={line.quantity_ordered}
                            onChange={(event) => updateLine(index, { quantity_ordered: event.target.value })}
                          />
                        </label>
                        <label>
                          Unit cost
                          <input
                            min="0"
                            step="0.01"
                            type="number"
                            value={line.unit_cost}
                            onChange={(event) => updateLine(index, { unit_cost: event.target.value })}
                          />
                        </label>
                      </div>
                      <button
                        className="action-button secondary full-width"
                        disabled={form.items.length === 1}
                        onClick={() => removeLine(index)}
                        type="button"
                      >
                        Remove line
                      </button>
                    </div>
                  ))}
                </div>

                <button
                  className="action-button secondary full-width"
                  onClick={() => setForm((current) => ({ ...current, items: [...current.items, emptyLine()] }))}
                  type="button"
                >
                  <Plus aria-hidden="true" size={15} />
                  Add line
                </button>
                <button className="action-button primary full-width" disabled={saving} type="submit">
                  {saving ? "Saving" : editingId ? "Save draft changes" : "Create draft PO"}
                </button>
              </>
            )}
          </form>
        </aside>
      </section>

      {receiveModalOpen && selectedOrder ? (
        <ReceiveModal
          onClose={() => setReceiveModalOpen(false)}
          onSubmit={() => void submitReceiving()}
          order={selectedOrder}
          quantities={receiveQuantities}
          saving={saving}
          setQuantities={setReceiveQuantities}
        />
      ) : null}
    </section>
  );
}

function ReceiveModal({
  onClose,
  onSubmit,
  order,
  quantities,
  saving,
  setQuantities,
}: {
  onClose: () => void;
  onSubmit: () => void;
  order: PurchaseOrder;
  quantities: Record<number, string>;
  saving: boolean;
  setQuantities: (value: Record<number, string>) => void;
}) {
  const receivableItems = order.items.filter((item) => Number(item.remaining_quantity) > 0);

  return (
    <div className="modal-backdrop" role="presentation">
      <div className="modal-card receive-modal" role="dialog" aria-modal="true" aria-labelledby="receive-order-title">
        <div className="modal-header">
          <div>
            <p className="eyebrow">Receive stock</p>
            <h3 id="receive-order-title">{order.po_number}</h3>
          </div>
          <button className="icon-button" onClick={onClose} type="button" aria-label="Close receive modal">
            <X aria-hidden="true" size={16} />
          </button>
        </div>
        <div className="receive-line-list">
          {receivableItems.map((item: PurchaseOrderItem) => (
            <label key={item.id}>
              <span>
                {item.product_name}
                <b>Remaining {formatQuantity(item.remaining_quantity)}</b>
              </span>
              <input
                min="0"
                max={item.remaining_quantity}
                step="0.01"
                type="number"
                value={quantities[item.id] ?? ""}
                onChange={(event) =>
                  setQuantities({
                    ...quantities,
                    [item.id]: event.target.value,
                  })
                }
              />
            </label>
          ))}
        </div>
        <div className="sale-button-row">
          <button className="action-button secondary" onClick={onClose} type="button">
            Cancel
          </button>
          <button className="action-button primary" disabled={saving} onClick={onSubmit} type="button">
            {saving ? "Receiving" : "Save receiving"}
          </button>
        </div>
      </div>
    </div>
  );
}
