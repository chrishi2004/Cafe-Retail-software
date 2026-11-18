import { useEffect, useRef, useState, type FormEvent } from "react";
import { businessDate } from "../../businessDates";
import { listRefunds, recordPaymentResolution, type RefundCase } from "../api/governance";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";
import { formatCurrency } from "../utils/format";

type Payment = RefundCase["payments"][number];
type Entry = { row: RefundCase; payment: Payment; action: "refund" | "not_received" };

export function RefundsPage() {
  const { token } = useAuth();
  const [history, setHistory] = useState(false);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [page, setPage] = useState<Awaited<ReturnType<typeof listRefunds>> | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [entry, setEntry] = useState<Entry | null>(null);
  const [saving, setSaving] = useState(false);
  const request = useRef({ payload: "", key: "", busy: false });

  useEffect(() => {
    if (!token) return;
    let active = true;
    setPage(null);
    listRefunds(token, history, offset).then((result) => {
      if (!active) return;
      if (!result.items.length && offset) setOffset(Math.max(0, offset - result.page_size));
      else setPage(result);
    }).catch((err: Error) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [token, history, offset, refresh]);

  const begin = (row: RefundCase, payment: Payment, action: Entry["action"]) => {
    setEntry({ row, payment, action });
    setError("");
    setNotice("");
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!entry || !token || request.current.busy) return;
    const form = new FormData(event.currentTarget);
    const { row, payment, action } = entry;
    const payload = action === "refund" ? {
      action,
      amount: String(form.get("amount")),
      refund_date: String(form.get("date")),
      reference_number: String(form.get("reference") ?? ""),
    } : { action, reason: String(form.get("reason")) };
    const hash = JSON.stringify([row.id, payment.id, payload]);
    if (request.current.payload !== hash) request.current = { payload: hash, key: crypto.randomUUID(), busy: false };
    request.current.busy = true;
    setSaving(true);
    setError("");
    try {
      await recordPaymentResolution(token, row.id, payment.id, payload, request.current.key);
      setNotice(action === "refund" ? "Refund recorded." : "Payment entry corrected.");
      request.current = { payload: "", key: "", busy: false };
      setEntry(null);
      setRefresh((current) => current + 1);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      request.current.busy = false;
      setSaving(false);
    }
  };

  return <section className="page-stack">
    <div className="page-header">
      <div><h2>Refunds</h2>
        <p>After deleting a paid bill, return the money first, then record it here. Use “No payment received” only for a mistaken payment entry.</p>
      </div>
    </div>
    <label className="checkbox-row">
      <input type="checkbox" checked={history} disabled={saving}
        onChange={(event) => { setHistory(event.target.checked); setOffset(0); setEntry(null); setError(""); }} />
      Include resolved payments
    </label>
    {notice && <p role="status">{notice}</p>}
    {error && <ErrorState message={error} />}
    {entry && <form className="panel page-stack" onSubmit={submit} key={`${entry.row.id}-${entry.payment.id}-${entry.action}`}>
      <h3>{entry.action === "refund" ? "Record a completed refund" : "Correct a mistaken payment"} · {entry.row.invoice_number}</h3>
      {entry.action === "refund" ? <>
        <p>Refund via {entry.payment.mode} before saving. This form does not send money. If the date is closed, reopen Daily Closing before recording it.</p>
        <div className="filter-bar">
          <label>Refund amount<input name="amount" type="number" min="0.01" step="0.01" max={entry.payment.remaining} defaultValue={entry.payment.remaining} required /></label>
          <label>Refund date (IST)<input name="date" type="date" min={entry.payment.received_date} max={businessDate()} defaultValue={businessDate()} required /></label>
          {!entry.payment.cash && <label>Refund reference<input name="reference" maxLength={100} required /></label>}
        </div>
      </> : <label>Why was no payment received?<input name="reason" minLength={3} maxLength={250} required /></label>}
      <div className="filter-actions">
        <button className="action-button" type="submit" disabled={saving}>
          {entry.action === "refund" ? "Confirm money returned" : "Confirm no money received"}
        </button>
        <button type="button" disabled={saving} onClick={() => setEntry(null)}>Back</button>
      </div>
    </form>}
    {!page && !error && <LoadingState label="Loading refunds" />}
    {page && !page.items.length && <p>No refunds to reconcile.</p>}
    {page?.items.map((row) => <article key={row.id} className="panel">
      <h3>{row.invoice_number}</h3>
      {row.legacy && <p>Older cancellation. Check your cash or transfer records before recording a refund.</p>}
      <div className="table-wrap"><table>
        <thead><tr><th>Payment</th><th>Received</th><th>To reconcile</th><th>Action</th></tr></thead>
        <tbody>{row.payments.map((payment) => <tr key={payment.id}>
          <td>{payment.mode} · {payment.received_date}</td>
          <td>{formatCurrency(payment.amount)}</td>
          <td>{formatCurrency(payment.remaining)}</td>
          <td>
            {payment.refunds.map((refund) => <p key={refund.id}>Returned {formatCurrency(refund.amount)} · {refund.date}{refund.reference ? ` · ${refund.reference}` : ""}</p>)}
            {payment.correction && <p>No payment received: {payment.correction}</p>}
            {Number(payment.remaining) > 0 && <>
              <button type="button" disabled={saving} onClick={() => begin(row, payment, "refund")}>Record refund</button>
              {!payment.refunds.length && <button type="button" disabled={saving} onClick={() => begin(row, payment, "not_received")}>No payment received</button>}
            </>}
          </td>
        </tr>)}</tbody>
      </table></div>
    </article>)}
    {page && (offset > 0 || page.has_more) && <div className="filter-actions">
      <button type="button" disabled={!offset || saving} onClick={() => { setEntry(null); setOffset(offset - page.page_size); }}>Previous</button>
      <button type="button" disabled={!page.has_more || saving} onClick={() => { setEntry(null); setOffset(offset + page.page_size); }}>Next</button>
    </div>}
  </section>;
}
