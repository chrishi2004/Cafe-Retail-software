import { type FormEvent, useCallback, useEffect, useState } from "react";
import { CheckCircle2, CircleOff, KeyRound, Pencil, Plus, Printer, RefreshCw, RotateCw, Users, X } from "lucide-react";

import {
  closeTableSession,
  createCafeTable,
  getTableSession,
  listCafeTables,
  openTableSession,
  renderTableQr,
  revokeTableQr,
  rotateTableQr,
  type CafeTable,
  type CafeTableInput,
  type QRPrintData,
  updateCafeTable,
} from "../api/cafe";
import { ApiError } from "../api/client";
import { listBranches } from "../api/masterData";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";
import type { Branch } from "../types";

function messageFrom(error: unknown): string {
  return error instanceof ApiError ? error.message : "Cafe table operation failed.";
}

function emptyTable(branchId = 0): CafeTableInput {
  return { branch_id: branchId, table_code: "", display_name: "", capacity: 4, area: "Indoor", is_active: true };
}

type OneTimeQr = {
  table: CafeTable;
  rawToken: string;
  printData: QRPrintData;
};

export function CafeTablesPage() {
  const { token, user } = useAuth();
  const canAdmin = user?.server_role === "super_admin" || user?.server_role === "admin";
  const canSession = canAdmin || user?.server_role === "store_manager" || user?.server_role === "order_taker";
  const [tables, setTables] = useState<CafeTable[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [editing, setEditing] = useState<CafeTable | null>(null);
  const [form, setForm] = useState<CafeTableInput>(() => emptyTable());
  const [oneTimeQr, setOneTimeQr] = useState<OneTimeQr | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const [tableRows, branchRows] = await Promise.all([listCafeTables(token), listBranches(token)]);
      setTables(tableRows);
      setBranches(branchRows.filter((branch) => branch.is_active));
      if (!form.branch_id && branchRows[0]) {
        setForm((current) => ({ ...current, branch_id: branchRows[0].id }));
      }
    } catch (loadError) {
      setError(messageFrom(loadError));
    } finally {
      setLoading(false);
    }
  }, [token, form.branch_id]);

  useEffect(() => {
    void load();
  }, [load]);

  function beginEdit(table: CafeTable) {
    setEditing(table);
    setForm({
      branch_id: table.branch_id,
      table_code: table.table_code,
      display_name: table.display_name,
      capacity: table.capacity,
      area: table.area,
      is_active: table.is_active,
    });
    setError(null);
    setSuccess(null);
  }

  function resetForm() {
    setEditing(null);
    setForm(emptyTable(branches[0]?.id ?? 0));
  }

  async function saveTable(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !canAdmin || !form.branch_id || !form.table_code.trim() || !form.display_name.trim()) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      if (editing) {
        await updateCafeTable(token, editing.id, {
          ...form,
          table_code: form.table_code.trim(),
          display_name: form.display_name.trim(),
          expected_version: editing.version,
        });
        setSuccess("Cafe table updated.");
      } else {
        await createCafeTable(token, {
          ...form,
          table_code: form.table_code.trim(),
          display_name: form.display_name.trim(),
        });
        setSuccess("Cafe table created.");
      }
      resetForm();
      await load();
    } catch (saveError) {
      setError(messageFrom(saveError));
    } finally {
      setSaving(false);
    }
  }

  async function rotateQr(table: CafeTable) {
    if (!token || !canAdmin) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    setOneTimeQr(null);
    try {
      const rotation = await rotateTableQr(token, table.id);
      const rendered = await renderTableQr(token, table.id, rotation.raw_token);
      setOneTimeQr({ table, rawToken: rotation.raw_token, printData: rendered });
      setSuccess("New QR credential generated. Save or print it now; the raw secret cannot be recovered later.");
      await load();
    } catch (rotateError) {
      setOneTimeQr(null);
      setError(messageFrom(rotateError));
    } finally {
      setSaving(false);
    }
  }

  async function revokeQr(table: CafeTable) {
    if (!token || !canAdmin) return;
    setSaving(true);
    setError(null);
    try {
      await revokeTableQr(token, table.id);
      if (oneTimeQr?.table.id === table.id) setOneTimeQr(null);
      setSuccess(`${table.display_name} QR revoked.`);
      await load();
    } catch (revokeError) {
      setError(messageFrom(revokeError));
    } finally {
      setSaving(false);
    }
  }

  async function openSession(table: CafeTable) {
    if (!token || !canSession) return;
    setSaving(true);
    setError(null);
    try {
      await openTableSession(token, table.id, "dine_in");
      setSuccess(`${table.display_name} session opened.`);
      await load();
    } catch (sessionError) {
      setError(messageFrom(sessionError));
    } finally {
      setSaving(false);
    }
  }

  async function closeSession(table: CafeTable) {
    if (!token || !canSession || !table.active_session_public_id) return;
    setSaving(true);
    setError(null);
    try {
      const session = await getTableSession(token, table.active_session_public_id);
      await closeTableSession(token, session.public_id, session.version, false);
      setSuccess(`${table.display_name} session closed.`);
      await load();
    } catch (sessionError) {
      setError(messageFrom(sessionError));
    } finally {
      setSaving(false);
    }
  }

  function printQr() {
    if (!oneTimeQr?.printData.qr_svg_data_uri) return;
    const popup = window.open("", "_blank", "noopener,noreferrer,width=520,height=700");
    if (!popup) {
      setError("Browser blocked the printable QR window.");
      return;
    }
    const { table, printData } = oneTimeQr;
    popup.document.write(`<!doctype html><html><head><title>${table.display_name} QR</title><style>body{font-family:system-ui;text-align:center;padding:32px}img{width:320px;height:320px}small{display:block;margin-top:16px;color:#555}</style></head><body><h1>${table.display_name}</h1><p>${table.table_code}</p><img alt="Cafe table QR" src="${printData.qr_svg_data_uri}"/><small>Expires: ${printData.expires_at ?? "No expiry"}</small><script>window.onload=()=>window.print()</script></body></html>`);
    popup.document.close();
  }

  if (loading && !tables.length) return <LoadingState label="Loading Cafe tables" />;

  return (
    <section className="page-stack">
      <div className="page-header">
        <div>
          <p className="eyebrow">Cafe floor administration</p>
          <h2>Tables & Secure QR</h2>
          <p className="page-description">QR codes identify a Cafe table only. P5 does not accept customer orders or create financial records.</p>
        </div>
        <button className="action-button secondary" type="button" onClick={() => void load()} disabled={loading || saving}><RefreshCw size={17} /> Refresh</button>
      </div>

      {error ? <ErrorState message={error} /> : null}
      {success ? <div className="state-panel success"><CheckCircle2 size={20} /><p>{success}</p></div> : null}

      {oneTimeQr ? (
        <article className="panel wide" aria-label="One-time QR credential">
          <div className="panel-header">
            <div>
              <p className="eyebrow">One-time QR preview</p>
              <h3>{oneTimeQr.table.display_name}</h3>
              <p className="page-description">The raw credential exists only in this temporary view. Dismiss it after saving or printing.</p>
            </div>
            <button className="table-action" type="button" onClick={() => setOneTimeQr(null)}><X size={16} /> Dismiss</button>
          </div>
          <div className="dashboard-grid">
            <div className="panel">
              {oneTimeQr.printData.qr_svg_data_uri ? <img className="qr-preview" src={oneTimeQr.printData.qr_svg_data_uri} alt={`QR for ${oneTimeQr.table.display_name}`} /> : <p>QR preview unavailable.</p>}
              <p className="muted-text">Reference: {oneTimeQr.printData.public_reference}</p>
              <p className="muted-text">Prefix: {oneTimeQr.printData.token_prefix}</p>
            </div>
            <div className="panel">
              <p className="eyebrow">Credential handling</p>
              <p className="page-description">Do not paste the raw token into notes, tickets, or chat. The server stores only its cryptographic hash.</p>
              <div className="form-actions">
                <button className="action-button primary" type="button" onClick={printQr} disabled={!oneTimeQr.printData.qr_svg_data_uri}><Printer size={17} /> Print QR</button>
                <button className="action-button secondary" type="button" onClick={() => setOneTimeQr(null)}>Dismiss secret</button>
              </div>
            </div>
          </div>
        </article>
      ) : null}

      <div className="dashboard-grid">
        {canAdmin ? (
          <form className="panel master-form" onSubmit={saveTable}>
            <div className="panel-header"><div><p className="eyebrow">Table editor</p><h3>{editing ? `Edit ${editing.display_name}` : "Add Cafe table"}</h3></div><Users size={21} /></div>
            <label>Branch<select value={form.branch_id || ""} onChange={(event) => setForm({ ...form, branch_id: Number(event.target.value) })} disabled={saving}>{branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}</select></label>
            <label>Table code<input value={form.table_code} onChange={(event) => setForm({ ...form, table_code: event.target.value })} placeholder="T01" disabled={saving} /></label>
            <label>Display name<input value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} placeholder="Table 1" disabled={saving} /></label>
            <label>Capacity<input type="number" min="1" value={form.capacity ?? ""} onChange={(event) => setForm({ ...form, capacity: event.target.value ? Number(event.target.value) : null })} disabled={saving} /></label>
            <label>Area<input value={form.area ?? ""} onChange={(event) => setForm({ ...form, area: event.target.value || null })} placeholder="Indoor" disabled={saving} /></label>
            <div className="form-actions"><button className="action-button primary" type="submit" disabled={saving || !form.branch_id || !form.table_code.trim() || !form.display_name.trim()}><Plus size={16} /> {editing ? "Save table" : "Add table"}</button>{editing ? <button className="action-button secondary" type="button" onClick={resetForm}>Cancel</button> : null}</div>
          </form>
        ) : null}

        <article className="panel">
          <div className="panel-header"><div><p className="eyebrow">Session rules</p><h3>Table lifecycle</h3></div><KeyRound size={21} /></div>
          <p className="page-description">Only Admin, Store Manager and Order Taker can open/close sessions. PostgreSQL enforces one active session per table even under concurrent requests.</p>
          <p className="page-description">Kitchen and Analyst roles remain read-only here.</p>
        </article>
      </div>

      <article className="panel wide">
        <div className="panel-header"><div><p className="eyebrow">Cafe floor</p><h3>{tables.length} tables</h3></div></div>
        {tables.length ? (
          <div className="data-table-shell">
            <table>
              <thead><tr><th>Table</th><th>Branch</th><th>Capacity</th><th>Session</th><th>QR</th><th>Actions</th></tr></thead>
              <tbody>
                {tables.map((table) => (
                  <tr key={table.id}>
                    <td><strong>{table.display_name}</strong><div className="muted-text">{table.table_code} · {table.area ?? "No area"} · v{table.version}</div></td>
                    <td>#{table.branch_id}</td>
                    <td>{table.capacity ?? "—"}</td>
                    <td><span className={`status-badge ${table.active_session_status ? "warning" : "success"}`}>{table.active_session_status ?? "free"}</span></td>
                    <td><span className={`status-badge ${table.qr_active ? "success" : "warning"}`}>{table.qr_active ? "Active" : "No active QR"}</span></td>
                    <td>
                      <div className="table-actions">
                        {canAdmin ? <button className="table-action" type="button" onClick={() => beginEdit(table)}><Pencil size={15} /> Edit</button> : null}
                        {canAdmin ? <button className="table-action" type="button" onClick={() => void rotateQr(table)} disabled={saving}><RotateCw size={15} /> {table.qr_active ? "Rotate QR" : "Generate QR"}</button> : null}
                        {canAdmin && table.qr_active ? <button className="table-action" type="button" onClick={() => void revokeQr(table)} disabled={saving}><CircleOff size={15} /> Revoke</button> : null}
                        {canSession && !table.active_session_public_id ? <button className="table-action" type="button" onClick={() => void openSession(table)} disabled={saving}>Open session</button> : null}
                        {canSession && table.active_session_public_id ? <button className="table-action" type="button" onClick={() => void closeSession(table)} disabled={saving}>Close session</button> : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="page-description">No Cafe tables configured yet.</p>}
      </article>
    </section>
  );
}
