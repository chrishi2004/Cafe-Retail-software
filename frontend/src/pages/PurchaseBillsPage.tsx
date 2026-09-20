import { FormEvent, useState } from "react";

import { ApiError } from "../api/client";
import { createPurchaseBill } from "../api/purchaseAccounting";
import { useAuth } from "../auth/AuthContext";
import { ErrorState } from "../components/ui";

export function PurchaseBillsPage() {
  const { token } = useAuth();
  const [branchId, setBranchId] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("1.00");
  const [unitCost, setUnitCost] = useState("0.00");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setError(null); setMessage(null);
    try {
      const bill = await createPurchaseBill(token, { branch_id: Number(branchId), supplier_id: Number(supplierId), bill_date: new Date().toISOString().slice(0, 10), idempotency_key: `ui-purchase-${Date.now()}`, items: [{ product_id: Number(productId), quantity, unit_cost: unitCost }] });
      setMessage(`Purchase bill ${bill.bill_number} posted for ₹${bill.total_amount}; payable balance ₹${bill.balance_due}.`);
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : "Could not post the purchase bill.");
    }
  }

  return <section className="page-shell"><div className="page-header"><div><p className="eyebrow">Phase 9 · Purchase accounting</p><h2>Purchase bills and supplier payables</h2><p className="page-description">Post supplier bills separately from stock receiving, then track payments and debit notes against the payable balance.</p></div></div>{error ? <ErrorState message={error} title="Purchase bill failed" /> : null}{message ? <div className="success-banner" role="status">{message}</div> : null}<form className="form-card" onSubmit={submit}><div className="form-grid"><label>Branch ID<input required min="1" type="number" value={branchId} onChange={(event) => setBranchId(event.target.value)} /></label><label>Supplier ID<input required min="1" type="number" value={supplierId} onChange={(event) => setSupplierId(event.target.value)} /></label><label>Product ID<input required min="1" type="number" value={productId} onChange={(event) => setProductId(event.target.value)} /></label><label>Quantity<input required min="0.01" step="0.01" type="number" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></label><label>Unit cost<input required min="0" step="0.01" type="number" value={unitCost} onChange={(event) => setUnitCost(event.target.value)} /></label></div><button className="action-button primary" type="submit">Post purchase bill</button></form></section>;
}
