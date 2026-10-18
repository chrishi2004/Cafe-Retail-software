import { useCallback, useEffect, useState } from "react";
import {
  getSyncContinuityStatus,
  getLatestReconciliation,
  runReconciliation,
  type SyncContinuityStatus,
  type ReconciliationReport,
} from "../api/continuity";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";
export function CafeContinuityPage() {
  const { token, user } = useAuth();
  const [status, setStatus] = useState<SyncContinuityStatus | null>(null),
    [report, setReport] = useState<ReconciliationReport | null>(null),
    [error, setError] = useState<string | null>(null),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      setStatus(await getSyncContinuityStatus(token));
      try {
        setReport(await getLatestReconciliation(token));
      } catch {
        setReport(null);
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connection check failed.");
    } finally {
      setLoading(false);
    }
  }, [token]);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  const check = async () => {
    if (!token || busy) return;
    setBusy(true);
    try {
      setReport(await runReconciliation(token));
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Data check failed.");
    } finally {
      setBusy(false);
    }
  };
  if (loading) return <LoadingState label="Checking connection" />;
  return (
    <section className="page-stack">
      <div className="page-header">
        <div>
          <p className="eyebrow">Service health</p>
          <h2>Connection and data checks</h2>
          <p className="page-description">
            This hosted application needs internet access. Check recorded
            invoices, payments, orders and stock for inconsistencies.
          </p>
        </div>
      </div>
      {error ? <ErrorState message={error} /> : null}
      <article className="panel">
        <h3>{status ? "Database connected" : "Connection unavailable"}</h3>
        <p>{status?.attention_message}</p>
        <button className="secondary-button" onClick={() => void refresh()}>
          Refresh connection
        </button>
      </article>
      <article className="panel">
        <h3>Last data check: {report?.status ?? "Not run"}</h3>
        {report ? (
          <p>
            Invoice issues: {report.invoice_mismatch_count} · Payment issues:{" "}
            {report.payment_mismatch_count} · Stock issues:{" "}
            {report.stock_mismatch_count} · Order issues:{" "}
            {report.order_mismatch_count}
          </p>
        ) : null}
        <p>
          Checks report inconsistencies and do not change financial records.
        </p>
        {["super_admin", "admin", "store_manager"].includes(
          user?.server_role ?? "",
        ) ? (
          <button
            className="primary-button"
            disabled={busy}
            onClick={() => void check()}
          >
            {busy ? "Checking…" : "Run data check"}
          </button>
        ) : null}
      </article>
    </section>
  );
}
