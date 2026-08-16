import { useCallback, useEffect, useMemo, useState } from "react";

import {
  billCafeOrder,
  billCafeTableSession,
  quoteCafeOrder,
  quoteCafeTableSession,
  type CafeBillPaymentInput,
  type CafeBillQuote,
  type CafeBillResult,
} from "../api/cafeBilling";
import { listPaymentModes } from "../api/businessSettings";
import { listCafeOrders, type CafeOrder } from "../api/cafeOrders";
import { ApiError } from "../api/client";
import { listCustomers } from "../api/customers";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";
import type { Customer } from "../types";

type PaymentMode = Awaited<ReturnType<typeof listPaymentModes>>[number];
type BillingSource = {
  kind: "cafe_table_session" | "cafe_takeaway";
  id: string;
  label: string;
  status: string;
};

const BILLABLE = new Set(["accepted", "served", "bill_requested"]);

function messageFrom(error: unknown): string {
  return error instanceof ApiError ? error.message : "Cafe billing request failed.";
}

function newCheckoutKey(): string {
  return `cafe-bill-${crypto.randomUUID()}`;
}

function sourcesFromOrders(orders: CafeOrder[]): BillingSource[] {
  const seen = new Map<string, BillingSource>();
  for (const order of orders) {
    if (!BILLABLE.has(order.status)) continue;
    if (order.table_session_public_id) {
      const id = order.table_session_public_id;
      if (!seen.has(`table:${id}`)) {
        seen.set(`table:${id}`, {
          kind: "cafe_table_session",
          id,
          label: `${order.table_code ?? "Table"} · ${order.order_number}`,
          status: order.status,
        });
      }
    } else {
      seen.set(`order:${order.public_id}`, {
        kind: "cafe_takeaway",
        id: order.public_id,
        label: `${order.order_type} · ${order.order_number}`,
        status: order.status,
      });
    }
  }
  return [...seen.values()];
}

export function CafeBillingPage() {
  const { token } = useAuth();
  const [orders, setOrders] = useState<CafeOrder[]>([]);
  const [modes, setModes] = useState<PaymentMode[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedSource, setSelectedSource] = useState<string>("");
  const [quote, setQuote] = useState<CafeBillQuote | null>(null);
  const [payments, setPayments] = useState<CafeBillPaymentInput[]>([]);
  const [customerId, setCustomerId] = useState<number | null>(null);
  const [checkoutKey, setCheckoutKey] = useState(newCheckoutKey);
  const [result, setResult] = useState<CafeBillResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sources = useMemo(() => sourcesFromOrders(orders), [orders]);
  const source = useMemo(
    () => sources.find((row) => `${row.kind}:${row.id}` === selectedSource) ?? null,
    [selectedSource, sources],
  );

  const loadWorkspace = useCallback(async () => {
    if (!token) return;
    try {
      const [orderRows, paymentRows, customerRows] = await Promise.all([
        listCafeOrders(token, { unbilledOnly: true }),
        listPaymentModes(token),
        listCustomers(token, { includeInactive: false, limit: 100 }),
      ]);
      setOrders(orderRows);
      setModes(paymentRows.filter((row) => row.is_active));
      setCustomers(customerRows.filter((row) => row.is_active));
      setError(null);
    } catch (loadError) {
      setError(messageFrom(loadError));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  const refreshQuote = useCallback(async () => {
    if (!token || !source) return;
    try {
      const next = source.kind === "cafe_table_session"
        ? await quoteCafeTableSession(token, source.id)
        : await quoteCafeOrder(token, source.id);
      setQuote(next);
      setResult(null);
      setError(null);
      const firstMode = modes[0];
      setPayments(firstMode ? [{ payment_mode_id: firstMode.id, amount: next.grand_total }] : []);
    } catch (quoteError) {
      setQuote(null);
      setError(messageFrom(quoteError));
    }
  }, [modes, source, token]);

  useEffect(() => {
    setQuote(null);
    setResult(null);
    setCustomerId(null);
    setCheckoutKey(newCheckoutKey());
    if (source) void refreshQuote();
  }, [selectedSource]); // source refresh intentionally follows source selection only

  const updatePayment = (index: number, field: keyof CafeBillPaymentInput, value: string | number | null) => {
    setPayments((current) => current.map((row, rowIndex) => (
      rowIndex === index ? { ...row, [field]: value } : row
    )));
  };

  const addSplit = () => {
    const firstMode = modes[0];
    setPayments((current) => [
      ...current,
      { payment_mode_id: firstMode?.id ?? null, amount: "0.00" },
    ]);
  };

  const checkout = async () => {
    if (!token || !source || !quote || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const fresh = source.kind === "cafe_table_session"
        ? await quoteCafeTableSession(token, source.id)
        : await quoteCafeOrder(token, source.id);
      setQuote(fresh);
      const payload = {
        expected_version: fresh.source_version,
        customer_id: customerId,
        payments,
      };
      const completed = source.kind === "cafe_table_session"
        ? await billCafeTableSession(token, source.id, payload, checkoutKey)
        : await billCafeOrder(token, source.id, payload, checkoutKey);
      setResult(completed);
      await loadWorkspace();
    } catch (checkoutError) {
      setError(messageFrom(checkoutError));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingState label="Loading Cafe billing" />;

  return (
    <section className="page-stack">
      <div className="page-header">
        <div>
          <p className="eyebrow">P8 financial workflow</p>
          <h2>Billing & Payments</h2>
          <p className="page-description">
            Select a served table or takeaway order. Totals are refreshed from the backend immediately before checkout.
          </p>
        </div>
        <button type="button" className="secondary-button" onClick={() => void loadWorkspace()}>Refresh sources</button>
      </div>

      {error ? <ErrorState message={error} /> : null}

      <article className="panel wide">
        <div className="form-grid">
          <label>
            Billing source
            <select value={selectedSource} onChange={(event) => setSelectedSource(event.target.value)}>
              <option value="">Select table / takeaway</option>
              {sources.map((row) => (
                <option key={`${row.kind}:${row.id}`} value={`${row.kind}:${row.id}`}>
                  {row.label} · {row.status}
                </option>
              ))}
            </select>
          </label>
          <label>
            Customer / credit account
            <select value={customerId ?? ""} onChange={(event) => setCustomerId(event.target.value ? Number(event.target.value) : null)}>
              <option value="">Walk-in / anonymous</option>
              {customers.map((customer) => (
                <option key={customer.id} value={customer.id}>{customer.name}</option>
              ))}
            </select>
          </label>
        </div>
      </article>

      {quote ? (
        <>
          <article className="panel wide">
            <div className="panel-header">
              <div><p className="eyebrow">Backend quote</p><h3>Eligible unbilled items</h3></div>
              <button type="button" className="secondary-button" onClick={() => void refreshQuote()}>Refresh quote</button>
            </div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Order</th><th>Item</th><th>Source</th><th>Qty</th><th>Unit price</th><th>Discount</th><th>Total</th></tr></thead>
                <tbody>
                  {quote.eligible_items.map((item) => (
                    <tr key={item.order_item_id}>
                      <td>{item.order_number}</td><td>{item.menu_item_name}</td><td>{item.source_channel}</td>
                      <td>{item.quantity}</td><td>₹{item.unit_price}</td><td>₹{item.discount}</td><td>₹{item.line_total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {quote.excluded_items.length ? (
              <p className="page-description">Excluded: {quote.excluded_items.map((item) => `${item.menu_item_name} (${item.excluded_reason})`).join(", ")}</p>
            ) : null}
            <div className="metric-row">
              <strong>Subtotal ₹{quote.subtotal}</strong>
              <strong>Discount ₹{quote.discount_total}</strong>
              <strong>GST ₹0.00</strong>
              <strong>Grand total ₹{quote.grand_total}</strong>
            </div>
          </article>

          <article className="panel wide">
            <div className="panel-header"><div><p className="eyebrow">Settlement</p><h3>Payment split</h3></div><button type="button" onClick={addSplit}>Add split</button></div>
            {payments.map((payment, index) => {
              const selectedMode = modes.find((mode) => mode.id === payment.payment_mode_id);
              return (
                <div className="form-grid" key={`${index}-${payment.payment_mode_id ?? "none"}`}>
                  <label>Mode<select value={payment.payment_mode_id ?? ""} onChange={(event) => updatePayment(index, "payment_mode_id", event.target.value ? Number(event.target.value) : null)}><option value="">Select</option>{modes.map((mode) => <option key={mode.id} value={mode.id}>{mode.name}</option>)}</select></label>
                  <label>Amount<input value={payment.amount} onChange={(event) => updatePayment(index, "amount", event.target.value)} inputMode="decimal" /></label>
                  <label>Reference<input value={payment.reference_number ?? ""} required={selectedMode?.requires_reference} onChange={(event) => updatePayment(index, "reference_number", event.target.value)} /></label>
                  <button type="button" className="danger-button" disabled={payments.length === 1} onClick={() => setPayments((current) => current.filter((_, rowIndex) => rowIndex !== index))}>Remove</button>
                </div>
              );
            })}
            <button type="button" disabled={submitting || !payments.length || !quote.eligible_items.length} onClick={() => void checkout()}>
              {submitting ? "Issuing bill…" : "Issue bill and settle"}
            </button>
            <p className="page-description">Checkout key stays stable through retries until this source changes: {checkoutKey.slice(0, 18)}…</p>
          </article>
        </>
      ) : null}

      {result ? (
        <article className="panel wide" id="cafe-receipt">
          <div className="panel-header">
            <div><p className="eyebrow">Invoice issued</p><h3>{result.receipt.invoice_number}</h3></div>
            <button type="button" className="secondary-button" onClick={() => window.print()}>Print receipt</button>
          </div>
          <p>{result.receipt.cafe_name} · {result.receipt.branch_name}</p>
          <p>Non-GST invoice · GSTIN not displayed</p>
          <div className="table-wrap"><table><thead><tr><th>Item</th><th>Qty</th><th>Price</th><th>Total</th></tr></thead><tbody>{result.receipt.items.map((item, index) => <tr key={`${item.sku}-${index}`}><td>{item.name}</td><td>{item.quantity}</td><td>₹{item.unit_price}</td><td>₹{item.line_total}</td></tr>)}</tbody></table></div>
          <div className="metric-row"><strong>Total ₹{result.receipt.grand_total}</strong><strong>Paid ₹{result.receipt.paid_amount}</strong><strong>Balance ₹{result.receipt.balance_due}</strong><strong>{result.closed ? "Source closed" : "Awaiting settlement"}</strong></div>
          {result.idempotent_replay ? <p className="page-description">Safe retry: original invoice returned, no duplicate effects created.</p> : null}
        </article>
      ) : null}
    </section>
  );
}
