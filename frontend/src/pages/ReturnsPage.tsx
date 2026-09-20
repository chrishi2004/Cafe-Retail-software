import { FormEvent, useState } from "react";

import { ApiError } from "../api/client";
import { createSalesReturn } from "../api/returns";
import { useAuth } from "../auth/AuthContext";
import { ErrorState } from "../components/ui";

export function ReturnsPage() {
  const { token } = useAuth();
  const [invoiceId, setInvoiceId] = useState("");
  const [invoiceItemId, setInvoiceItemId] = useState("");
  const [quantity, setQuantity] = useState("1.00");
  const [reason, setReason] = useState("");
  const [refundMode, setRefundMode] = useState("customer_credit");
  const [condition, setCondition] = useState("saleable");
  const [restock, setRestock] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setError(null);
    setMessage(null);
    try {
      const result = await createSalesReturn(token, Number(invoiceId), {
        reason,
        refund_mode: refundMode as "customer_credit" | "cash" | "original_payment",
        idempotency_key: `ui-return-${invoiceId}-${invoiceItemId}-${Date.now()}`,
        items: [{ invoice_item_id: Number(invoiceItemId), quantity, condition: condition as "saleable" | "damaged", restock }],
      });
      setMessage(`Return ${result.return_number} issued with credit note ${result.credit_note.credit_note_number} for ₹${result.total_amount}.`);
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : "Could not issue the return.");
    }
  }

  return (
    <section className="page-shell">
      <div className="page-header"><div><p className="eyebrow">Phase 8 · Returns</p><h2>Sales returns and credit notes</h2><p className="page-description">Return exact invoice quantities, restore saleable stock, and issue a traceable credit note.</p></div></div>
      {error ? <ErrorState message={error} title="Return failed" /> : null}
      {message ? <div className="success-banner" role="status">{message}</div> : null}
      <form className="form-card" onSubmit={submit}>
        <div className="form-grid">
          <label>Invoice ID<input required min="1" type="number" value={invoiceId} onChange={(event) => setInvoiceId(event.target.value)} /></label>
          <label>Invoice item ID<input required min="1" type="number" value={invoiceItemId} onChange={(event) => setInvoiceItemId(event.target.value)} /></label>
          <label>Quantity<input required min="0.01" step="0.01" type="number" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></label>
          <label>Refund mode<select value={refundMode} onChange={(event) => setRefundMode(event.target.value)}><option value="customer_credit">Customer credit</option><option value="cash">Cash refund</option><option value="original_payment">Original payment</option></select></label>
          <label>Condition<select value={condition} onChange={(event) => setCondition(event.target.value)}><option value="saleable">Saleable</option><option value="damaged">Damaged</option></select></label>
          <label>Reason<input required minLength={3} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        </div>
        <label className="checkbox-row"><input checked={restock} type="checkbox" onChange={(event) => setRestock(event.target.checked)} /> Restore saleable quantity to inventory</label>
        <button className="action-button primary" type="submit">Issue return and credit note</button>
      </form>
    </section>
  );
}
