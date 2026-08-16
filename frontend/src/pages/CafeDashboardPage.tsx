import { useEffect, useState } from "react";

import { getCafeDashboard, type P9Dashboard } from "../api/p9";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";

const money = (value: string | number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(Number(value) || 0);

export function CafeDashboardPage() {
  const { token, user } = useAuth();
  const [dashboard, setDashboard] = useState<P9Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!token) return;
    void getCafeDashboard(token).then(setDashboard).catch((err: Error) => setError(err.message));
  }, [token]);
  if (!token || (!dashboard && !error)) return <LoadingState label="Loading Cafe dashboard" />;
  if (error) return <ErrorState message={error} />;
  if (!dashboard) return null;
  return (
    <section className="page-stack" data-p9-scope="cafe">
      <div className="page-header">
        <div><p className="eyebrow">P9 · Cafe dashboard</p><h2>{user?.company_name ?? "Cafe"} reporting</h2>
          <p className="page-description">Cafe-only metrics for {dashboard.period_start} through {dashboard.period_end}. Orders, invoices, collections and open sessions remain separate.</p>
        </div>
      </div>
      <section className="metric-grid">
        <div className="metric-card blue"><span>Ordered value</span><strong>{money(dashboard.kpis.ordered_value)}</strong></div>
        <div className="metric-card green"><span>Net billed revenue</span><strong>{money(dashboard.kpis.net_billed_revenue)}</strong></div>
        <div className="metric-card amber"><span>Collections</span><strong>{money(dashboard.kpis.collections)}</strong></div>
        <div className="metric-card rose"><span>Outstanding</span><strong>{money(dashboard.kpis.outstanding)}</strong></div>
        <div className="metric-card"><span>Open/unbilled sessions</span><strong>{dashboard.kpis.open_unbilled_sessions}</strong></div>
      </section>
      <div className="content-grid">
        <article className="panel"><div className="panel-header"><h3>Top Cafe items</h3></div>
          {dashboard.top_items.length === 0 ? <p className="page-description">No Cafe item sales in this period.</p> : <div className="table-wrap"><table><thead><tr><th>Item</th><th>Units</th><th>Ordered value</th></tr></thead><tbody>{dashboard.top_items.map((item) => <tr key={item.menu_item_id}><td>{item.item_name}</td><td>{item.units_sold}</td><td>{money(item.ordered_value)}</td></tr>)}</tbody></table></div>}
        </article>
        <article className="panel"><div className="panel-header"><h3>Reconciliation</h3></div>
          <p>Orders: {dashboard.kpis.order_count}</p><p>Cancelled before billing: {money(dashboard.kpis.cancelled_value)}</p><p>Average bill: {money(dashboard.kpis.average_bill_value)}</p><p>Table sessions: {dashboard.table_turnover.session_count}</p>
        </article>
      </div>
    </section>
  );
}
