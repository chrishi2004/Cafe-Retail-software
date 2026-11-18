import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { PackagePlus, Plus, RefreshCw, Trash2 } from "lucide-react";

import { listBranches, listProducts, listSuppliers } from "../api/masterData";
import { createStockIntake, listStockIntakes, type StockIntake } from "../api/stockIntakes";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, LoadingState } from "../components/ui";
import type { Branch, Product, Supplier } from "../types";
import { cafeToday } from "../utils/cafeDates";
import { formatCurrency } from "../utils/format";

type FeedLine = { product_id: number; quantity: string; unit_cost: string };
const emptyLine = (): FeedLine => ({ product_id: 0, quantity: "", unit_cost: "" });

const PAYMENT_MODES = [
  ["cash", "Cash"],
  ["upi", "UPI"],
  ["card", "Card"],
  ["bank_transfer", "Bank Transfer"],
  ["credit", "Credit / Pay Later"],
  ["other", "Other"],
] as const;

export function CafeStockFeedPage() {
  const { token, user } = useAuth();
  const [branches, setBranches] = useState<Branch[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [history, setHistory] = useState<StockIntake[]>([]);
  const [branchId, setBranchId] = useState(user?.branch_id ?? 0);
  const [supplierId, setSupplierId] = useState(0);
  const [vendorName, setVendorName] = useState("");
  const [purchaseDate, setPurchaseDate] = useState(cafeToday());
  const [paymentMode, setPaymentMode] = useState("cash");
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [recordExpense, setRecordExpense] = useState(true);
  const [lines, setLines] = useState<FeedLine[]>([emptyLine()]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const canWrite = ["super_admin", "admin", "store_manager"].includes(user?.server_role ?? "");
  const goods = useMemo(() => products.filter((row) => row.is_active && row.item_type !== "service"), [products]);
  const total = useMemo(
    () => lines.reduce((sum, line) => sum + (Number(line.quantity) || 0) * (Number(line.unit_cost) || 0), 0),
    [lines],
  );

  const loadHistory = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      setHistory(await listStockIntakes(token, { branchId: branchId || undefined }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [branchId, token]);

  useEffect(() => {
    if (!token) return;
    Promise.all([
      listBranches(token, { includeInactive: false }),
      listSuppliers(token, { includeInactive: false }),
      listProducts(token, { includeInactive: false }),
    ]).then(([branchRows, supplierRows, productRows]) => {
      setBranches(branchRows);
      setSuppliers(supplierRows);
      setProducts(productRows);
      setBranchId((current) => current || user?.branch_id || branchRows[0]?.id || 0);
    }).catch((err: Error) => setError(err.message));
  }, [token, user?.branch_id]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const updateLine = (index: number, patch: Partial<FeedLine>) => {
    setLines((current) => current.map((line, itemIndex) => {
      if (itemIndex !== index) return line;
      const next = { ...line, ...patch };
      if (patch.product_id !== undefined) {
        const product = goods.find((row) => row.id === patch.product_id);
        next.unit_cost = product?.unit_cost ?? "";
      }
      return next;
    }));
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !canWrite || !branchId) return;
    const items = lines
      .filter((line) => line.product_id > 0 && Number(line.quantity) > 0)
      .map((line) => ({ ...line, unit_cost: line.unit_cost || "0" }));
    if (!items.length) {
      setError("Add at least one valid stock item and quantity.");
      return;
    }
    if (!supplierId && !vendorName.trim()) {
      setError("Select a supplier or enter a vendor/source.");
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const saved = await createStockIntake(
        token,
        {
          branch_id: branchId,
          supplier_id: supplierId || null,
          purchase_date: purchaseDate,
          vendor_name: vendorName.trim() || null,
          reference_number: reference.trim() || null,
          payment_mode: paymentMode,
          record_expense: recordExpense,
          notes: notes.trim() || null,
          items,
        },
        crypto.randomUUID(),
      );
      setSuccess(`Stock feed #${saved.id} posted to ${saved.branch_name}. ${saved.expense_id ? `Expense #${saved.expense_id} linked.` : ""}`);
      setLines([emptyLine()]);
      setReference("");
      setNotes("");
      await loadHistory();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="page-stack">
      <div className="page-header">
        <div>
          <p className="eyebrow">Café purchasing and stock receipt</p>
          <h2>Inventory stock feed</h2>
          <p className="page-description">
            Receive groceries, vegetables, LPG/gas, dairy, beverages, packaging, cleaning consumables and other raw stock into the selected shop.
          </p>
        </div>
        <button className="action-button secondary" onClick={() => void loadHistory()} type="button"><RefreshCw size={16} />Refresh</button>
      </div>

      {error ? <ErrorState message={error} title="Stock feed failed" /> : null}
      {success ? <div className="success-banner">{success}</div> : null}

      {!goods.length ? (
        <div className="state-panel">
          <PackagePlus size={22} />
          <h3>Create inventory items first</h3>
          <p>Add raw items under Inventory Items and create their category/supplier before feeding stock.</p>
        </div>
      ) : null}

      <div className="content-grid stock-feed-grid">
        <article className="panel">
          <div className="panel-header"><div><p className="eyebrow">New receipt</p><h3>Add purchased stock</h3></div><strong>{formatCurrency(total)}</strong></div>
          {!canWrite ? <p className="page-description">Your role has read-only stock-feed access.</p> : (
            <form className="master-form" onSubmit={submit}>
              <div className="form-grid two">
                <label>Shop / branch
                  <select value={branchId} onChange={(e) => setBranchId(Number(e.target.value))} required>
                    <option value={0}>Select branch</option>
                    {branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
                  </select>
                </label>
                <label>Purchase date <input type="date" value={purchaseDate} onChange={(e) => setPurchaseDate(e.target.value)} required /></label>
              </div>
              <div className="form-grid two">
                <label>Saved supplier
                  <select value={supplierId} onChange={(e) => setSupplierId(Number(e.target.value))}>
                    <option value={0}>Other / local vendor</option>
                    {suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
                  </select>
                </label>
                <label>Vendor/source <input placeholder="Local kirana, vegetable market, gas agency…" value={vendorName} onChange={(e) => setVendorName(e.target.value)} /></label>
              </div>

              <div className="stock-feed-lines">
                {lines.map((line, index) => {
                  const product = goods.find((row) => row.id === line.product_id);
                  return (
                    <div className="stock-feed-line" key={index}>
                      <label>Inventory item
                        <select value={line.product_id} onChange={(e) => updateLine(index, { product_id: Number(e.target.value) })}>
                          <option value={0}>Select item</option>
                          {goods.map((row) => <option key={row.id} value={row.id}>{row.name} ({row.unit_of_measure})</option>)}
                        </select>
                      </label>
                      <label>Quantity ({product?.unit_of_measure ?? "unit"}) <input min="0.01" step="0.01" type="number" value={line.quantity} onChange={(e) => updateLine(index, { quantity: e.target.value })} /></label>
                      <label>Unit cost <input min="0" step="0.01" type="number" value={line.unit_cost} onChange={(e) => updateLine(index, { unit_cost: e.target.value })} /></label>
                      <button className="icon-button" aria-label="Remove stock line" disabled={lines.length === 1} onClick={() => setLines((current) => current.filter((_, i) => i !== index))} type="button"><Trash2 size={16} /></button>
                    </div>
                  );
                })}
              </div>
              <button className="action-button secondary" onClick={() => setLines((current) => [...current, emptyLine()])} type="button"><Plus size={16} />Add item</button>

              <div className="form-grid two">
                <label>Payment mode
                  <select value={paymentMode} onChange={(e) => setPaymentMode(e.target.value)}>
                    {PAYMENT_MODES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </label>
                <label>Bill / reference <input maxLength={160} value={reference} onChange={(e) => setReference(e.target.value)} /></label>
              </div>
              <label className="checkbox-row">
                <input type="checkbox" checked={recordExpense} onChange={(e) => setRecordExpense(e.target.checked)} />
                Also record this purchase in branch expenses
              </label>
              <label>Notes <textarea maxLength={1000} value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
              <button className="action-button primary" disabled={saving || !branchId || total < 0} type="submit">
                {saving ? "Posting stock…" : "Post stock feed"}
              </button>
            </form>
          )}
        </article>

        <article className="panel">
          <div className="panel-header"><div><p className="eyebrow">Recent receipts</p><h3>Stock feed history</h3></div></div>
          {loading ? <LoadingState label="Loading stock feed" /> : null}
          {!loading && !history.length ? <EmptyState title="No stock feeds" message="Purchased stock receipts will appear here." /> : null}
          {!loading && history.length ? (
            <div className="table-shell">
              <table>
                <thead><tr><th>Date / Branch</th><th>Vendor</th><th>Items</th><th>Payment</th><th>Total</th><th>Expense</th></tr></thead>
                <tbody>
                  {history.map((row) => (
                    <tr key={row.id}>
                      <td><strong>{row.purchase_date}</strong><span>{row.branch_name}</span></td>
                      <td>{row.vendor_name ?? row.supplier_name ?? "Not recorded"}{row.reference_number ? <span>{row.reference_number}</span> : null}</td>
                      <td>{row.item_count}<span>{row.items.slice(0, 2).map((item) => item.product_name).join(", ")}{row.items.length > 2 ? "…" : ""}</span></td>
                      <td>{row.payment_mode.replaceAll("_", " ")}</td>
                      <td>{formatCurrency(row.total_amount)}</td>
                      <td>{row.expense_id ? `#${row.expense_id}` : "Not linked"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </article>
      </div>
    </section>
  );
}
