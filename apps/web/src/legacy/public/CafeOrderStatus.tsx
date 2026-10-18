import type { PublicOrder } from "../api/publicCafeClient";

function price(value: string): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(Number(value));
}

function label(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}

export function CafeOrderStatus({
  orders,
  sessionStatus,
  busy,
  requestBill,
  continuityMode = "local",
}: {
  orders: PublicOrder[];
  sessionStatus: string;
  busy: boolean;
  requestBill: () => Promise<void>;
  continuityMode?: "local" | "cloud";
}) {
  return (
    <section className="panel page-stack" aria-label="Order status">
      <div className="panel-header"><h3>Order status</h3><span className="status-badge ok">Auto-refreshes</span></div>
      {!orders.length ? <p className="page-description">No orders placed from this device yet.</p> : orders.map((order) => (
        <article className="compact-list" key={order.public_id}>
          <div style={{ display: "grid", gap: 6 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}><strong>{order.order_number}</strong><span className="status-badge ok">{label(order.status)}</span></div>
            <span>{order.items.map((item) => `${item.quantity}× ${item.name}`).join(" · ")}</span>
            <strong>{price(order.estimated_total)}</strong>
          </div>
        </article>
      ))}
      {continuityMode === "cloud" ? <p className="page-description" style={{ fontSize: ".8rem" }}>Cloud continuity accepts the order while the Local Hub is unavailable. Cafe staff will reconcile it before billing.</p> : null}
      {continuityMode === "local" && orders.length > 0 && !["closed", "cancelled"].includes(sessionStatus) ? <button type="button" className="action-button secondary" disabled={busy || sessionStatus === "bill_requested"} onClick={() => void requestBill()}>{sessionStatus === "bill_requested" ? "Bill requested" : busy ? "Requesting…" : "Request bill"}</button> : null}
      <p className="page-description" style={{ fontSize: ".8rem" }}>Payment is completed with Cafe staff. This page cannot mark payment complete or close the table.</p>
    </section>
  );
}
