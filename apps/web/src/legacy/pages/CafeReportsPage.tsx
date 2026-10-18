import { useCallback, useEffect, useRef, useState } from "react";

import { downloadExport } from "../api/exports";
import { getCafeDashboard, type P9Dashboard } from "../api/p9";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";
import { cafeRange, PRESETS, type CafePreset } from "../utils/cafeDates";

const money = (value: string | number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(Number(value) || 0);

export function CafeReportsPage() {
  const { token, user } = useAuth();
  const [preset, setPreset] = useState<CafePreset>("Today");
  const [startDate, setStartDate] = useState(() => cafeRange("Today").startDate);
  const [endDate, setEndDate] = useState(() => cafeRange("Today").endDate);
  const [report, setReport] = useState<P9Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const requestId = useRef(0);
  const load = useCallback(async () => {
    const id = ++requestId.current;
    if (!token) return;
    if (!startDate || !endDate || startDate > endDate) { setError("Select a valid date range."); setLoading(false); return; }
    setLoading(true);
    setError(null);
    try {
      const data = await getCafeDashboard(token, { startDate, endDate });
      if (id === requestId.current) setReport(data);
    } catch (failure) {
      if (id === requestId.current) setError(failure instanceof Error ? failure.message : "Cafe reporting could not be loaded.");
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [token, startDate, endDate]);

  useEffect(() => {
    void load();
    return () => { requestId.current += 1; };
  }, [load]);

  const exportCsv = async () => {
    if (!token) return;
    setExporting(true);
    setError(null);
    try {
      await downloadExport(token, "cafe", { startDate: startDate || undefined, endDate: endDate || undefined });
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Cafe report export failed.");
    } finally {
      setExporting(false);
    }
  };

  if (!token) return null;
  if (loading && !report) return <LoadingState label="Loading Cafe reports" />;

  return (
    <section className="page-stack" aria-labelledby="cafe-reports-title">
      <div className="page-header">
        <div>
          <p className="eyebrow">Cafe reporting</p>
          <h2 id="cafe-reports-title">{user?.company_name ?? "Cafe"} performance</h2>
          <p className="page-description">Review billed revenue, collections, outstanding balances, order channels and payment modes without exposing Retail data.</p>
        </div>
      </div>

      <div className="filter-bar">
        <div className="filter-actions">
          <label>Period <select value={preset} onChange={(event) => {
            const next = event.target.value as CafePreset; setPreset(next);
            if (next !== "Custom Range") { const range = cafeRange(next); setStartDate(range.startDate); setEndDate(range.endDate); }
          }}>{PRESETS.map((value) => <option key={value}>{value}</option>)}</select></label>
          <label>From <input type="date" value={startDate} onChange={(event) =>  { setPreset("Custom Range"); setStartDate(event.target.value); }} /></label>
          <label>To <input type="date" value={endDate} onChange={(event) =>  { setPreset("Custom Range"); setEndDate(event.target.value); }} /></label>
        </div>
        <div className="filter-actions">
          <button className="action-button secondary" onClick={() => void load()} type="button">Apply dates</button>
          <button className="action-button primary" disabled={exporting || loading || !report || report.period_start !== startDate || report.period_end !== endDate} onClick={() => void exportCsv()} type="button">
            {exporting ? "Preparing CSV" : "Download Cafe CSV"}
          </button>
        </div>
      </div>

      {error ? <ErrorState message={error} /> : null}
      {report ? (
        <>
          <section className="metric-grid">
            <div className="metric-card green"><span>Net billed revenue</span><strong>{money(report.kpis.net_billed_revenue)}</strong></div>
            <div className="metric-card amber"><span>Collections</span><strong>{money(report.kpis.collections)}</strong></div>
            <div className="metric-card rose"><span>Outstanding</span><strong>{money(report.kpis.outstanding)}</strong></div>
            <div className="metric-card blue"><span>Average bill</span><strong>{money(report.kpis.average_bill_value)}</strong></div>
          </section>
          <div className="content-grid">
            <article className="panel">
              <div className="panel-header"><h3>Order channels</h3></div>
              {Object.entries(report.source_channel_mix).map(([channel, value]) => <p key={channel}>{channel.replace(/_/g, " ")}: {money(value)}</p>)}
            </article>
            <article className="panel">
              <div className="panel-header"><h3>Payment modes</h3></div>
              {Object.entries(report.payment_mode_mix).map(([mode, value]) => <p key={mode}>{mode.replace(/_/g, " ")}: {money(value)}</p>)}
            </article>
          </div>
          <article className="panel wide">
            <div className="panel-header"><h3>Top-selling Cafe items</h3><span>{report.period_start} to {report.period_end}</span></div>
            {report.top_items.length === 0 ? <p className="page-description">No Cafe item sales in this period.</p> : (
              <div className="table-wrap"><table><thead><tr><th>Item</th><th>Units</th><th>Ordered value</th></tr></thead><tbody>
                {report.top_items.map((item) => <tr key={item.menu_item_id}><td>{item.item_name}</td><td>{item.units_sold}</td><td>{money(item.ordered_value)}</td></tr>)}
              </tbody></table></div>
            )}
          </article>
        </>
      ) : null}
    </section>
  );
}
