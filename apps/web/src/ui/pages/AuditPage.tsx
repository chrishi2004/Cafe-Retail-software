import { useEffect, useState } from "react";
import { businessDate, shiftDate } from "../../businessDates";
import { apiRequest } from "../api/client";
import { downloadCsv } from "../api/exports";

type Option = { id: number; name: string };
type Options = {
  companies: Option[];
  branches: (Option & { company_id: number })[];
  actors: Option[];
  categories: { id: string; label: string }[];
};
const columns = [
  ["timestamp_ist", "Time (IST)"], ["actor", "Actor"], ["action", "Action"], ["category", "Category"],
  ["venture", "Venture"], ["branch", "Branch"], ["record", "Affected record"], ["reference", "Reference"], ["outcome", "Outcome"],
] as const;
type Page = {
  rows: ({ id: number } & Record<typeof columns[number][0], string | null>)[];
  next_cursor: string | null;
};
type Filters = ReturnType<typeof defaults>;
const endpoint = "/audit/events";
function defaults() {
  const today = businessDate();
  return { start_date: shiftDate(today, -6), end_date: today, company_id: "", branch_id: "", actor_id: "", category: "", reference: "" };
}
function query(filters: Filters, extra: Record<string, string> = {}) {
  return "?" + new URLSearchParams(Object.entries({ ...filters, ...extra }).filter(([, value]) => value)).toString();
}

export function AuditPage({ token }: { token: string }) {
  const [options, setOptions] = useState<Options>();
  const [filters, setFilters] = useState(defaults);
  const [applied, setApplied] = useState(defaults);
  const [pages, setPages] = useState<string[]>([]);
  const [result, setResult] = useState<Page>();
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const cursor = pages.at(-1);
  useEffect(() => {
    const controller = new AbortController();
    void apiRequest<Options>("/audit/options", { signal: controller.signal }, token)
      .then(setOptions)
      .catch((err: Error) => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [token]);
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    setResult(undefined);
    void apiRequest<Page>(endpoint + query(applied, cursor ? { cursor } : {}), { signal: controller.signal }, token)
      .then(setResult)
      .catch((err: Error) => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [applied, cursor, token]);

  const update = (field: keyof Filters, value: string) =>
    setFilters(prev => ({ ...prev, [field]: value, ...(field === "company_id" ? { branch_id: "" } : {}) }));
  return (
    <article className="panel page-stack">
      <p>Review recorded activity across your businesses. Older entries may have missing information, and actions that were never logged cannot be shown.</p>
      <form className="filter-bar" onSubmit={event => { event.preventDefault(); setPages([]); setApplied({ ...filters }); setExportError(""); }}>
        <label>From (IST)<input type="date" required value={filters.start_date} onChange={e => update("start_date", e.target.value)} /></label>
        <label>Through (IST)<input type="date" required value={filters.end_date} onChange={e => update("end_date", e.target.value)} /></label>
        <label>Venture<select aria-label="Venture" value={filters.company_id} onChange={e => update("company_id", e.target.value)}>
          <option value="">All ventures</option>{options?.companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select></label>
        <label>Branch<select aria-label="Branch" value={filters.branch_id} onChange={e => update("branch_id", e.target.value)}>
          <option value="">All branches</option>{options?.branches.filter(b => !filters.company_id || String(b.company_id) === filters.company_id).map(b =>
            <option key={b.id} value={b.id}>{b.name} ({options.companies.find(c => c.id === b.company_id)?.name})</option>)}
        </select></label>
        <label>Employee<select aria-label="Employee" value={filters.actor_id} onChange={e => update("actor_id", e.target.value)}>
          <option value="">All employees</option>{options?.actors.map(a => <option key={a.id} value={a.id}>{a.name} (#{a.id})</option>)}
        </select></label>
        <label>Category<select aria-label="Category" value={filters.category} onChange={e => update("category", e.target.value)}>
          <option value="">All actions</option>{options?.categories.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
        </select></label>
        <label>Invoice or transaction reference<input value={filters.reference} maxLength={80} onChange={e => update("reference", e.target.value)} /></label>
        <button className="action-button primary" type="submit">Apply filters</button>
        <button className="action-button" type="button" disabled={!result || exporting} onClick={async () => {
          setExporting(true);
          setExportError("");
          try { await downloadCsv(token, endpoint + query(applied, { format: "csv" }), "operational-audit.csv"); }
          catch (err) { setExportError(err instanceof Error ? err.message : "Could not export audit history."); }
          finally { setExporting(false); }
        }}>{exporting ? "Exporting…" : "Download CSV"}</button>
      </form>
      {error || exportError ? <p role="alert">{error || exportError}</p> : null}
      {!result && !error ? <p role="status">Loading activity…</p> : null}
      {result && !result.rows.length ? <p role="status">No recorded activity matches these filters.</p> : null}
      {result?.rows.length ? (
        <>
          <div className="table-wrap">
            <table>
              <thead><tr>{columns.map(([key, label]) => <th scope="col" key={key}>{label}</th>)}</tr></thead>
              <tbody>{result.rows.map(row => <tr key={row.id}>{columns.map(([key]) => <td key={key}>{row[key] ?? "—"}</td>)}</tr>)}</tbody>
            </table>
          </div>
          <div className="filter-bar">
            <button className="action-button" type="button" disabled={!pages.length} onClick={() => setPages(previous => previous.slice(0, -1))}>Previous</button>
            <span>Page {pages.length + 1}</span>
            <button className="action-button" type="button" disabled={!result.next_cursor} onClick={() => {
              const next = result.next_cursor;
              if (next) setPages(previous => [...previous, next]);
            }}>Next</button>
          </div>
        </>
      ) : null}
    </article>
  );
}
