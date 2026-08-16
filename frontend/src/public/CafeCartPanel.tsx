import type { PublicMenuItem } from "../api/publicCafeClient";

function price(value: string | number): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(Number(value));
}

export function CafeCartPanel({
  lines,
  total,
  customerNotes,
  pendingRetry,
  busy,
  acceptingItems,
  changeLineNote,
  changeCustomerNotes,
  submit,
}: {
  lines: Array<{ item: PublicMenuItem; quantity: number; notes: string }>;
  total: number;
  customerNotes: string;
  pendingRetry: boolean;
  busy: boolean;
  acceptingItems: boolean;
  changeLineNote: (id: string, value: string) => void;
  changeCustomerNotes: (value: string) => void;
  submit: () => Promise<void>;
}) {
  if (!lines.length) return null;
  return (
    <section className="panel page-stack" aria-label="Your cart">
      <div className="panel-header"><h3>Your order</h3><strong>{price(total)}</strong></div>
      {lines.map((line) => (
        <div className="compact-list" key={line.item.public_id}>
          <article style={{ display: "grid" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><strong>{line.item.name}</strong><span>{line.quantity} × {price(line.item.selling_price)}</span></div>
            <input style={{ width: "100%", minHeight: 38, border: "1px solid #d8dee8", borderRadius: 8, padding: "8px 10px" }} value={line.notes} maxLength={300} onChange={(event) => changeLineNote(line.item.public_id, event.target.value)} placeholder="Item note, optional" aria-label={`Note for ${line.item.name}`} />
          </article>
        </div>
      ))}
      <textarea style={{ width: "100%", minHeight: 72, border: "1px solid #d8dee8", borderRadius: 8, padding: "8px 10px" }} value={customerNotes} maxLength={500} onChange={(event) => changeCustomerNotes(event.target.value)} placeholder="Order note, optional" aria-label="Order note" />
      <button type="button" className="action-button primary" disabled={busy || !acceptingItems} onClick={() => void submit()}>{busy ? "Submitting…" : pendingRetry ? `Retry order · ${price(total)}` : `Place order · ${price(total)}`}</button>
      <p className="page-description" style={{ fontSize: ".8rem" }}>Cafe prices and totals are recalculated by the server before the order is accepted.</p>
    </section>
  );
}
