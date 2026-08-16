import { useCallback, useEffect, useMemo, useState } from "react";

import { listCafeTables, listMenuItems, openTableSession, type CafeTable, type MenuItem, type TableSessionType } from "../api/cafe";
import { createCafeStaffOrder } from "../api/cafeOrders";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Could not create Cafe order.";
}

export function CafeNewOrderPage() {
  const { token } = useAuth();
  const [items, setItems] = useState<MenuItem[]>([]);
  const [tables, setTables] = useState<CafeTable[]>([]);
  const [cart, setCart] = useState<Record<number, number>>({});
  const [orderType, setOrderType] = useState<TableSessionType>("dine_in");
  const [tableId, setTableId] = useState<number | null>(null);
  const [branchId, setBranchId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [menuRows, tableRows] = await Promise.all([listMenuItems(token), listCafeTables(token)]);
      setItems(menuRows.filter((row) => row.available && row.is_active));
      const activeTables = tableRows.filter((row) => row.is_active);
      setTables(activeTables);
      if (!tableId && activeTables[0]) setTableId(activeTables[0].id);
      if (!branchId && activeTables[0]) setBranchId(activeTables[0].branch_id);
      setError(null);
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [branchId, tableId, token]);

  useEffect(() => { void load(); }, [load]);

  const selectedTable = tables.find((row) => row.id === tableId) ?? null;
  const visibleItems = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return items.filter((item) => !needle || item.name.toLowerCase().includes(needle));
  }, [items, search]);
  const total = useMemo(
    () => items.reduce((sum, item) => sum + Number(item.selling_price) * (cart[item.id] ?? 0), 0),
    [cart, items],
  );

  const add = (item: MenuItem) => setCart((current) => ({ ...current, [item.id]: (current[item.id] ?? 0) + 1 }));
  const change = (item: MenuItem, delta: number) => setCart((current) => {
    const next = Math.max(0, (current[item.id] ?? 0) + delta);
    const updated = { ...current };
    if (next) updated[item.id] = next; else delete updated[item.id];
    return updated;
  });

  const submit = async () => {
    if (!token || saving) return;
    const selected = items.filter((item) => (cart[item.id] ?? 0) > 0);
    if (!selected.length) { setError("Add at least one menu item."); return; }
    if (!branchId) { setError("Select a Cafe branch."); return; }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      let sessionPublicId: string | undefined;
      if (orderType === "dine_in") {
        if (!selectedTable) throw new Error("Select a table for dine-in service.");
        if (selectedTable.branch_id !== branchId) throw new Error("Selected table is outside the chosen branch.");
        sessionPublicId = selectedTable.active_session_public_id ?? undefined;
        if (!sessionPublicId) {
          const opened = await openTableSession(token, selectedTable.id, "dine_in");
          sessionPublicId = opened.public_id;
        }
      }
      const order = await createCafeStaffOrder(token, {
        order_type: orderType,
        branch_id: branchId,
        table_session_public_id: sessionPublicId,
        customer_notes: notes.trim() || undefined,
        items: selected.map((item) => ({
          menu_item_public_id: item.public_id ?? String(item.id),
          quantity: cart[item.id],
        })),
      });
      setSuccess(`${order.order_number} placed at ₹${order.estimated_total}. Backend pricing is authoritative.`);
      setCart({});
      setNotes("");
      await load();
    } catch (submitError) {
      setError(errorMessage(submitError));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingState label="Loading Cafe order entry" />;

  return (
    <section className="page-stack">
      <div className="page-header"><div><p className="eyebrow">Staff order entry</p><h2>New Cafe Order</h2><p className="page-description">Dine-in, takeaway and counter orders use the same backend menu pricing and item snapshot engine as QR orders.</p></div></div>
      {error ? <ErrorState message={error} /> : null}
      {success ? <p className="success-message">{success}</p> : null}
      <div className="filter-row">
        <label>Mode <select value={orderType} onChange={(event) => setOrderType(event.target.value as TableSessionType)}><option value="dine_in">Dine in</option><option value="takeaway">Takeaway</option><option value="counter">Counter</option></select></label>
        <label>Branch <select value={branchId ?? ""} onChange={(event) => setBranchId(Number(event.target.value))}>{Array.from(new Map(tables.map((table) => [table.branch_id, table.branch_id])).keys()).map((id) => <option key={id} value={id}>Branch {id}</option>)}</select></label>
        {orderType === "dine_in" ? <label>Table <select value={tableId ?? ""} onChange={(event) => { const id = Number(event.target.value); setTableId(id); const table = tables.find((row) => row.id === id); if (table) setBranchId(table.branch_id); }}>{tables.map((table) => <option key={table.id} value={table.id}>{table.table_code} · {table.display_name}</option>)}</select></label> : null}
        <label>Search <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Menu item" /></label>
      </div>
      <div className="two-column-grid">
        <div className="panel wide">
          <div className="table-wrap"><table><thead><tr><th>Item</th><th>Area</th><th>Price</th><th></th></tr></thead><tbody>{visibleItems.map((item) => <tr key={item.id}><td>{item.name}</td><td>{item.preparation_area}</td><td>₹{item.selling_price}</td><td><button type="button" onClick={() => add(item)}>Add</button></td></tr>)}</tbody></table></div>
        </div>
        <div className="panel">
          <h3>Cart</h3>
          {items.filter((item) => cart[item.id]).map((item) => <div className="cart-line" key={item.id}><span>{item.name}</span><span><button type="button" onClick={() => change(item, -1)}>−</button> {cart[item.id]} <button type="button" onClick={() => change(item, 1)}>+</button></span></div>)}
          <label>Order notes<textarea value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={500} /></label>
          <p><strong>Displayed estimate: ₹{total.toFixed(2)}</strong></p>
          <p className="page-description">The server recalculates every price. This client total is only a preview.</p>
          <button type="button" disabled={saving} onClick={() => void submit()}>{saving ? "Placing…" : "Place order"}</button>
        </div>
      </div>
    </section>
  );
}
