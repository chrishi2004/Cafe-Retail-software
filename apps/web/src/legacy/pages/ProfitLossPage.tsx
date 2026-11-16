import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ProfitLossReport } from "../../server/profit-loss";
import { apiRequest } from "../api/client";
import { downloadCsv } from "../api/exports";
import { ErrorState, LoadingState } from "../components/ui";
import { cafeRange, PRESETS, type CafePreset } from "../utils/cafeDates";
import { formatCurrency, formatDate } from "../utils/format";

const endpoint = "/financial/profit-loss";
type Option = { id: number; name: string };
type ScopeOptions = { companies: Option[]; branches: (Option & { company_id: number })[] };
type Metrics = ProfitLossReport["current"];
type Filters = ReturnType<typeof defaultFilters>;

function defaultFilters() {
  return { ...cafeRange("This Month"), company: "", branch: "" };
}

function query(filters: Filters) {
  const params = new URLSearchParams({ start_date: filters.startDate, end_date: filters.endDate });
  if (filters.company) params.set("company_id", filters.company);
  if (filters.branch) params.set("branch_id", filters.branch);
  return params;
}

const statusText: Record<Metrics["quality"]["status"], string> = {
  recorded_cost_covered: "Recorded cost coverage",
  cost_data_incomplete: "Cost data incomplete",
  billing_data_incomplete: "Billing data incomplete",
  no_sales: "No active sales for this period",
};

const performanceRows = [
  ["gross_billed_sales", "Gross billed sales (including GST)"],
  ["cancelled_sales_adjustments", "Cancelled and voided sales adjustments"],
  ["net_billed_sales", "Net billed sales (including GST)"],
  ["recorded_sales_tax", "Recorded sales tax"],
  ["net_recognized_sales", "Net recognized sales (excluding GST)"],
  ["recorded_cogs", "Recorded COGS"],
  ["gross_profit", "Recorded gross profit"],
  ["gross_margin_percent", "Gross margin"],
  ["operating_expenses", "Recorded operating expenses"],
  ["stock_purchases", "Recorded stock purchases (shown separately)"],
  ["operating_result", "Recorded operating result"],
] as const satisfies readonly [keyof Omit<Metrics, "quality">, string][];

const collectionRows = [
  ["cash_collections", "Cash collections"],
  ["upi_collections", "UPI collections"],
  ["card_collections", "Card collections"],
  ["other_collections", "Other collections"],
  ["gross_collections", "Gross collections"],
  ["actual_refunds", "Actual refunds"],
  ["actual_cash_refunds", "Actual cash refunds"],
  ["net_collections", "Net collections after refunds"],
  ["cash_operating_expenses", "Cash operating expenses"],
  ["cash_supplier_outflows", "Recorded supplier cash outflows"],
  ["outstanding_invoice_credit", "Outstanding credit on selected invoices"],
] as const satisfies readonly [keyof Omit<Metrics, "quality">, string][];

function metricText(value: string | null, percent = false) {
  if (value === null) return "Unavailable";
  return percent ? value + "%" : formatCurrency(value);
}

function MetricsTable({ rows, report, label }: { rows: readonly (typeof performanceRows[number] | typeof collectionRows[number])[]; report: ProfitLossReport; label: string }) {
  return <div className="table-wrap">
    <table aria-label={label}>
      <thead><tr><th scope="col">Metric</th><th scope="col">Selected period</th><th scope="col">Previous period</th></tr></thead>
      <tbody>{rows.map(([key, title]) => (
        <tr key={key}><th scope="row">{title}</th><td>{metricText(report.current[key], key === "gross_margin_percent")}</td>
          <td>{metricText(report.previous[key], key === "gross_margin_percent")}</td></tr>
      ))}</tbody>
    </table>
  </div>;
}

function ReportView({ report }: { report: ProfitLossReport }) {
  const q = report.current.quality;
  const trend = report.trend.map(row => ({
    date: formatDate(row.period_ist),
    sales: row.net_recognized_sales === null ? null : Number(row.net_recognized_sales),
    expenses: Number(row.operating_expenses), purchases: Number(row.stock_purchases),
  }));
  return <>
    <article className="state-panel" aria-label="Data quality">
      <strong>{statusText[q.status]}</strong>
      <p>{q.status === "recorded_cost_covered"
        ? "Results use recorded sale-time costs and posted expenses. They are an operating estimate, not verified net profit."
        : q.status === "no_sales" ? "Profit and margin are unavailable without active sales."
        : "Profit, margin and operating result are withheld. Recorded costs may cover only part of the period."}</p>
      {q.cafe_lines_without_recipe_cost > 0 && <p>{q.cafe_lines_without_recipe_cost} Café invoice lines have no ingredient recipe cost coverage.</p>}
      {q.missing_cost_lines > 0 && <p>{q.missing_cost_lines} sale lines or invoices lack a usable historical cost.</p>}
      {q.inferred_cost_lines > 0 && <p>{q.inferred_cost_lines} historical lines use costs derived from their saved sale-time margin.</p>}
      {q.unpriced_stock_receipts > 0 && <p>{q.unpriced_stock_receipts} stock receipts lack a recorded purchase cost; the stock purchase total is incomplete.</p>}
      {q.missing_tax_records + q.invalid_billing_records > 0 && <p>{q.missing_tax_records + q.invalid_billing_records} billing records lack reliable totals or tax data. Recognized sales are unavailable.</p>}
    </article>
    <section className="metric-grid" aria-label="Profit and loss summary">
      <article className="metric-card blue"><p>Net recognized sales</p><strong>{metricText(report.current.net_recognized_sales)}</strong><span>Excluding recorded GST</span></article>
      <article className="metric-card"><p>Gross margin</p><strong>{metricText(report.current.gross_margin_percent, true)}</strong><span>{statusText[q.status]}</span></article>
      <article className="metric-card green"><p>Recorded operating result</p><strong>{metricText(report.current.operating_result)}</strong><span>From recorded costs and operating expenses</span></article>
      <article className="metric-card"><p>Net collections</p><strong>{metricText(report.current.net_collections)}</strong><span>Actual receipts less actual refunds</span></article>
    </section>
    <article className="panel wide">
      <h3>Sales and expense trends</h3>
      <p>By {report.trend_interval} in IST for the selected dates.</p>
      <ResponsiveContainer width="100%" height={270}>
        <LineChart data={trend} margin={{ right: 18, left: 12 }}>
          <CartesianGrid stroke="#e7ebf1" vertical={false} />
          <XAxis dataKey="date" minTickGap={18} />
          <YAxis width={76} tickFormatter={value => "₹" + Number(value).toLocaleString("en-IN")} />
          <Tooltip formatter={value => formatCurrency(Number(value))} />
          <Legend />
          <Line type="linear" dataKey="sales" name="Recognized sales" stroke="#142a49" strokeWidth={2} dot={trend.length === 1} isAnimationActive={false} />
          <Line type="linear" dataKey="expenses" name="Operating expenses" stroke="#0b8075" strokeWidth={2} dot={trend.length === 1} isAnimationActive={false} />
          <Line type="linear" dataKey="purchases" name="Stock purchases" stroke="#9a622b" strokeDasharray="5 4" dot={trend.length === 1} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </article>
    <article className="panel wide">
      <h3>Financial performance and period comparison</h3>
      <p><strong>{report.scope.venture}</strong>{report.scope.branch !== null ? ` · ${report.scope.branch}` : " · All branches"}</p>
      <p>{report.period.start} to {report.period.end} vs. {report.previous_period.start} to {report.previous_period.end} (IST)</p>
      <MetricsTable rows={performanceRows} report={report} label="Financial performance" />
    </article>
    <article className="panel wide">
      <h3>Operating expenses by category</h3>
      {report.expenses_by_category.length ? <div className="table-wrap"><table>
        <thead><tr><th scope="col">Category</th><th scope="col">Amount</th></tr></thead>
        <tbody>{report.expenses_by_category.map(row => <tr key={row.category}><th scope="row">{row.category.replaceAll("_", " ")}</th>
          <td>{formatCurrency(row.amount)}</td></tr>)}</tbody>
      </table></div> : <p>No posted operating expenses in the selected period.</p>}
    </article>
    <article className="panel wide">
      <h3>Collections, refunds and customer credit</h3>
      <p>Receipts and refunds use their own business dates. These totals do not include the till’s opening cash.</p>
      <MetricsTable rows={collectionRows} report={report} label="Collections and customer credit" />
      <p>{report.current_customer_ledger_credit === null
        ? "Branch credit shows balances on the selected invoices. The shared customer ledger does not allocate every credit balance by branch."
        : <>Current customer ledger credit across all dates: <strong>{formatCurrency(report.current_customer_ledger_credit)}</strong>. Separate from balances on selected invoices.</>}</p>
      <p>Supplier payables are unavailable because there is no supplier balance ledger.</p>
    </article>
    {report.by_venture.length > 1 && <article className="panel wide">
      <h3>Venture comparison</h3>
      <div className="table-wrap"><table>
        <thead><tr><th scope="col">Venture</th><th scope="col">Recognized sales</th><th scope="col">Recorded COGS</th>
          <th scope="col">Operating result</th><th scope="col">Cost data</th></tr></thead>
        <tbody>{report.by_venture.map(row => <tr key={row.company_id}><th scope="row">{row.venture}</th>
          <td>{metricText(row.current.net_recognized_sales)}</td><td>{metricText(row.current.recorded_cogs)}</td>
          <td>{metricText(row.current.operating_result)}</td><td>{statusText[row.current.quality.status]}</td></tr>)}</tbody>
      </table></div>
    </article>}
  </>;
}

export function ProfitLossPage({ token }: { token: string }) {
  const [options, setOptions] = useState<ScopeOptions>();
  const [preset, setPreset] = useState<CafePreset>("This Month");
  const [filters, setFilters] = useState(defaultFilters);
  const [selected, setSelected] = useState(defaultFilters);
  const [report, setReport] = useState<ProfitLossReport>();
  const [optionsError, setOptionsError] = useState("");
  const [reportError, setReportError] = useState("");
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    void apiRequest<ScopeOptions>(endpoint + "/options", { signal: controller.signal }, token).then(setOptions)
      .catch((error: Error) => { if (!controller.signal.aborted) setOptionsError(error.message); });
    return () => controller.abort();
  }, [token]);
  useEffect(() => {
    const controller = new AbortController();
    setReport(undefined);
    setReportError("");
    void apiRequest<ProfitLossReport>(endpoint + "?" + query(selected), { signal: controller.signal }, token).then(setReport)
      .catch((error: Error) => { if (!controller.signal.aborted) setReportError(error.message); });
    return () => controller.abort();
  }, [selected, token]);

  return <>
    <article className="panel">
      <p>Compare Café and Retail financial performance, with separate figures for sales, collections and available cost data.</p>
      <form className="filter-bar" onSubmit={event => { event.preventDefault(); setSelected({ ...filters }); setExportError(""); }}>
        <label>Venture<select aria-label="Financial venture" value={filters.company} onChange={e => setFilters(current => ({ ...current, company: e.target.value, branch: "" }))}>
          <option value="">Consolidated</option>{options?.companies.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select></label>
        <label>Branch<select aria-label="Financial branch" value={filters.branch} onChange={e => setFilters(current => ({ ...current, branch: e.target.value }))}>
          <option value="">All branches</option>{options?.branches.filter(item => !filters.company || String(item.company_id) === filters.company).map(item =>
            <option key={item.id} value={item.id}>{item.name}{!filters.company && ` · ${options.companies.find(c => c.id === item.company_id)?.name ?? ""}`}</option>)}
        </select></label>
        <label>Date range<select aria-label="Financial date range" value={preset} onChange={e => {
          const next = e.target.value as CafePreset;
          setPreset(next);
          if (next !== "Custom Range") setFilters(current => ({ ...current, ...cafeRange(next) }));
        }}>{PRESETS.map(item => <option key={item}>{item}</option>)}</select></label>
        <label>From (IST)<input aria-label="Financial from date" type="date" required value={filters.startDate} onChange={e => {
          setPreset("Custom Range"); setFilters(current => ({ ...current, startDate: e.target.value }));
        }} /></label>
        <label>Through (IST)<input aria-label="Financial through date" type="date" required min={filters.startDate} value={filters.endDate} onChange={e => {
          setPreset("Custom Range"); setFilters(current => ({ ...current, endDate: e.target.value }));
        }} /></label>
        <button className="action-button primary" type="submit" disabled={!options}>Apply filters</button>
        <button className="action-button" type="button" disabled={!report || exporting} onClick={async () => {
          setExporting(true); setExportError("");
          try {
            const params = query(selected);
            params.set("format", "csv");
            await downloadCsv(token, endpoint + "?" + params, "profit-loss.csv");
          } catch (error) { setExportError(error instanceof Error ? error.message : "Could not download this report."); }
          finally { setExporting(false); }
        }}>{exporting ? "Preparing CSV…" : "Download CSV"}</button>
      </form>
      {optionsError || reportError || exportError ? <ErrorState message={optionsError || reportError || exportError} /> : null}
    </article>
    {report ? <ReportView report={report} /> : !reportError && <LoadingState label="Loading financial report" />}
  </>;
}
