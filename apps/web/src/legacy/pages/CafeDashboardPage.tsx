import { useEffect, useState } from "react";

import { getCafeDashboard, type P9Dashboard } from "../api/p9";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";
import { listCafeOrders, type CafeOrder } from "../api/cafeOrders";
import { cafeRange } from "../utils/cafeDates";

const money = (value: string | number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(Number(value) || 0);

export function CafeDashboardPage() {
  const { token, user } = useAuth();
  const [dashboard, setDashboard] = useState<P9Dashboard | null>(null);
  const [orders, setOrders] = useState<CafeOrder[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!token) return;
    let active = true;
    const load = () => Promise.all([getCafeDashboard(token, cafeRange("Today")), listCafeOrders(token, { openOnly: true })])
      .then(([data, rows]) => { if (active) { setDashboard(data); setOrders(rows.filter((order) => !["closed", "cancelled", "rejected"].includes(order.status))); setError(null); } })
      .catch((err: Error) => { if (active) setError(err.message); });
    void load();
    const timer = window.setInterval(() => void load(), 30000);
    return () => { active = false; window.clearInterval(timer); };
  }, [token]);
  if (!token || (!dashboard && !error)) return <LoadingState label="Loading Cafe dashboard" />;
  if (error) return <ErrorState message={error} />;
  if (!dashboard) return null;
  return (
    <section className="page-stack" data-p9-scope="cafe">
      <div className="page-header">
        <div><p className="eyebrow">Today · Café dashboard</p><h2>{user?.company_name ?? "Cafe"} reporting</h2>
          <p className="page-description">Metrics for {dashboard.period_start} through {dashboard.period_end}. Orders, invoices, collections and open sessions remain separate.</p>
        </div>
      </div>
      <section className="metric-grid">
        <div className="metric-card"><span>Order count</span><strong>{dashboard.kpis.order_count}</strong></div>
        <div className="metric-card"><span>Average bill</span><strong>{money(dashboard.kpis.average_bill_value)}</strong></div>
        {["Cash", "UPI", "Card"].map((mode) => <div key={mode} className="metric-card"><span>{mode}</span><strong>{money(Object.entries(dashboard.payment_mode_mix).filter(([name]) => name.toLowerCase() === mode.toLowerCase()).reduce((sum, [, amount]) => sum + Number(amount), 0))}</strong></div>)}
        <div className="metric-card blue"><span>Ordered value</span><strong>{money(dashboard.kpis.ordered_value)}</strong></div>
        <div className="metric-card green"><span>Billed sales</span><strong>{money(dashboard.kpis.net_billed_revenue)}</strong></div>
        <div className="metric-card amber"><span>Collections</span><strong>{money(dashboard.kpis.collections)}</strong></div>
        <div className="metric-card rose"><span>Outstanding</span><strong>{money(dashboard.kpis.outstanding)}</strong></div>
        <div className="metric-card"><span>Open/unbilled sessions</span><strong>{dashboard.kpis.open_unbilled_sessions}</strong></div>
      </section>
      <article className="panel"><h3>Current / open orders</h3>
        {!orders.length ? <p>No open orders.</p> : <div className="table-wrap"><table><thead><tr><th>Order</th><th>Mode</th><th>Status</th><th>Value</th></tr></thead><tbody>{orders.map((order) => <tr key={order.public_id}><td>{order.order_number}</td><td>{order.order_type}</td><td>{order.status}</td><td>{money(order.estimated_total)}</td></tr>)}</tbody></table></div>}
      </article>
      <div className="content-grid">
        <article className="panel"><div className="panel-header"><h3>Top-selling items</h3></div>
          {dashboard.top_selling_items.length === 0 ? <p className="page-description">No Cafe item sales in this period.</p> : <div className="table-wrap"><table><thead><tr><th>Item</th><th>Units</th><th>Billed sales</th></tr></thead><tbody>{dashboard.top_selling_items.map((item) => <tr key={item.menu_item_id}><td>{item.item_name}</td><td>{item.units_sold}</td><td>{money(item.ordered_value)}</td></tr>)}</tbody></table></div>}
        </article>
        <article className="panel"><div className="panel-header"><h3>Reconciliation</h3></div>
          <p>Orders: {dashboard.kpis.order_count}</p><p>Cancelled before billing: {money(dashboard.kpis.cancelled_value)}</p><p>Average bill: {money(dashboard.kpis.average_bill_value)}</p><p>Table sessions: {dashboard.table_turnover.session_count}</p>
        </article>
      </div>
    </section>
  );
}
