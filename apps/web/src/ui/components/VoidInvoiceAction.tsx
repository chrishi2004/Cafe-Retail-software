import { useRef, useState } from "react";
import { apiRequest } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { businessDate, inBusinessRange } from "../../businessDates";

type Invoice = {
  id: number;
  number: string;
  status?: string;
  type?: string;
  source?: string;
  issuedAt?: string | null;
  invoiceDate: string;
  paid?: string;
};

export function VoidInvoiceAction({ invoice, onVoided }: { invoice: Invoice; onVoided: () => void }) {
  const { token, user } = useAuth();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);
  const key = useRef("");
  if (!token || !user || !["admin", "super_admin"].includes(user.server_role)) return null;
  const today = businessDate();
  if (
    !["paid", "partial_paid", "credit", "unpaid", "issued"].includes(invoice.status ?? "") ||
    invoice.type !== "non_gst" || invoice.source === "cafe_table_session" ||
    !invoice.issuedAt || !inBusinessRange(invoice.issuedAt, today, today) ||
    !inBusinessRange(invoice.invoiceDate, today, today)
  ) return null;

  const remove = async () => {
    if (busy.current || !window.confirm(
      `Permanently delete invoice ${invoice.number}? This removes the bill from sales and it cannot be reprinted. Stock stays unchanged.` +
      (Number(invoice.paid) > 0 ? "\n\nPayment still counts in collections. Use Refunds to record money returned or correct a mistaken payment." : ""),
    )) return;

    busy.current = true;
    setPending(true);
    setError(null);
    try {
      key.current ||= crypto.randomUUID();
      await apiRequest(`/governance/voids/invoices/${invoice.id}`, {
        method: "POST",
        headers: { "Idempotency-Key": key.current },
        body: JSON.stringify({ confirmed: true, delete_permanently: true }),
      }, token);
      onVoided();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      busy.current = false;
      setPending(false);
    }
  };

  return <>
    <button
      type="button"
      className="action-button secondary"
      aria-label={`Delete invoice ${invoice.number}`}
      disabled={pending}
      onClick={() => void remove()}
    >
      {pending ? "Deleting…" : "Delete invoice"}
    </button>
    {error && <p role="alert">{error}</p>}
  </>;
}
