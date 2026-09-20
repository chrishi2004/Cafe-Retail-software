import { FormEvent, useState } from "react";

import { ApiError } from "../api/client";
import { createExpense } from "../api/expenses";
import { useAuth } from "../auth/AuthContext";
import { ErrorState } from "../components/ui";

export function ExpensesPage() {
  const { token } = useAuth();
  const [branchId, setBranchId] = useState(""); const [categoryId, setCategoryId] = useState(""); const [amount, setAmount] = useState(""); const [reason, setReason] = useState(""); const [message, setMessage] = useState<string | null>(null); const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) { event.preventDefault(); if (!token) return; setError(null); setMessage(null); try { const row = await createExpense(token, { branch_id: Number(branchId), category_id: Number(categoryId), expense_date: new Date().toISOString().slice(0, 10), amount, payment_mode: "cash", reason, idempotency_key: `ui-expense-${Date.now()}` }); setMessage(`Expense ${row.id} posted for ₹${row.amount}.`); } catch (requestError) { setError(requestError instanceof ApiError ? requestError.message : "Could not post the expense."); } }
  return <section className="page-shell"><div className="page-header"><div><p className="eyebrow">Phase 10 · Cashbook</p><h2>Expenses and accounting summaries</h2><p className="page-description">Post controlled branch expenses with category, payment mode and audit metadata. Use the API summary for reconciled cashbook totals.</p></div></div>{error ? <ErrorState message={error} title="Expense failed" /> : null}{message ? <div className="success-banner" role="status">{message}</div> : null}<form className="form-card" onSubmit={submit}><div className="form-grid"><label>Branch ID<input required min="1" type="number" value={branchId} onChange={(event) => setBranchId(event.target.value)} /></label><label>Category ID<input required min="1" type="number" value={categoryId} onChange={(event) => setCategoryId(event.target.value)} /></label><label>Amount<input required min="0.01" step="0.01" type="number" value={amount} onChange={(event) => setAmount(event.target.value)} /></label><label>Reason<input required minLength={3} value={reason} onChange={(event) => setReason(event.target.value)} /></label></div><button className="action-button primary" type="submit">Post expense</button></form></section>;
}
