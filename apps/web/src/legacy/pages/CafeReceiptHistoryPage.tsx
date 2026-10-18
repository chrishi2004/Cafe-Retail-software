import { useEffect, useRef, useState, type FormEvent } from "react";

import { getCafeReceipt, listCafeInvoiceHistory, type CafeInvoiceHistory, type CafeReceipt } from "../api/cafeBilling";
import { listBranches } from "../api/masterData";
import { useAuth } from "../auth/AuthContext";
import { CafeReceiptView, receiptTime } from "../components/CafeReceipt";
import { ErrorState, LoadingState } from "../components/ui";
import type { Branch } from "../types";

type Filters = { search: string; branchId?: number; startDate: string; endDate: string };
const EMPTY_FILTERS: Filters = { search: "", startDate: "", endDate: "" };

export function CafeReceiptHistoryPage() {
  const { token } = useAuth();
  const [branches, setBranches] = useState<Branch[]>([]);
  const [draft, setDraft] = useState<Filters>(EMPTY_FILTERS);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [offset, setOffset] = useState(0);
  const [history, setHistory] = useState<CafeInvoiceHistory | null>(null);
  const [receipt, setReceipt] = useState<CafeReceipt | null>(null);
  const [loading, setLoading] = useState(true);
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);
  const limit = 50;

  useEffect(() => {
    if (!token) return;
    let active = true;
    listBranches(token).then((rows) => { if (active) setBranches(rows); }).catch((err: Error) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [token]);
  useEffect(() => {
    if (!token) return;
    let active = true;
    setLoading(true); setError(null); setHistory(null);
    listCafeInvoiceHistory(token, { ...filters, offset, limit }).then((rows) => { if (active) setHistory(rows); })
      .catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token, filters, offset]);
  useEffect(() => () => { requestId.current += 1; }, []);

  const apply = (event: FormEvent) => {
    event.preventDefault();
    if (draft.startDate && draft.endDate && draft.startDate > draft.endDate) { setError("Select a valid date range."); return; }
    requestId.current += 1; setOpening(false); setReceipt(null);
    setOffset(0); setFilters({ ...draft, search: draft.search.trim() });
  };
  const open = async (invoiceId: number) => {
    if (!token) return;
    const id = ++requestId.current;
    setReceipt(null); setOpening(true); setError(null);
    try {
      const existing = await getCafeReceipt(token, invoiceId);
      if (id === requestId.current) setReceipt(existing);
    } catch (err) { if (id === requestId.current) setError((err as Error).message); }
    finally { if (id === requestId.current) setOpening(false); }
  };

  return <section className="page-stack">
    <div className="page-header"><div><p className="eyebrow">Café invoices</p><h2>Receipt history</h2><p>Find an existing invoice and reprint its receipt.</p></div></div>
    <form className="filter-bar" onSubmit={apply}>
      <label>Invoice number <input value={draft.search} maxLength={100} onChange={(e) => setDraft({ ...draft, search: e.target.value })} /></label>
      <label>Branch <select value={draft.branchId ?? ""} onChange={(e) => setDraft({ ...draft, branchId: Number(e.target.value) || undefined })}><option value="">All authorized branches</option>{branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}</select></label>
      <label>From <input type="date" value={draft.startDate} onChange={(e) => setDraft({ ...draft, startDate: e.target.value })} /></label>
      <label>To <input type="date" value={draft.endDate} onChange={(e) => setDraft({ ...draft, endDate: e.target.value })} /></label>
      <button type="submit" className="action-button secondary">Find receipts</button>
    </form>
    {error ? <ErrorState message={error} /> : null}
    {loading ? <LoadingState label="Loading receipt history" /> : history ? <article className="panel">
      {!history.items.length ? <p>No matching Café invoices.</p> : <div className="table-wrap"><table><thead><tr><th>Invoice</th><th>Date / time (IST)</th><th>Branch</th><th>Status</th><th>Total</th><th>Paid</th><th>Balance</th><th></th></tr></thead><tbody>{history.items.map((invoice) => <tr key={invoice.invoice_id}>
        <td>{invoice.invoice_number}</td><td>{receiptTime(invoice.issued_at)}</td><td>{invoice.branch_name}</td><td>{invoice.invoice_status.replace(/_/g, " ")}</td><td>₹{invoice.grand_total}</td><td>₹{invoice.paid_amount}</td><td>₹{invoice.balance_due}</td>
        <td><button type="button" disabled={opening} aria-label={`View / reprint ${invoice.invoice_number}`} onClick={() => void open(invoice.invoice_id)}>View / reprint</button></td>
      </tr>)}</tbody></table></div>}
      <div className="filter-actions"><span>{history.total ? `${offset + 1}–${Math.min(offset + limit, history.total)}` : "0"} of {history.total}</span>
        <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>Previous</button>
        <button type="button" disabled={offset + limit >= history.total} onClick={() => setOffset(offset + limit)}>Next</button>
      </div>
    </article> : null}
    {opening ? <LoadingState label="Loading existing receipt" /> : null}
    {receipt ? <CafeReceiptView receipt={receipt} reprint><button type="button" onClick={() => setReceipt(null)}>Close receipt</button></CafeReceiptView> : null}
  </section>;
}
