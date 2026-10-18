import { useEffect, useRef, useState } from "react";

import { listPaymentModes } from "../api/businessSettings";
import { listMenuItems, type MenuItem } from "../api/cafe";
import { type CafeBillResult, type CafeReceipt } from "../api/cafeBilling";
import { activeVentureStorage, apiRequest, ApiError } from "../api/client";
import { listBranches } from "../api/masterData";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";
import type { Branch, PaymentMode } from "../types";

type Checkout = {
  branch_id: number; order_type: "counter" | "takeaway";
  items: Array<{ menu_item_public_id: string; quantity: number }>;
  payment_mode_id: number; reference_number?: string;
};
type Pending = { key: string; payload: Checkout };
const money = (value: string | number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(Number(value));

export function CafePOSPage() {
  const { token, user } = useAuth();
  const storageKey = `cafe-pos-v1:${user?.id}:${user?.company_id ?? activeVentureStorage.get()}`;
  const [pending, setPending] = useState<Pending | null>(() => {
    try { return JSON.parse(sessionStorage.getItem(storageKey) ?? "null") as Pending | null; }
    catch { return null; }
  });
  const [items, setItems] = useState<MenuItem[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [modes, setModes] = useState<PaymentMode[]>([]);
  const [branchId, setBranchId] = useState(0);
  const [modeId, setModeId] = useState(0);
  const [cart, setCart] = useState<Record<number, number>>({});
  const [orderType, setOrderType] = useState<"counter" | "takeaway">("counter");
  const [search, setSearch] = useState("");
  const [reference, setReference] = useState("");
  const [receipt, setReceipt] = useState<CafeReceipt | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const busy = useRef(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let active = true;
    Promise.all([listMenuItems(token), listBranches(token), listPaymentModes(token)]).then(([menu, bs, ps]) => {
      if (!active) return;
      setItems(menu.filter((row) => row.available && row.is_active));
      setBranches(bs);
      setBranchId(bs[0]?.id ?? 0);
      const usable = ps.filter((mode) => mode.is_active && ["cash", "upi", "card"].includes(mode.mode_type));
      setModes(usable);
      setModeId(usable[0]?.id ?? 0);
    }).catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token]);

  const menu = items.filter((item) => item.branch_id === null || item.branch_id === branchId);
  const selected = menu.filter((item) => cart[item.id]);
  const mode = modes.find((row) => row.id === modeId);
  const change = (id: number, delta: number) => setCart((current) => ({ ...current, [id]: Math.max(0, Math.min(20, (current[id] ?? 0) + delta)) }));
  const total = selected.reduce((sum, item) => sum + Number(item.selling_price) * cart[item.id], 0);

  const submit = async () => {
    if (!token || busy.current) return;
    if (!pending && (!selected.length || !branchId || !mode)) return;
    if (!pending && mode?.requires_reference && !reference.trim()) { setError("Enter the payment reference."); return; }
    const attempt = pending ?? {
      key: Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) => byte.toString(16).padStart(2, "0")).join(""),
      payload: { branch_id: branchId, order_type: orderType,
        items: selected.map((item) => ({ menu_item_public_id: item.public_id, quantity: cart[item.id] })),
        payment_mode_id: modeId, reference_number: reference.trim() || undefined },
    };
    // Persist before sending: a lost response or reload retries the same sale.
    try { sessionStorage.setItem(storageKey, JSON.stringify(attempt)); }
    catch { setError("Checkout recovery storage is unavailable. Enable browser session storage before billing."); return; }
    setPending(attempt);
    busy.current = true; setSaving(true); setError(null);
    try {
      const result = await apiRequest<CafeBillResult>("/cafe/billing/pos/checkout", {
        method: "POST", headers: { "Idempotency-Key": attempt.key }, body: JSON.stringify(attempt.payload),
      }, token);
      setReceipt(result.receipt);
      sessionStorage.removeItem(storageKey); setPending(null);
      setCart({}); setReference(""); setSearch("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Checkout failed. Retry this sale.");
      if (err instanceof ApiError && [400, 403, 404, 409, 422].includes(err.status)) {
        sessionStorage.removeItem(storageKey); setPending(null);
      }
    } finally { busy.current = false; setSaving(false); }
  };

  if (loading) return <LoadingState label="Loading Café POS" />;
  return <section className="page-stack">
    <div className="page-header"><div><p className="eyebrow">Café counter</p><h2>Bill a customer</h2></div></div>
    {error ? <ErrorState message={error} /> : null}
    {receipt ? <article className="panel" aria-live="polite">
      <h3>Paid · {receipt.invoice_number}</h3><p>{receipt.cafe_name} · {receipt.branch_name}</p>
      {receipt.items.map((item, index) => <p key={index}>{item.name} × {item.quantity} · {money(item.line_total)}</p>)}
      <p><strong>Total {money(receipt.grand_total)}</strong> · Paid {money(receipt.paid_amount)} · Due {money(receipt.balance_due)}</p>
      {receipt.payments.map((payment, index) => <p key={index}>{payment.mode_name}: {money(payment.amount)}</p>)}
      <button type="button" onClick={() => setReceipt(null)}>Next customer</button>
    </article> : null}
    {pending ? <article className="panel"><h3>Sale awaiting confirmation</h3><p>Branch: {branches.find((branch) => branch.id === pending.payload.branch_id)?.name ?? pending.payload.branch_id} · {pending.payload.order_type}. Retry to retrieve the invoice safely.</p><button type="button" disabled={saving} onClick={() => void submit()}>{saving ? "Confirming…" : "Retry same sale"}</button></article> : null}
    <fieldset disabled={saving || !!pending || !!receipt} className="page-stack cafe-pos-fields">
      <div className="filter-bar">
        <label>Branch <select value={branchId} onChange={(e) => { setBranchId(Number(e.target.value)); setCart({}); }}>{branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}</select></label>
        <label>Order <select value={orderType} onChange={(e) => setOrderType(e.target.value as "counter" | "takeaway")}><option value="counter">Counter</option><option value="takeaway">Takeaway</option></select></label>
        <label>Search menu <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Item name" /></label>
      </div>
      <div className="content-grid">
        <article className="panel"><h3>Menu</h3><div className="cafe-pos-menu">{menu.filter((item) => item.name.toLowerCase().includes(search.toLowerCase())).map((item) => <button type="button" key={item.id} onClick={() => change(item.id, 1)}>{item.name}<br />{money(item.selling_price)}</button>)}</div>{!menu.length ? <p>No available menu items for this branch.</p> : null}</article>
        <article className="panel"><h3>Current bill</h3>
          {!selected.length ? <p>Select menu items to start.</p> : selected.map((item) => <div className="cart-line" key={item.id}><span>{item.name} · {money(Number(item.selling_price) * cart[item.id])}</span><span><button type="button" aria-label={`Remove one ${item.name}`} onClick={() => change(item.id, -1)}>−</button> {cart[item.id]} <button type="button" aria-label={`Add one ${item.name}`} onClick={() => change(item.id, 1)}>+</button></span></div>)}
          <p><strong>Total estimate: {money(total)}</strong></p>
          <label>Payment <select value={modeId} onChange={(e) => setModeId(Number(e.target.value))}>{modes.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
          {mode?.requires_reference ? <label>Payment reference <input value={reference} onChange={(e) => setReference(e.target.value)} maxLength={100} /></label> : null}
          {!modes.length ? <p>Owner must configure Cash, UPI or Card before billing.</p> : null}
          <button className="action-button primary" type="button" disabled={!selected.length || !mode || !branchId || selected.length > 25} onClick={() => void submit()}>{saving ? "Billing…" : "Pay & create invoice"}</button>
          {selected.length > 25 ? <p>A bill supports up to 25 different items.</p> : null}
        </article>
      </div>
    </fieldset>
  </section>;
}
