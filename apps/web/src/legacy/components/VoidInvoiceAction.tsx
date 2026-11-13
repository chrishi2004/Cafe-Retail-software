import { useRef, useState } from "react";
import { apiRequest } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { cafeToday } from "../utils/cafeDates";

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

const businessDay = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit",
});

export function VoidInvoiceAction({ invoice, onVoided }: { invoice: Invoice; onVoided: () => void }) {
  const { token, user } = useAuth();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);
  const key = useRef("");
  if (!token || !user || !["admin", "super_admin"].includes(user.server_role)) return null;
  const today = cafeToday();
  if (
    !["paid", "partial_paid", "credit", "unpaid", "issued"].includes(invoice.status ?? "") ||
    invoice.type !== "non_gst" || invoice.source === "cafe_table_session" ||
    !invoice.issuedAt || businessDay.format(new Date(invoice.issuedAt)) !== today ||
    businessDay.format(new Date(invoice.invoiceDate)) !== today
  ) return null;

  const remove = async () => {
    if (busy.current || !window.confirm(
      `Delete invoice ${invoice.number} from today's sales?\n\n` +
      "The bill will be marked Cancelled and excluded from sales and collections. Stock will stay unchanged." +
      (Number(invoice.paid) > 0 ? "\n\nIf payment was actually received, return it separately before confirming." : ""),
    )) return;

    busy.current = true;
    setPending(true);
    setError(null);
    try {
      key.current ||= crypto.randomUUID();
      await apiRequest(`/governance/voids/invoices/${invoice.id}`, {
        method: "POST",
        headers: { "Idempotency-Key": key.current },
        body: JSON.stringify({ confirmed: true }),
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
