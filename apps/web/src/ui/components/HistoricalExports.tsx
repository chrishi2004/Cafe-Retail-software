import { useEffect, useState } from "react";
import { apiRequest } from "../api/client";
import { downloadCsv } from "../api/exports";
import { listBranches } from "../api/masterData";
import { useAuth } from "../auth/AuthContext";
import { cafeRange, PRESETS, type CafePreset } from "../utils/cafeDates";

const REPORTS = [
  ["sales", "Sales by period"],
  ["consolidated", "Café and Retail financial summary"],
  ["invoices", "Invoice history"],
  ["payments", "Payment and credit history"],
  ["reversals", "Refund, cancellation and correction history"],
  ["expenses", "Expense ledger"],
  ["inventory", "Current stock balances"],
  ["movements", "Stock movement history"],
  ["stock-feeds", "Stock feed history"],
  ["purchases", "Supplier purchase orders"],
  ["supplier-payments", "Recorded supplier payments"],
  ["closings", "Daily Closing and cash variance"],
  ["employees", "Employee transaction summary"],
] as const;
type Report = typeof REPORTS[number][0];
type Option = { id: number; name: string };
type Options = { companies: Option[]; branches: (Option & { company_id: number })[] };

export function HistoricalExports({ group = false, initialRange }: {
  group?: boolean;
  initialRange?: { startDate: string; endDate: string };
}) {
  const { user, token } = useAuth();
  const [options, setOptions] = useState<Options>();
  const [kind, setKind] = useState<Report>(group ? "consolidated" : "sales");
  const [preset, setPreset] = useState<CafePreset>(initialRange ? "Custom Range" : "This Month");
  const [range, setRange] = useState(initialRange ?? cafeRange("This Month"));
  const [company, setCompany] = useState("");
  const [branch, setBranch] = useState("");
  const [cadence, setCadence] = useState("daily");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [optionsError, setOptionsError] = useState("");
  const allowed = !!user && ["super_admin", "admin", "store_manager", "analyst"].includes(user.server_role);
  useEffect(() => {
    if (!allowed || !token) return;
    let active = true;
    setOptions(undefined);
    setOptionsError("");
    const result = group ? apiRequest<Options>("/audit/options", {}, token) : listBranches(token, { includeInactive: true }).then(branches => ({
      companies: [], branches: branches.map(row => ({ id: row.id, name: row.name, company_id: 0 })),
    }));
    void result.then(value => { if (active) setOptions(value); })
      .catch((err: Error) => { if (active) setOptionsError(err.message); });
    return () => { active = false; };
  }, [allowed, token, group]);
  useEffect(() => {
    if (initialRange && initialRange.startDate && initialRange.endDate) {
      setPreset("Custom Range");
      setRange({ startDate: initialRange.startDate, endDate: initialRange.endDate });
    }
  }, [initialRange?.startDate, initialRange?.endDate]);

  if (!allowed || !token) return null;
  return (
    <article className="panel page-stack" aria-label="Historical CSV exports">
      <div className="panel-header"><h3>Historical CSV exports</h3></div>
      <p>Download the full selected period in India Standard Time. Bills, actual payments and refunds have separate dates.</p>
      <form className="filter-bar" onSubmit={async event => {
        event.preventDefault();
        setBusy(true);
        setError("");
        try {
          const query = new URLSearchParams();
          if (kind !== "inventory") {
            const effective = preset === "Custom Range" ? range : cafeRange(preset);
            if (!effective.startDate || !effective.endDate || effective.startDate > effective.endDate) throw new Error("Choose a valid date range.");
            query.set("start_date", effective.startDate);
            query.set("end_date", effective.endDate);
          }
          if (company) query.set("company_id", company);
          if (branch) query.set("branch_id", branch);
          if (kind === "sales") query.set("cadence", cadence);
          await downloadCsv(token, `/exports/history/${kind}?${query}`, `${kind}.csv`);
        } catch (failure) {
          setError(failure instanceof Error ? failure.message : "Could not download this report.");
        } finally { setBusy(false); }
      }}>
        <label>Report<select aria-label="Historical report" value={kind} onChange={event => setKind(event.target.value as Report)}>
          {REPORTS.filter(([key]) => group || key !== "consolidated").map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select></label>
        {group && <label>Venture<select aria-label="Export venture" value={company} onChange={event => { setCompany(event.target.value); setBranch(""); }}>
          <option value="">All ventures</option>{options?.companies.map(row => <option value={row.id} key={row.id}>{row.name}</option>)}
        </select></label>}
        <label>Branch<select aria-label="Export branch" value={branch} onChange={event => setBranch(event.target.value)}>
          <option value="">All authorized branches</option>
          {options?.branches.filter(row => !company || String(row.company_id) === company).map(row => <option value={row.id} key={row.id}>
            {row.name}{group && !company ? ` · ${options.companies.find(item => item.id === row.company_id)?.name ?? ""}` : ""}
          </option>)}
        </select></label>
        {kind !== "inventory" && <>
          <label>Date range<select aria-label="Export date range" value={preset} onChange={event => {
            const next = event.target.value as CafePreset; setPreset(next);
            if (next !== "Custom Range") setRange(cafeRange(next));
          }}>{PRESETS.map(item => <option key={item}>{item}</option>)}</select></label>
          <label>From (IST)<input aria-label="Export from date" type="date" required value={range.startDate}
            onChange={event => { setRange(current => ({ ...current, startDate: event.target.value })); setPreset("Custom Range"); }} /></label>
          <label>Through (IST)<input aria-label="Export through date" type="date" required value={range.endDate}
            onChange={event => { setRange(current => ({ ...current, endDate: event.target.value })); setPreset("Custom Range"); }} /></label>
        </>}
        {kind === "sales" && <label>Group sales by<select aria-label="Export sales interval" value={cadence} onChange={event => setCadence(event.target.value)}>
          <option value="daily">Day</option><option value="weekly">Week (Monday–Sunday)</option><option value="monthly">Month</option>
        </select></label>}
        <button type="submit" className="action-button primary" disabled={busy || !options}>{busy ? "Preparing CSV…" : "Download historical CSV"}</button>
      </form>
      {kind === "inventory" && <small>Stock balances show the current on-hand, reserved and on-order quantities. For past changes, download Stock movement history.</small>}
      {kind === "supplier-payments" && <small>Includes supplier payments recorded as stock-purchase expenses. Purchase orders and unpaid supplier credit do not count as payments.</small>}
      {kind === "employees" && <small>Amounts are grouped by the employee who issued the invoice, recorded the receipt or recorded the refund.</small>}
      {error || optionsError ? <p role="alert">{error || optionsError}</p> : null}
    </article>
  );
}
