import { useCallback, useEffect, useState } from "react";

import {
  getLatestReconciliation,
  getSyncContinuityStatus,
  listDeadLetters,
  retryDeadLetter,
  runReconciliation,
  type ContinuityMode,
  type DeadLetter,
  type ReconciliationReport,
  type SyncContinuityStatus,
} from "../api/continuity";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingState } from "../components/ui";

const STATE_COPY: Record<ContinuityMode, { title: string; detail: string }> = {
  live: { title: "Live", detail: "Local Hub and cloud coordination are synchronized." },
  offline_local: { title: "Local only", detail: "Local operations remain available; cloud work stays durably queued." },
  cloud_continuity: { title: "Cloud continuity", detail: "Public cloud intake is active while Local Hub is unavailable." },
  synchronizing: { title: "Recovering", detail: "Queued work is draining and reconciliation has not completed yet." },
  stale: { title: "Stale", detail: "Heartbeat or snapshot freshness is outside the approved window." },
  attention_required: { title: "Attention required", detail: "A dead letter or reconciliation mismatch needs operator review." },
};

function fmt(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "Not recorded";
}

function messageFrom(error: unknown): string {
  return error instanceof ApiError ? error.message : "Continuity status could not be loaded.";
}

export function CafeContinuityPage() {
  const { token, user } = useAuth();
  const [status, setStatus] = useState<SyncContinuityStatus | null>(null);
  const [report, setReport] = useState<ReconciliationReport | null>(null);
  const [deadLetters, setDeadLetters] = useState<DeadLetter[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canOperate = user?.server_role === "super_admin" || user?.server_role === "admin" || user?.server_role === "store_manager";

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const [nextStatus, nextDeadLetters] = await Promise.all([
        getSyncContinuityStatus(token),
        listDeadLetters(token),
      ]);
      setStatus(nextStatus);
      setDeadLetters(nextDeadLetters);
      try {
        setReport(await getLatestReconciliation(token));
      } catch (err) {
        if (!(err instanceof ApiError) || err.status !== 404) throw err;
        setReport(null);
      }
      setError(null);
    } catch (err) {
      setError(messageFrom(err));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function reconcile() {
    if (!token || !canOperate) return;
    setWorking(true);
    try {
      setReport(await runReconciliation(token));
      await refresh();
    } catch (err) {
      setError(messageFrom(err));
    } finally {
      setWorking(false);
    }
  }

  async function retry(row: DeadLetter) {
    if (!token || !canOperate) return;
    setWorking(true);
    try {
      await retryDeadLetter(token, row.id);
      await refresh();
    } catch (err) {
      setError(messageFrom(err));
    } finally {
      setWorking(false);
    }
  }

  if (loading) return <LoadingState label="Loading continuity state" />;
  if (error && !status) {
    return (
      <ErrorState message={error}>
        <button className="secondary-button" onClick={() => void refresh()}>Retry</button>
      </ErrorState>
    );
  }

  const mode = status?.continuity_mode ?? "stale";
  const stateCopy = STATE_COPY[mode];
  const mismatchTotal = report
    ? report.order_mismatch_count + report.invoice_mismatch_count + report.payment_mismatch_count + report.stock_mismatch_count + report.queue_receipt_mismatch_count + report.closing_mismatch_count
    : 0;

  return (
    <section className="page-stack" data-hc4-continuity-state={mode}>
      <div className="page-header">
        <div>
          <p className="eyebrow">HC4 continuity</p>
          <h2>Operations continuity</h2>
          <p className="page-description">Queue durability, writer fencing, recovery and reconciliation status for this authorized venture scope.</p>
        </div>
        {canOperate ? <button className="primary-button" disabled={working} onClick={() => void reconcile()}>{working ? "Checking…" : "Run reconciliation"}</button> : null}
      </div>

      {error ? <div className="notice error">{error}</div> : null}
      <article className="panel wide">
        <div className="panel-header">
          <div><p className="eyebrow">Current state</p><h3>{stateCopy.title}</h3></div>
          <strong>{mode}</strong>
        </div>
        <p className="page-description">{status?.attention_message ?? stateCopy.detail}</p>
        <div className="metric-grid">
          <div className="metric-card"><span>Pending inbound</span><strong>{status?.pending_inbox ?? 0}</strong></div>
          <div className="metric-card"><span>Pending outbound</span><strong>{status?.pending_outbox ?? 0}</strong></div>
          <div className="metric-card"><span>Dead letters</span><strong>{status?.dead_letters ?? 0}</strong></div>
          <div className="metric-card"><span>Fencing epoch</span><strong>{status?.fencing_epoch ?? 0}</strong></div>
        </div>
        <div className="detail-grid">
          <p><strong>Last heartbeat</strong><br />{fmt(status?.last_heartbeat_at ?? null)}</p>
          <p><strong>Last cloud contact</strong><br />{fmt(status?.last_cloud_contact_at ?? null)}</p>
          <p><strong>Last inbound sync</strong><br />{fmt(status?.last_inbound_sync_at ?? null)}</p>
          <p><strong>Last outbound sync</strong><br />{fmt(status?.last_outbound_sync_at ?? null)}</p>
          <p><strong>Last queue drain</strong><br />{fmt(status?.last_queue_drain_at ?? null)}</p>
          <p><strong>Lease expires</strong><br />{fmt(status?.lease_expires_at ?? null)}</p>
        </div>
      </article>

      <article className="panel wide">
        <div className="panel-header"><div><p className="eyebrow">Reconciliation</p><h3>{report?.status ?? "Not run"}</h3></div></div>
        {report ? (
          <>
            <p className="page-description">Reference {report.reconciliation_reference} · completed {fmt(report.completed_at)}</p>
            <div className="metric-grid">
              <div className="metric-card"><span>Mismatches</span><strong>{mismatchTotal}</strong></div>
              <div className="metric-card"><span>Dead letters</span><strong>{report.dead_letter_count}</strong></div>
              <div className="metric-card"><span>Inbound after</span><strong>{report.pending_inbox_after}</strong></div>
              <div className="metric-card"><span>Outbound after</span><strong>{report.pending_outbox_after}</strong></div>
            </div>
          </>
        ) : <p className="page-description">No completed reconciliation exists for this scope yet.</p>}
      </article>

      <article className="panel wide">
        <div className="panel-header"><div><p className="eyebrow">Durable failures</p><h3>Dead-letter attention</h3></div><span>{deadLetters.length}</span></div>
        {deadLetters.length === 0 ? <p className="page-description">No unresolved synchronization dead letters.</p> : (
          <div className="table-wrap"><table><thead><tr><th>Direction</th><th>Error</th><th>Correlation</th><th>Retries</th><th>Action</th></tr></thead><tbody>
            {deadLetters.map((row) => <tr key={row.id}><td>{row.direction}</td><td>{row.error_code}<br /><small>{row.error_message}</small></td><td>{row.correlation_id}</td><td>{row.retry_count}</td><td>{canOperate && row.retryable ? <button className="secondary-button" disabled={working} onClick={() => void retry(row)}>Retry</button> : "Review"}</td></tr>)}
          </tbody></table></div>
        )}
      </article>
    </section>
  );
}
