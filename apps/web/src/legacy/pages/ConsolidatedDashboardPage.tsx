import { useEffect, useState } from "react";

import { getConsolidatedDashboard, type P9Consolidated } from "../api/p9";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";

const money = (value: string | number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(Number(value) || 0);

export function ConsolidatedDashboardPage() {
  const { token } = useAuth();
  const [dashboard, setDashboard] = useState<P9Consolidated | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (token) void getConsolidatedDashboard(token).then(setDashboard).catch((err: Error) => setError(err.message)); }, [token]);
  if (!token || (!dashboard && !error)) return <LoadingState label="Loading consolidated dashboard" />;
  if (error) return <ErrorState message={error} />;
  if (!dashboard) return null;
  return (
    <section className="page-stack" data-p9-scope={dashboard.scope}>
      <div className="page-header"><div><p className="eyebrow">P9 · Consolidated dashboard</p><h2>All Ventures</h2><p className="page-description">Active scope: {dashboard.scope}. Retail and Cafe invoice sources are counted once.</p></div></div>
      <section className="metric-grid"><div className="metric-card green"><span>Net billed revenue</span><strong>{money(dashboard.kpis.net_billed_revenue)}</strong></div><div className="metric-card amber"><span>Collections</span><strong>{money(dashboard.kpis.collections)}</strong></div><div className="metric-card rose"><span>Outstanding</span><strong>{money(dashboard.kpis.outstanding)}</strong></div></section>
      <article className="panel wide"><div className="panel-header"><h3>Venture comparison</h3></div><div className="table-wrap"><table><thead><tr><th>Venture</th><th>Company</th><th>Net billed</th><th>Collections</th><th>Outstanding</th></tr></thead><tbody>{dashboard.venture_summaries.map((row) => <tr key={row.company_id}><td>{row.venture}</td><td>{row.company_name}</td><td>{money(row.net_billed_revenue)}</td><td>{money(row.collections)}</td><td>{money(row.outstanding)}</td></tr>)}</tbody></table></div></article>
    </section>
  );
}
