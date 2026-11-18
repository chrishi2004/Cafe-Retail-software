import { CafeCartPanel } from "./CafeCartPanel";
import { CafeMenuList } from "./CafeMenuList";
import { CafeOrderStatus } from "./CafeOrderStatus";
import { useCafeCart } from "./useCafeCart";
import { useCafeSession } from "./useCafeSession";

import "../styles.css";

export function CustomerMenu({ qrToken }: { qrToken: string }) {
  const cafe = useCafeSession(qrToken);
  const cart = useCafeCart(cafe.menu, cafe.session, async () => {
    if (cafe.session) await cafe.refresh(cafe.session);
  });

  const requestBill = async () => {
    if (!cafe.session) return;
    cart.setBusy(true);
    cart.setError(null);
    try {
      await cafe.session.requestBill();
      cart.setMessage("Bill requested. Cafe staff will complete billing and payment.");
      await cafe.refresh(cafe.session);
    } catch {
      cart.setError("The bill request could not be confirmed.");
    } finally {
      cart.setBusy(false);
    }
  };

  if (cafe.state === "loading") {
    return <main className="login-shell"><section className="login-card"><h1>Opening your table menu…</h1><p className="page-description">Checking the current Cafe session.</p></section></main>;
  }
  if (cafe.state === "invalid") {
    return <main className="login-shell"><section className="login-card"><h1>This table link is unavailable</h1><p className="page-description">The QR may be expired, revoked, or the table session may already be closed.</p></section></main>;
  }
  if (cafe.state === "offline" || !cafe.menu) {
    return <main className="login-shell"><section className="login-card"><h1>Menu temporarily unavailable</h1><p className="page-description">The Cafe service could not be reached. Reopen the QR when the connection is available.</p></section></main>;
  }

  const acceptingItems = cafe.sessionStatus === "open";
  return (
    <main style={{ minHeight: "100vh", padding: 16, background: "#f4f6f8" }}>
      <div className="page-stack" style={{ maxWidth: 760, margin: "0 auto" }}>
        <header className="page-header">
          <div><p className="eyebrow">{cafe.menu.cafe_name}</p><h1>{cafe.menu.table_display_name}</h1><p className="page-description">Table {cafe.menu.table_code} · {cafe.sessionStatus.replace(/_/g, " ")}</p></div>
          <span className={`status-badge ${acceptingItems ? "ok" : "warning"}`}>{acceptingItems ? "Ordering open" : "Ordering paused"}</span>
        </header>
        {cart.message ? <div className="success-banner" role="status">{cart.message}</div> : null}
        {cart.error ? <div className="state-panel" role="alert"><p>{cart.error}</p></div> : null}
        {!acceptingItems ? <div className="state-panel"><p>New items are disabled for this session. Existing order status is still available.</p></div> : null}
        <CafeMenuList menu={cafe.menu} acceptingItems={acceptingItems} quantity={cart.quantity} changeQuantity={cart.changeQuantity} />
        <CafeCartPanel lines={cart.lines} total={cart.total} customerNotes={cart.customerNotes} pendingRetry={Boolean(cart.pendingKey)} busy={cart.busy} acceptingItems={acceptingItems} changeLineNote={cart.changeLineNote} changeCustomerNotes={cart.changeCustomerNotes} submit={cart.submit} />
        <CafeOrderStatus orders={cafe.orders} sessionStatus={cafe.sessionStatus} busy={cart.busy} requestBill={requestBill} />
      </div>
    </main>
  );
}
