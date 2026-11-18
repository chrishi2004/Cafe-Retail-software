import { createPortal } from "react-dom";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { closeClosing, createClosing, getClosing, reopenClosing, submitClosing, type Closing } from "../api/governance";
import { downloadClosingCsv } from "../api/exports";
import { listBranches } from "../api/masterData";
import { ApiError, apiRequest } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";
import type { Branch } from "../types";
import { cafeToday } from "../utils/cafeDates";
import { formatCurrency } from "../utils/format";

const caption = (value: string | null | undefined) => value == null ? "Not recorded" : formatCurrency(value);
const tender = [
  ["Cash", "cash"], ["UPI", "upi"], ["Card", "card"], ["Other electronic", "other_electronic"], ["Other non-cash", "other_non_cash"],
] as const;

function ClosingSummary({ row, counted }: { row: Closing; counted: string }) {
  const live = !!row.preview_token;
  const validCount = /^\d{1,9}(\.\d{1,2})?$/.test(counted);
  const physicalCount = live ? (validCount ? counted : null) : row.counted_cash;
  const difference = live && physicalCount !== null
    ? (Math.round(Number(physicalCount) * 100) - Math.round(Number(row.expected_cash) * 100)) / 100
    : row.variance == null ? null : Number(row.variance);
  const values = [
    ["Opening cash", row.opening_cash],
    ["Actual cash receipts", row.cash_collections],
    ["Actual cash refunds", row.cash_refunds],
    ["Cash operating expenses", row.breakdown?.cash_operating_expenses],
    ["Cash supplier payments", row.breakdown?.cash_supplier_payments],
    ["Total cash outflows", row.cash_expenses],
    ["Expected closing cash", row.expected_cash],
    ["Counted physical cash", physicalCount],
  ];
  return <article className="panel page-stack daily-closing-summary" aria-label="Daily Closing summary">
    <header>
      <h3>{live ? "Daily Closing preview" : "Daily Closing summary"}</h3>
      <p>{row.company_name} · {row.branch_name} · {row.business_date} (IST)</p>
      <p>Status: <strong>{row.status}</strong></p>
      {live && <p>This preview can change until you submit the count.</p>}
    </header>
    <div className="table-wrap"><table>
      <caption>Physical cash</caption>
      <tbody>
        {values.map(([label, amount]) => <tr key={label}><th scope="row">{label}</th><td>{caption(amount)}</td></tr>)}
        <tr><th scope="row">Cash shortage / excess</th><td>{
          difference === null ? "Pending count" : difference < 0 ? `Shortage ${formatCurrency(-difference)}` :
            difference > 0 ? `Excess ${formatCurrency(difference)}` : "Balanced"
        }</td></tr>
      </tbody>
    </table></div>
    {row.breakdown && <div className="table-wrap"><table>
      <caption>Payments by method</caption>
      <thead><tr><th scope="col">Method</th><th scope="col">Sales collections</th><th scope="col">Customer credit repayments</th><th scope="col">Actual refunds</th></tr></thead>
      <tbody>{tender.map(([label, key]) => <tr key={key}>
        <th scope="row">{label}</th><td>{caption(row.breakdown?.sales[key])}</td>
        <td>{caption(row.breakdown?.repayments[key])}</td><td>{caption(row.breakdown?.refunds[key])}</td>
      </tr>)}</tbody>
    </table></div>}
    {!row.breakdown && <p>This historical closing has saved totals but no detailed payment or cash-outflow breakdown.</p>}
    <div className="table-wrap"><table>
      <caption>Non-cash totals</caption>
      <tbody>
        <tr><th scope="row">Total non-cash receipts</th><td>{caption(row.non_cash_total)}</td></tr>
        <tr><th scope="row">Non-cash refunds</th><td>{caption(row.non_cash_refunds)}</td></tr>
        <tr><th scope="row">Non-cash expenses paid</th><td>{caption(row.non_cash_expenses)}</td></tr>
      </tbody>
    </table></div>
    <p>Opened by: {row.opened_by_name ?? "Not recorded"} · Submitted by: {row.submitted_by_name ?? "—"} · Closed by: {row.closed_by_name ?? "—"}</p>
    {row.reopened_by_name && <p>Last reopened by: {row.reopened_by_name} · {row.reopened_reason}</p>}
  </article>;
}

export function CafeClosingPage({ title = "Café cash reconciliation" }: { title?: string } = {}) {
  const { token, user } = useAuth();
  const [branches, setBranches] = useState<Branch[]>([]);
  const [branchId, setBranchId] = useState(0);
  const [day, setDay] = useState(cafeToday);
  const [closing, setClosing] = useState<Closing | null>(null);
  const [openingCash, setOpeningCash] = useState("0");
  const [counted, setCounted] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const lock = useRef(false);

  useEffect(() => {
    if (!token) return;
    let active = true;
    listBranches(token, { includeInactive: true }).then((rows) => {
      if (!active) return;
      setBranches(rows);
      setBranchId(rows.find((row) => row.is_active)?.id ?? rows[0]?.id ?? 0);
      if (!rows.length) setLoading(false);
    }).catch((err: Error) => { if (active) { setError(err.message); setLoading(false); } });
    return () => { active = false; };
  }, [token]);
  useEffect(() => {
    if (!token || !branchId || !day) return;
    let active = true;
    setLoading(true);
    setClosing(null);
    getClosing(token, branchId, day).then((row) => {
      if (active) setClosing(row);
    }).catch((err: Error) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token, branchId, day, revision]);

  const run = async (action: "open" | "submit" | "close" | "reopen" | "export", credentials?: FormData) => {
    if (!token || !branchId || lock.current) return;
    lock.current = true; setBusy(true); setError("");
    try {
      if (action === "export") { await downloadClosingCsv(token, branchId, day); return; }
      if (action === "open") await createClosing(token, { branch_id: branchId, business_date: day, opening_cash: openingCash });
      if (action === "submit" && closing?.preview_token)
        await submitClosing(token, closing.id, counted, closing.preview_token);
      if (action === "close" && closing) await closeClosing(token, closing.id);
      if (action === "reopen" && closing && credentials) {
        await apiRequest("/auth/step-up", { method: "POST", body: JSON.stringify({
          password: credentials.get("password"), totp_code: credentials.get("totp"),
        }) }, token);
        await reopenClosing(token, closing.id, String(credentials.get("reason")));
        setCounted("");
      }
      setRevision((n) => n + 1);
    } catch (err) {
      setError((err as Error).message);
      if (err instanceof ApiError && err.code === "closing_preview_changed") setRevision((n) => n + 1);
    } finally {
      lock.current = false; setBusy(false);
    }
  };

  const select = (id: number, date: string) => {
    if (id === branchId && date === day) return;
    setClosing(null); setBranchId(id); setDay(date); setError(""); setCounted(""); setOpeningCash("0");
  };
  const reopen = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    event.currentTarget.reset();
    void run("reopen", form);
  };
  const activeBranch = branches.some((branch) => branch.id === branchId && branch.is_active);
  const editable = closing && activeBranch && !!closing.preview_token;
  const saved = closing && ["submitted", "closed"].includes(closing.status);
  return <section className="page-stack daily-closing-page">
    <div className="page-header"><div><p className="eyebrow">Daily Closing</p><h2>{title}</h2></div>
      {closing && <div className="filter-actions">
        <button type="button" onClick={() => window.print()} disabled={busy || loading}>Print summary</button>
        <button type="button" onClick={() => void run("export")} disabled={busy || loading}>Download CSV</button>
      </div>}
    </div>
    <div className="filter-bar">
      <label>Branch<select aria-label="Branch" disabled={busy} value={branchId} onChange={(e) => select(Number(e.target.value), day)}>
        {branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}{branch.is_active ? "" : " (Inactive)"}</option>)}
      </select></label>
      <label>Business date (IST)<input type="date" value={day} max={cafeToday()} disabled={busy} onChange={(e) => {
        if (e.target.value) select(branchId, e.target.value);
      }} /></label>
      <button type="button" disabled={busy || loading || !branchId} onClick={() => { setError(""); setRevision((n) => n + 1); }}>Refresh preview</button>
    </div>
    {error && <ErrorState message={error} />}
    {loading ? <LoadingState label="Loading business day" /> : !branchId ? <p>No authorized branches are available.</p> :
      !closing ? (day === cafeToday() && activeBranch && !error ? <form className="panel page-stack" onSubmit={(e) => { e.preventDefault(); void run("open"); }}>
        <h3>Open today</h3>
        <label>Opening cash<input type="number" required min="0" max="999999999.99" step="0.01" value={openingCash} onChange={(e) => setOpeningCash(e.target.value)} /></label>
        <button type="submit" disabled={busy}>Open business day</button>
      </form> : !error && <p>No closing was recorded for this branch on {day}.</p>) :
        <ClosingSummary row={closing} counted={counted} />}
    {!loading && closing && createPortal(
      <div className="daily-closing-print">
        <style>{"@page { size: A4 portrait; margin: 12mm; }"}</style>
        <ClosingSummary row={closing} counted={counted} />
      </div>,
      document.body,
    )}
    {!loading && editable && <form className="panel page-stack" onSubmit={(e) => { e.preventDefault(); void run("submit"); }}>
      <label>Counted physical cash<input type="number" required min="0" max="999999999.99" step="0.01" value={counted} onChange={(e) => setCounted(e.target.value)} /></label>
      <p>Submitting saves the count and locks payments and expenses for this branch and day.</p>
      <button type="submit" disabled={busy}>Submit count</button>
    </form>}
    {!loading && activeBranch && closing?.status === "submitted" && <button type="button" disabled={busy} onClick={() => void run("close")}>Close day</button>}
    {!loading && saved && activeBranch && ["admin", "super_admin"].includes(user?.server_role ?? "") &&
      <form className="panel page-stack" onSubmit={reopen}>
        <h3>Reopen for a correction</h3>
        <label>Correction reason<input name="reason" required minLength={3} maxLength={500} /></label>
        <label>Confirm password<input name="password" required type="password" autoComplete="current-password" /></label>
        <label>Authenticator code<input name="totp" required inputMode="numeric" pattern="[0-9]{6}" autoComplete="one-time-code" /></label>
        <button type="submit" disabled={busy}>Reopen day</button>
      </form>}
  </section>;
}
