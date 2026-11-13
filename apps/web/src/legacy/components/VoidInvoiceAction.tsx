import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, apiRequest } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { cafeToday } from "../utils/cafeDates";

type Invoice = {
  id: number;
  number: string;
  status: string;
  type: string;
  source?: string;
  issuedAt: string | null;
  invoiceDate?: string;
  paid: string;
};

export function VoidInvoiceAction({ invoice, onVoided }: { invoice: Invoice; onVoided: () => void }) {
  const { token, user } = useAuth();
  const [open, setOpen] = useState(false);
  const [checking, setChecking] = useState(false);
  const [verifiedUntil, setVerifiedUntil] = useState(0);
  const [reason, setReason] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [payment, setPayment] = useState("");
  const [stock, setStock] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);
  const key = useRef("");
  useEffect(() => {
    if (!verifiedUntil) return;
    const timer = window.setTimeout(() => setVerifiedUntil(0), Math.max(0, verifiedUntil - Date.now()));
    return () => window.clearTimeout(timer);
  }, [verifiedUntil]);
  if (!token || !user || !["admin", "super_admin"].includes(user.server_role)) return null;
  if (!["paid", "partial_paid", "credit", "unpaid", "issued"].includes(invoice.status)) return null;
  const day = (value: string) => new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit",
  }).format(new Date(value));
  if (invoice.type !== "non_gst" || invoice.source === "cafe_table_session" ||
      !invoice.issuedAt || day(invoice.issuedAt) !== cafeToday() ||
      (invoice.invoiceDate && day(invoice.invoiceDate) !== cafeToday())) {
    return <p className="page-description">Only today’s non-GST counter or retail bills can be voided here.</p>;
  }

  const paid = Number(invoice.paid) > 0;
  const needsVerification = verifiedUntil === 0;

  const openForm = async () => {
    setChecking(true);
    setVerifiedUntil(0);
    try {
      const status = await apiRequest<{ remaining_ms: number }>("/governance/step-up", {}, token);
      if (status.remaining_ms > 0) setVerifiedUntil(Date.now() + status.remaining_ms);
    } catch {
      // A failed status check falls back to asking for credentials.
    } finally {
      setChecking(false);
      setOpen(true);
    }
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy.current || !reason.trim() || !stock || (paid && !payment)) return;
    busy.current = true;
    setPending(true);
    setError(null);
    try {
      if (needsVerification) {
        const verified = await apiRequest<{ remaining_ms: number }>("/governance/step-up", {
          method: "POST",
          body: JSON.stringify({ password, totp_code: code }),
        }, token);
        setVerifiedUntil(Date.now() + verified.remaining_ms);
      }
      key.current ||= crypto.randomUUID();
      await apiRequest(`/governance/voids/invoices/${invoice.id}`, {
        method: "POST",
        headers: { "Idempotency-Key": key.current },
        body: JSON.stringify({
          reason: reason.trim(),
          restock: stock === "restore",
          ...(paid ? { payment_resolution: payment } : {}),
        }),
      }, token);
      setOpen(false);
      onVoided();
    } catch (err) {
      if (err instanceof ApiError && err.code === "step_up_required")
        setVerifiedUntil(0);
      setError((err as Error).message);
    } finally {
      setPassword("");
      setCode("");
      busy.current = false;
      setPending(false);
    }
  };

  if (!open) return <button type="button" className="action-button secondary" disabled={checking} onClick={() => void openForm()}>{checking ? "Checking…" : "Void invoice"}</button>;

  return <form className="detail-stack" onSubmit={(event) => void submit(event)}>
    <h4>Void {invoice.number}</h4>
    <p>The original bill stays in history as cancelled. The POS will correct recorded totals. It cannot send money back to the customer.</p>
    {error && <p role="alert">{error}</p>}
    <fieldset disabled={pending}>
      <label>Reason <input required minLength={3} maxLength={300} value={reason} onChange={(e) => { setReason(e.target.value); key.current = ""; }} /></label>
      {paid && <label>Recorded payment (₹{invoice.paid})
        <select required value={payment} onChange={(e) => { setPayment(e.target.value); key.current = ""; }}>
          <option value="">Choose payment outcome</option>
          <option value="not_received">No money was received</option>
          <option value="returned">All money was already returned outside the POS</option>
        </select>
      </label>}
      <label>Stock
        <select required value={stock} onChange={(e) => { setStock(e.target.value); key.current = ""; }}>
          <option value="">Choose stock action</option>
          <option value="restore">Put the deducted items back in stock</option>
          <option value="leave">Leave stock unchanged (e.g. food was prepared)</option>
        </select>
      </label>
      {needsVerification ? <>
      <label>Admin password <input required type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
      {user.mfa_enabled && <label>Authenticator code <input required pattern="[0-9]{6}" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} /></label>}
      </> : <p role="status">Admin verified. Confirm this correction before verification expires.</p>}
      <button className="action-button primary" type="submit">{pending ? "Voiding…" : "Confirm void"}</button>
      <button className="action-button secondary" type="button" onClick={() => { setOpen(false); setError(null); setPassword(""); setCode(""); }}>Keep invoice</button>
    </fieldset>
  </form>;
}
